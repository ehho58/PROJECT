# list_images

端末に保存されている画像ファイル名を取得するコマンドラインツールです。
Python 3.8 以降があれば、追加のインストールなしで動作します（標準ライブラリのみ）。

## 使い方

```bash
# 画像が置かれがちな既定フォルダ（Pictures / Downloads / Desktop など）を走査
python3 list_images.py

# フォルダを指定して走査
python3 list_images.py ~/Downloads ~/Desktop

# ファイル名だけを出力
python3 list_images.py --names-only

# 拡張子を絞り込む
python3 list_images.py -e jpg -e png

# JSON / CSV で出力、ファイルに書き出す
python3 list_images.py --format json -o images.json
```

## オプション

| オプション | 説明 |
| --- | --- |
| `paths...` | 走査するディレクトリ（省略時は既定フォルダ） |
| `-e, --ext EXT` | 対象の拡張子（複数指定可） |
| `-f, --format {text,json,csv}` | 出力形式（既定: `text`） |
| `--names-only` | ファイル名だけを出力 |
| `--no-recursive` | サブディレクトリを辿らない |
| `--include-hidden` | 隠しファイル・隠しフォルダも対象にする |
| `--max-depth N` | 走査する階層の上限 |
| `--sort {name,path,size,modified}` | 並び順（既定: `name`） |
| `--limit N` | 出力件数の上限 |
| `-o, --output FILE` | 結果をファイルに書き出す |

## 対応拡張子

`.jpg` `.jpeg` `.jpe` `.png` `.gif` `.bmp` `.webp` `.tif` `.tiff` `.heic` `.heif`
`.avif` `.svg` `.ico` および RAW 形式（`.raw` `.cr2` `.nef` `.arw` `.dng`）。

## 挙動のメモ

- 既定では隠しファイル・隠しフォルダを除外します（`--include-hidden` で有効化）。
- `.git` / `node_modules` / `__pycache__` / `Library` / `AppData` などの
  キャッシュ・アプリ内部データのフォルダは常にスキップします。
- シンボリックリンクは辿りません。複数の走査対象が重なっている場合は重複を除去します。
- 読み取り専用のツールです。ファイルの変更・削除・送信は一切行いません。

## 各端末での実行例

```bash
# macOS
python3 list_images.py ~/Pictures ~/Downloads

# Windows (PowerShell)
python list_images.py $env:USERPROFILE\Pictures

# Android (Termux ※ termux-setup-storage で権限付与後)
python3 list_images.py /sdcard/DCIM /sdcard/Pictures
```
