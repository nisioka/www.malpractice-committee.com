#!/usr/bin/env python3
"""記事の末尾の著者欄（「管理者」）を、全ページから外す。

記事の末尾（病院カテゴリの下、コメント欄の上）に、テーマ（Xeory）が出していた著者欄
`<aside class="post-author">` が残っている。中身は人の形の仮のアイコン（`masman.png`）と
「管理者」という名前だけで、WordPress のときの投稿者の表示名がそのまま出ていた移行の名残なので、
枠ごと外す。著者欄の手前の空白（`</footer>` との間の空行と字下げ）も一緒に外す。
ほかのバイトは変えない。何度実行しても結果は同じ。

残すもの:
- `<head>` の構造化データ（JSON-LD）の `author`・`publisher`（`"name": "管理者"` の Person）。
  画面には出ず、検索結果の扱いに関わるので、このスクリプトでは触らない
- テーマの CSS の `.post-author` の規則と `masman.png`。`wp-content/` は触らない決まりで、
  使うページが無くなるだけなので害は無い
- 本文の中の「管理者」（「院長などの管理者」など）。記事の中身なので触らない

生成側（`sitelib.py`）からも著者欄を外してあるので、記事を足しても入らない。

対象は Git が追跡している全 HTML。WordPress 時代の HTML を取り込み直したときは、
このスクリプトを掛け直す。

  python3 _automation/remove_post_author.py --dry-run   # 件数だけ表示
  python3 _automation/remove_post_author.py             # 書き換える
"""
import argparse
import collections
import os
import re
import sys

import check_links as cl

# 著者欄の手前の空白から、閉じタグの後ろの行末の空白まで。著者欄の中に aside は入れ子にならない。
POST_AUTHOR = re.compile(
    r"\s*<aside class=\"post-author\"[^>]*>(?:(?!</?aside\b).)*</aside>[ \t]*", re.S)


def fix(text, stats):
    text, n = POST_AUTHOR.subn("", text)
    if n:
        stats["記事の末尾の著者欄（post-author、「管理者」）"] += n
    if '<aside class="post-author"' in text:
        stats["残した 著者欄（閉じタグが見つからない）"] += 1
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに件数だけ表示")
    args = ap.parse_args()

    stats = collections.Counter()
    changed = 0
    for f in cl.tracked_files():
        if not f.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(cl.ROOT, f)
        with open(path, encoding="utf-8", newline="") as fh:
            before = fh.read()
        after = fix(before, stats)
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if any(k.startswith("残した") for k in stats):
        sys.exit(1)


if __name__ == "__main__":
    main()
