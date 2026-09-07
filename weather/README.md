# 豊島区の週間天気 — 自動更新アーティファクト

公開先（固定URL）: <https://claude.ai/code/artifact/8932cf28-7927-4b27-93a6-a7392aeb398b>

1日2回（**06:25 / 17:25 JST**）、Routine が新しいセッションを起動して予報を取り直し、
同じURLへ再公開します。気象庁の週間予報の発表（11:00 / 17:00 JST）の後を拾う時刻です。

## 構成

| ファイル | 役割 |
| --- | --- |
| `data.json` | 予報の数値と解説文。**唯一の入力**。 |
| `style.css` | ページのCSS（ライト／ダーク両対応のトークン定義を含む）。 |
| `build.py` | `data.json` + `style.css` → 公開用HTML。依存なし。 |
| `fetch_jma.py` | 気象庁APIから `data.json` の数値部分を更新する。 |
| `toshima-weather.html` | 生成物。手で編集しないこと。 |

```sh
python3 weather/fetch_jma.py        # 数値を更新（到達不可なら exit 3）
python3 weather/build.py            # weather/toshima-weather.html を生成
python3 weather/build.py -o /tmp/x.html
```

## データ取得の2経路

**第1経路 — 気象庁API（`fetch_jma.py`）。** 東京地方（130010）の3日予報と週間予報、
豊島区（13116）の警報・注意報を読み、`data.json` の `days` と `advisories.active` を差し替える。
気温は代表地点である東京（アメダス 44132）の値。

> ⚠️ **この経路は実地検証できていません。** 現在の実行環境は `www.jma.go.jp` への通信が
> egress プロキシで遮断されており（`Tunnel connection failed: 403`）、レスポンスを一度も
> 受け取れていません。パース処理は気象庁JSONの公開仕様に沿って書いたもので、実データでの
> 確認は未了です。環境の許可リストに `www.jma.go.jp` が入れば、この経路が自動的に有効になります。

**第2経路 — Web検索（フォールバック）。** `fetch_jma.py` が exit 3 を返したら、
セッションが WebSearch で各社の予報を集め、`data.json` を手で書き換える。
豊島区単位の値が取れない項目は `ref` に該当キー（`tmax` / `tmin` / `pop` / `mm`）を入れると、
ページ上で † が付き「東京（都心）の参考値」と注記される。値そのものが無い場合は `null`。

## `data.json` の書式

```jsonc
{
  "generated_label": "2026年9月7日",   // ページ本文に出る表記
  "generated_iso":   "2026-09-07",     // ヘッダの「更新」
  "data_origin":     "web-search",     // "jma" | "web-search" — 免責文が切り替わる
  "location":   { "name": "豊島区", "code": "13116",
                  "area": "東京都 東京地方", "area_code": "130010" },
  "advisories": { "active": ["大雨注意報"], "text": "…" },
  "days": [
    { "md": "9/7", "dow": "月", "dow_en": "MON", "today": true,
      "weather": "雨時々曇",          // 「晴」「曇」「雨」「雪」の文字からアイコンを組み立てる
      "note":    "終日の雨。道路冠水と落雷に注意",
      "tmax": 24, "tmin": 21, "pop": 100, "mm": 124,
      "ref": [] }                      // † を付けるフィールド名の配列
  ],
  "highlights": [ { "lead": "前半は雨、後半に回復。", "body": "…" } ],
  "sources":    [ ["ラベル", "https://…"] ]
}
```

`days` は7件（先頭が当日、`today: true`）。「この期間の数字」は `days` から自動集計するので
手で書かない。`highlights` と `advisories.text` は自動生成されず、更新のたびに書き直す。

## 再公開

Artifact ツールに **`url` を必ず渡す**（渡さないと別のアーティファクトが新規作成され、
共有済みのリンクが更新されない）。公開前に `action: "read"` で現行版を読むこと。
`favicon` は再公開時に渡さない（☔ が維持される）。
