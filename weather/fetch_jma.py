#!/usr/bin/env python3
"""気象庁の予報JSONから weather/data.json の数値部分を更新する。

  python3 weather/fetch_jma.py            # data.json を上書き
  python3 weather/fetch_jma.py --dry-run  # 取得結果を表示するだけ

終了コード
  0  更新した
  3  気象庁へ到達できない（egress 遮断など）。呼び出し側は Web 検索へフォールバックすること。

注意: このセッションの実行環境は www.jma.go.jp への通信が egress プロキシで遮断されており、
      本スクリプトの取得経路は実地検証できていません（コード 3 で抜けることのみ確認済み）。
      解説文（highlights）と注意報の本文は自動生成せず、data.json の既存値を保ちます。
"""

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
PREF_CODE = "130000"          # 東京都
AREA_CODE = "130010"          # 東京地方（豊島区が属する予報区）
CITY_CODE = "13116"           # 豊島区（警報・注意報の細分区域）
AMEDAS = "44132"              # 東京（気温の代表地点）

FORECAST_URL = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{PREF_CODE}.json"
WARNING_URL = f"https://www.jma.go.jp/bosai/warning/data/warning/{PREF_CODE}.json"
DOW_JA = ["月", "火", "水", "木", "金", "土", "日"]
DOW_EN = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# 週間予報は天気コードしか持たないため、頻出コードのみ telop に対応付ける。
TELOP = {
    "100": "晴", "101": "晴時々曇", "102": "晴一時雨", "104": "晴一時雪",
    "110": "晴のち曇", "111": "晴のち曇", "112": "晴のち雨", "114": "晴のち雨",
    "115": "晴のち雪", "200": "曇", "201": "曇時々晴", "202": "曇一時雨",
    "203": "曇時々雨", "204": "曇一時雪", "206": "曇時々雪",
    "210": "曇のち晴", "211": "曇のち晴", "212": "曇のち雨", "214": "曇のち雨",
    "215": "曇のち雪", "218": "曇のち雪", "270": "雪時々曇",
    "300": "雨", "301": "雨時々晴", "302": "雨時々止む", "303": "雨時々雪",
    "308": "雨（大雨のおそれ）", "311": "雨のち晴", "313": "雨のち曇",
    "314": "雨のち雪", "400": "雪", "401": "雪時々晴", "402": "雪時々止む",
    "403": "雪時々雨", "406": "風雪強い", "411": "雪のち晴", "413": "雪のち曇",
    "414": "雪のち雨",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "toshima-weather/1.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.load(res)


def pick(areas, code, key=None):
    for a in areas:
        if a["area"]["code"] == code:
            return a[key] if key else a
    return None


def day_of(iso):
    return dt.datetime.fromisoformat(iso).date()


def near_term(part):
    """3日予報パート -> {date: {weather, pop, tmax, tmin}}"""
    out = {}
    ts = part["timeSeries"]
    weathers = pick(ts[0]["areas"], AREA_CODE, "weathers") or []
    for iso, text in zip(ts[0]["timeDefines"], weathers):
        out.setdefault(day_of(iso), {})["weather"] = text.replace("　", "")

    if len(ts) > 1:
        pops = pick(ts[1]["areas"], AREA_CODE, "pops") or []
        for iso, p in zip(ts[1]["timeDefines"], pops):
            if p == "":
                continue
            d = out.setdefault(day_of(iso), {})
            d["pop"] = max(d.get("pop", 0), int(p))

    if len(ts) > 2:
        temps = pick(ts[2]["areas"], AMEDAS, "temps") or []
        for iso, t in zip(ts[2]["timeDefines"], temps):
            if t == "":
                continue
            d = out.setdefault(day_of(iso), {})
            hour = dt.datetime.fromisoformat(iso).hour
            key = "tmin" if hour < 12 else "tmax"
            d[key] = int(t)
    return out


def weekly(part):
    """週間予報パート -> {date: {weather, pop, tmax, tmin}}"""
    out = {}
    ts = part["timeSeries"]
    codes = pick(ts[0]["areas"], AREA_CODE, "weatherCodes") or []
    pops = pick(ts[0]["areas"], AREA_CODE, "pops") or []
    for i, iso in enumerate(ts[0]["timeDefines"]):
        d = out.setdefault(day_of(iso), {})
        if i < len(codes):
            d["weather"] = TELOP.get(codes[i], "")
        if i < len(pops) and pops[i] != "":
            d["pop"] = int(pops[i])

    if len(ts) > 1:
        mins = pick(ts[1]["areas"], AMEDAS, "tempsMin") or []
        maxs = pick(ts[1]["areas"], AMEDAS, "tempsMax") or []
        for i, iso in enumerate(ts[1]["timeDefines"]):
            d = out.setdefault(day_of(iso), {})
            if i < len(mins) and mins[i] != "":
                d["tmin"] = int(mins[i])
            if i < len(maxs) and maxs[i] != "":
                d["tmax"] = int(maxs[i])
    return out


def warnings_for_city(payload):
    names = []
    for area_type in payload.get("areaTypes", []):
        for area in area_type.get("areas", []):
            if area.get("code") != CITY_CODE:
                continue
            for w in area.get("warnings", []):
                if w.get("status") in ("解除", "発表警報・注意報はなし"):
                    continue
                name = w.get("name") or w.get("code")
                if name and name not in names:
                    names.append(name)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        forecast = get(FORECAST_URL)
        warning = get(WARNING_URL)
    except (urllib.error.URLError, OSError, TimeoutError) as err:
        print(f"jma unreachable: {err}", file=sys.stderr)
        print("-> fall back to web search (see weather/README.md)", file=sys.stderr)
        return 3

    merged = weekly(forecast[1])
    for date, values in near_term(forecast[0]).items():
        merged.setdefault(date, {}).update(values)

    today = min(merged)
    days = []
    for date in sorted(merged)[:7]:
        v = merged[date]
        days.append({
            "md": f"{date.month}/{date.day}",
            "dow": DOW_JA[date.weekday()],
            "dow_en": DOW_EN[date.weekday()],
            **({"today": True} if date == today else {}),
            "weather": v.get("weather", ""),
            "note": "",
            "tmax": v.get("tmax"),
            "tmin": v.get("tmin"),
            "pop": v.get("pop"),
            "mm": None,
            "ref": [],
        })

    with open(args.data, encoding="utf-8") as fh:
        data = json.load(fh)
    data["days"] = days
    data["generated_iso"] = today.isoformat()
    data["generated_label"] = f"{today.year}年{today.month}月{today.day}日"
    data["data_origin"] = "jma"
    data.setdefault("advisories", {})["active"] = warnings_for_city(warning)

    if args.dry_run:
        print(json.dumps(days, ensure_ascii=False, indent=2))
        return 0

    with open(args.data, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"updated {args.data} from jma ({len(days)} days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
