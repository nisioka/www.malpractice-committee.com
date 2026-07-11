#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pr_preview.py の manifest.tsv から、PRに貼るスクショ埋め込みコメント(markdown)を生成する。

使い方:
  python3 _automation/pr_preview_comment.py <manifest.tsv> <raw_image_base_url>
出力: 標準出力に markdown。先頭に sticky 判定用マーカーを含む。
"""
import pathlib
import sys

MARKER = "<!-- pr-preview-bot -->"


def main(argv) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 1
    manifest = pathlib.Path(argv[1])
    rawbase = argv[2].rstrip("/")
    rows = [l.split("\t") for l in manifest.read_text(encoding="utf-8").splitlines() if l.strip()]

    out = [
        MARKER,
        "## 🖼️ ページプレビュー",
        "",
        f"このPRで追加・変更された **{len(rows)}ページ** を実CSS付きで描画しました"
        "（マージ前の見た目確認用）。",
        "",
    ]
    for png, rel, label in rows:
        out.append(f"<details open><summary><b><code>{label}</code></b> &nbsp; "
                   f"<code>{rel}</code></summary>")
        out.append("")
        out.append(f"![{label}]({rawbase}/{png})")
        out.append("")
        out.append("</details>")
        out.append("")
    out.append("<sub>自動生成: `.github/workflows/pr-preview.yml` ／ "
               "画像は `pr-previews` ブランチに保存（適宜削除可）。</sub>")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
