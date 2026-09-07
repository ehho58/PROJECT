#!/usr/bin/env python3
"""豊島区の週間天気アーティファクトを weather/data.json から組み立てる。

  python3 weather/build.py                 -> weather/toshima-weather.html
  python3 weather/build.py -o /path/x.html -> 出力先を指定

依存なし（標準ライブラリのみ）。data.json の書式は weather/README.md を参照。
"""

import argparse
import html
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# 気温レンジバーの目盛。データが外に出たら自動で広げる。
SCALE_FLOOR, SCALE_CEIL = 16, 36
MIN_SPAN = 16

E = html.escape


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --- 天気アイコン ------------------------------------------------------------
# 天気文字列から、雲量・降水・日射の3要素を読み取って SVG を組み立てる。

def read_sky(text):
    """天気文字列 -> (sun, cloud, rain) の強さ。rain は 0-3。"""
    sun = "晴" in text
    cloud = "曇" in text or "くもり" in text
    rain = 0
    if "雨" in text or "雪" in text:
        rain = 2
        if "一時" in text or "時々" in text or "のち" in text:
            rain = 1
        if text.strip() in ("雨", "大雨", "雪"):
            rain = 3
    return sun, cloud, rain


CLOUD_PATH = ("M10 18a5.2 5.2 0 0 1 .5-10.3 7 7 0 0 1 13.2 2.2"
              "A4.6 4.6 0 0 1 23.3 18H10Z")
CLOUD_PATH_LOW = ("M9 22a5.4 5.4 0 0 1 .5-10.7A7.2 7.2 0 0 1 23 13.6"
                  "A4.8 4.8 0 0 1 22.6 22H9Z")
DROPS = {
    1: "M13.5 21.5 11.5 27M20 21.5l-2 5.5",
    2: "M12.5 21.5 11 25.5M18.5 21.5 17 25.5",
    3: "M11 21.5 9 27M16.5 21.5l-2 5.5M22 21.5l-2 5.5",
}


def icon_svg(text, heavy=False):
    sun, cloud, rain = read_sky(text)
    parts = ['<svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">']
    if sun:
        parts.append('<circle cx="21.5" cy="11" r="5" fill="none" '
                     'stroke="var(--sun)" stroke-width="1.6"></circle>')
    if cloud or rain:
        path = CLOUD_PATH if rain else CLOUD_PATH_LOW
        fill = "var(--sheet)" if sun else "none"
        opacity = ".7" if sun else (".55" if rain else ".65")
        parts.append(f'<path d="{path}" fill="{fill}" stroke="currentColor" '
                     f'stroke-width="1.6" stroke-linejoin="round" opacity="{opacity}"></path>')
    if rain:
        offset = ' transform="translate(0,3)"' if sun else ""
        parts.append(f'<path d="{DROPS[rain]}"{offset} stroke="var(--rain)" '
                     'stroke-width="2.1" stroke-linecap="round"></path>')
    if heavy:
        parts.append('<path d="M17.8 20.4h3.4l-2.6 3.4h3" fill="none" '
                     'stroke="var(--alert)" stroke-width="1.5" '
                     'stroke-linejoin="round" stroke-linecap="round"></path>')
    parts.append("</svg>")
    return "".join(parts)


# --- 気温スケール ------------------------------------------------------------

def temp_scale(days):
    temps = [t for d in days for t in (d.get("tmax"), d.get("tmin")) if t is not None]
    lo, hi = SCALE_FLOOR, SCALE_CEIL
    if temps:
        lo = min(lo, (min(temps) - 3) // 2 * 2)
        hi = max(hi, -(-(max(temps) + 3) // 2) * 2)
    if hi - lo < MIN_SPAN:
        hi = lo + MIN_SPAN
    return lo, hi


def pct(value, lo, hi):
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100))


# --- 部品 --------------------------------------------------------------------

def dagger(day, field):
    return "<sup>&dagger;</sup>" if field in day.get("ref", []) else ""


def temps_cell(day, lo, hi):
    mid = f'<span class="tick" style="left:{pct((lo + hi) / 2, lo, hi):.4g}%"></span>'
    tmax, tmin = day.get("tmax"), day.get("tmin")
    if tmax is not None and tmin is not None:
        left = pct(tmin, lo, hi)
        width = pct(tmax, lo, hi) - left
        warm = " warm" if tmax >= 26 else ""
        mark = f'<span class="bar{warm}" style="left:{left:.4g}%;width:{width:.4g}%"></span>'
    elif tmax is not None or tmin is not None:
        only = tmax if tmax is not None else tmin
        mark = f'<span class="pt" style="left:{pct(only, lo, hi):.4g}%"></span>'
    else:
        mark = ""
    lo_txt = f'{tmin}&deg;' if tmin is not None else "&mdash;"
    hi_txt = f'{tmax}&deg;' if tmax is not None else "&mdash;"
    return (
        '<div class="temps">'
        f'<div class="track">{mid}{mark}</div>'
        '<div class="temp-nums">'
        f'<span class="lo">最低 {lo_txt}{dagger(day, "tmin")}</span>'
        f'<span class="hi">最高 {hi_txt}{dagger(day, "tmax")}</span>'
        "</div></div>"
    )


def rain_cell(day):
    pop = day.get("pop")
    width = pop if pop is not None else 0
    strong = " strong" if pop is not None and pop >= 70 else ""
    pop_txt = f'{pop}%{dagger(day, "pop")}' if pop is not None else "&mdash;"
    mm = day.get("mm")
    if mm is None:
        mm_txt, mm_cls = "雨量 &mdash;", ""
    else:
        mm_txt = f'雨量 {mm} mm{dagger(day, "mm")}'
        mm_cls = " heavy" if mm >= 50 else ""
    return (
        '<div class="rain-cell"><div class="rain">'
        f'<span class="meter"><i class="{strong.strip()}" style="width:{width}%"></i></span>'
        f'<span class="pop">{pop_txt}</span>'
        f'</div><span class="mm{mm_cls}">{mm_txt}</span></div>'
    )


def row(day, lo, hi):
    cls = "row today" if day.get("today") else "row"
    dow_cls = {"土": " sat", "日": " sun"}.get(day["dow"], "")
    badge = '<span class="badge">今日</span>' if day.get("today") else ""
    heavy = (day.get("mm") or 0) >= 50 or (day.get("pop") or 0) >= 90
    note = day.get("note", "")
    return (
        f'<div class="{cls}">'
        f'<div class="date"><span class="md">{E(day["md"])}</span>'
        f'<span class="dow{dow_cls}">{E(day["dow_en"])} &middot; {E(day["dow"])}</span>{badge}</div>'
        f'<div class="cond">{icon_svg(day["weather"], heavy)}'
        f'<div class="cond-text"><span class="w">{E(day["weather"])}</span>'
        f'<span class="note">{E(note)}</span></div></div>'
        f'{temps_cell(day, lo, hi)}{rain_cell(day)}</div>'
    )


def facts(days):
    """予報値から集計。編集ではなくデータから出す。"""
    out = []
    wet = [d for d in days if (d.get("pop") or 0) >= 60]
    out.append(("降水確率 60% 以上の日", f"{len(wet)} 日 / {len(days)} 日"))
    highs = [d for d in days if d.get("tmax") is not None]
    lows = [d for d in days if d.get("tmin") is not None]
    if highs:
        out.append(("最高気温の幅",
                    f'{min(d["tmax"] for d in highs)} &ndash; {max(d["tmax"] for d in highs)} &deg;C'))
    if lows:
        out.append(("最低気温の幅",
                    f'{min(d["tmin"] for d in lows)} &ndash; {max(d["tmin"] for d in lows)} &deg;C'))
    rains = [d for d in days if d.get("mm") is not None]
    if rains:
        top = max(rains, key=lambda d: d["mm"])
        out.append(("最大の日雨量", f'{top["mm"]} mm（{E(top["md"])}）'))
    if highs:
        cool = min(highs, key=lambda d: d["tmax"])
        warm = max(highs, key=lambda d: d["tmax"])
        out.append(("もっとも涼しい日", f'{E(cool["md"])}（{E(cool["dow"])}）'))
        out.append(("もっとも暑い日", f'{E(warm["md"])}（{E(warm["dow"])}）'))
    return out


ORIGIN_NOTE = {
    "jma": "数値は気象庁の予報電文（bosai forecast API）から自動取得しています。",
    "web-search": "外部APIへ直接接続できない環境のため、数値はWeb検索経由で各社の予報から集めています。"
                  "豊島区単位の値が得られなかった項目には &dagger; を付け、東京（都心）の参考値を掲載しています。",
}


def render(data, css):
    days = data["days"]
    lo, hi = temp_scale(days)
    loc = data["location"]
    adv = data.get("advisories") or {}
    tags = "".join(f'<span class="tag">{E(t)}</span>' for t in adv.get("active", []))
    rows = "".join(row(d, lo, hi) for d in days)
    facts_html = "".join(f"<dt>{E(k)}</dt><dd>{v}</dd>" for k, v in facts(days))
    highlights = "".join(
        f'<p><strong>{E(h["lead"])}</strong>{E(h["body"])}</p>' for h in data.get("highlights", []))
    sources = "".join(
        f'<a href="{E(url)}" target="_blank" rel="noopener">{E(label)}</a>'
        for label, url in data.get("sources", []))
    origin = ORIGIN_NOTE.get(data.get("data_origin", "web-search"), "")

    advisory = ""
    if adv.get("active") or adv.get("text"):
        advisory = f"""
  <section class="advisory">
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <path d="M11 2.6 20.4 19H1.6L11 2.6Z" fill="none" stroke="var(--caution)" stroke-width="1.7" stroke-linejoin="round"></path>
      <path d="M11 8.4v4.6" stroke="var(--caution)" stroke-width="1.9" stroke-linecap="round"></path>
      <circle cx="11" cy="16.1" r="1.05" fill="var(--caution)"></circle>
    </svg>
    <div class="advisory-body">
      <div class="advisory-title">取得時点で{E(loc['name'])}に発表中の注意報</div>
      <div class="tags">{tags}</div>
      <p>{E(adv.get('text', ''))}</p>
    </div>
  </section>"""

    return f"""<title>{E(loc['name'])}の週間天気</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@600;700&amp;family=Zen+Kaku+Gothic+New:wght@400;500;700&amp;family=IBM+Plex+Mono:wght@400;500;600&amp;display=swap">
<style>
{css}</style>

<div class="wrap">

  <header class="masthead">
    <div class="eyebrow">Toshima-ku, Tokyo &middot; 7-day outlook</div>
    <h1>{E(loc['name'])}の週間天気</h1>
    <div class="masthead-foot">
      <span>地点 <b>{E(loc['name'])}（{E(loc['code'])}）</b></span>
      <span>予報区 <b>{E(loc['area'])}（{E(loc['area_code'])}）</b></span>
      <span>更新 <b>{E(data['generated_iso'])}</b></span>
    </div>
  </header>
{advisory}

  <section class="sheet" aria-label="週間予報表">
    <div class="sheet-head">
      <div>日付</div>
      <div>天気</div>
      <div class="col-scale"><span>{lo}&deg;C</span><span>気温レンジ</span><span>{hi}&deg;C</span></div>
      <div style="text-align:right">降水確率 / 雨量</div>
    </div>
{rows}
    <div class="scale-note">
      <span>気温レンジバーの目盛 {lo}&deg;C &ndash; {hi}&deg;C（中央の細線 = {(lo + hi) // 2}&deg;C）</span>
      <span>&dagger; 豊島区の値が取れず東京（都心）の参考値</span>
      <span>&mdash; = データなし</span>
    </div>
  </section>

  <div class="cols">
    <section class="prose">
      <h2>今週の見どころ</h2>
{highlights}
    </section>

    <aside>
      <h2>この期間の数字</h2>
      <dl class="facts">{facts_html}</dl>
    </aside>
  </div>

  <section class="prose">
    <h2>出典と最新情報</h2>
    <div class="sources">{sources}</div>
  </section>

  <p class="disclaimer">
    <b>データについて。</b>このページは <b>{E(data['generated_label'])}</b> 時点の予報スナップショットで、
    定期実行タスクが1日2回（06:25 / 17:25 JST）再取得して同じURLに再公開しています。
    ページ自身は予報サーバーへ接続しないため、開いている間は自動では変わりません &mdash; 再読み込みで最新版になります。
    {origin}
    &mdash; 印は該当データが取得できなかった項目です。行動判断には必ず上のリンク先で最新の発表をご確認ください。
  </p>

</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--data", default=str(HERE / "data.json"))
    ap.add_argument("-c", "--css", default=str(HERE / "style.css"))
    ap.add_argument("-o", "--out", default=str(HERE / "toshima-weather.html"))
    args = ap.parse_args()

    data = load(args.data)
    with open(args.css, encoding="utf-8") as fh:
        css = fh.read()
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data, css), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(data['days'])} days)")


if __name__ == "__main__":
    main()
