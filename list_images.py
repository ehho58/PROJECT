#!/usr/bin/env python3
"""端末に保存されている画像ファイル名を取得するツール.

標準ライブラリのみで動作します (Python 3.8+)。

使い方の例::

    python3 list_images.py                    # 既定の画像フォルダを走査
    python3 list_images.py ~/Downloads        # 特定のフォルダを走査
    python3 list_images.py --names-only       # ファイル名だけを出力
    python3 list_images.py --format json      # JSON で出力
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

# 一般的な画像ファイルの拡張子（小文字・ドット付き）
IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".jpe",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".avif",
        ".svg",
        ".ico",
        ".raw",
        ".cr2",
        ".nef",
        ".arw",
        ".dng",
    }
)

# 走査対象から常に除外するディレクトリ名（キャッシュ・依存関係・VCS など）
SKIPPED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".cache",
        ".gradle",
        ".npm",
        "Library",  # macOS のアプリ内部データ（大量のアイコン等）
        "AppData",  # Windows のアプリ内部データ
    }
)


def default_search_roots() -> List[Path]:
    """OS ごとの「画像が置かれがちな場所」を返す（存在するものだけ）。"""
    home = Path.home()
    candidates = [
        home / "Pictures",
        home / "ピクチャ",
        home / "Photos",
        home / "Downloads",
        home / "ダウンロード",
        home / "Desktop",
        home / "デスクトップ",
        home / "Documents",
        home / "ドキュメント",
        # Android (Termux) でよく使われるパス
        Path("/sdcard/DCIM"),
        Path("/sdcard/Pictures"),
        Path("/sdcard/Download"),
    ]
    roots = [path for path in candidates if path.is_dir()]
    return roots or [home]


def iter_image_files(
    roots: Sequence[Path],
    extensions: Iterable[str],
    recursive: bool = True,
    include_hidden: bool = False,
    max_depth: int | None = None,
) -> Iterator[Path]:
    """指定したディレクトリ配下の画像ファイルを列挙する。"""
    wanted = {ext.lower() if ext.startswith(".") else "." + ext.lower() for ext in extensions}
    seen: set[Path] = set()

    for root in roots:
        if root.is_file():
            if root.suffix.lower() in wanted:
                yield root
            continue
        if not root.is_dir():
            print(f"警告: ディレクトリが見つかりません: {root}", file=sys.stderr)
            continue

        root_depth = len(root.resolve().parts)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)

            if not recursive:
                dirnames[:] = []
            else:
                depth = len(current.resolve().parts) - root_depth
                if max_depth is not None and depth >= max_depth:
                    dirnames[:] = []
                else:
                    dirnames[:] = [
                        name
                        for name in dirnames
                        if name not in SKIPPED_DIR_NAMES
                        and (include_hidden or not name.startswith("."))
                    ]

            for name in filenames:
                if not include_hidden and name.startswith("."):
                    continue
                path = current / name
                if path.suffix.lower() not in wanted:
                    continue
                # 別々の root が重なっていた場合の重複を除去する
                try:
                    key = path.resolve()
                except OSError:
                    key = path
                if key in seen:
                    continue
                seen.add(key)
                yield path


def describe(path: Path) -> dict:
    """出力用にファイル 1 件の情報をまとめる。"""
    try:
        stat = path.stat()
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
    except OSError:
        size = None
        modified = None
    return {
        "name": path.name,
        "path": str(path),
        "extension": path.suffix.lower(),
        "size_bytes": size,
        "modified": modified,
    }


def sort_records(records: List[dict], key: str) -> List[dict]:
    if key == "name":
        return sorted(records, key=lambda r: r["name"].lower())
    if key == "path":
        return sorted(records, key=lambda r: r["path"].lower())
    if key == "size":
        return sorted(records, key=lambda r: r["size_bytes"] or 0, reverse=True)
    if key == "modified":
        return sorted(records, key=lambda r: r["modified"] or "", reverse=True)
    return records


def human_size(size: int | None) -> str:
    if size is None:
        return "-"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def render(records: List[dict], fmt: str, names_only: bool) -> str:
    if names_only:
        return "\n".join(r["name"] for r in records)
    if fmt == "json":
        return json.dumps(records, ensure_ascii=False, indent=2)
    if fmt == "csv":
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["name", "path", "extension", "size_bytes", "modified"])
        writer.writeheader()
        writer.writerows(records)
        return buffer.getvalue().rstrip("\n")
    return "\n".join(f"{r['name']}\t{human_size(r['size_bytes'])}\t{r['path']}" for r in records)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="端末に保存されている画像ファイル名を取得します。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="走査するディレクトリ（省略時は画像が置かれがちな既定フォルダ）",
    )
    parser.add_argument(
        "-e",
        "--ext",
        action="append",
        dest="extensions",
        metavar="EXT",
        help="対象の拡張子を指定（複数指定可。例: -e jpg -e png）",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("text", "json", "csv"),
        default="text",
        help="出力形式（既定: text）",
    )
    parser.add_argument("--names-only", action="store_true", help="ファイル名だけを出力する")
    parser.add_argument("--no-recursive", action="store_true", help="サブディレクトリを辿らない")
    parser.add_argument("--include-hidden", action="store_true", help="隠しファイル・隠しフォルダも対象にする")
    parser.add_argument("--max-depth", type=int, default=None, metavar="N", help="走査する階層の上限")
    parser.add_argument(
        "--sort",
        choices=("name", "path", "size", "modified"),
        default="name",
        help="並び順（既定: name）",
    )
    parser.add_argument("--limit", type=int, default=None, metavar="N", help="出力する件数の上限")
    parser.add_argument("-o", "--output", type=Path, metavar="FILE", help="結果を書き出すファイル")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    roots = args.paths or default_search_roots()
    extensions = args.extensions or IMAGE_EXTENSIONS

    records = [
        describe(path)
        for path in iter_image_files(
            roots,
            extensions,
            recursive=not args.no_recursive,
            include_hidden=args.include_hidden,
            max_depth=args.max_depth,
        )
    ]
    records = sort_records(records, args.sort)
    if args.limit is not None:
        records = records[: args.limit]

    output = render(records, args.format, args.names_only)

    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"{len(records)} 件を {args.output} に書き出しました。", file=sys.stderr)
    else:
        if output:
            print(output)
        print(f"\n合計 {len(records)} 件の画像ファイルが見つかりました。", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
