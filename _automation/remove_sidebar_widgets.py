#!/usr/bin/env python3
"""サイドバーから、機能していない部品を枠ごと外す。

  サイト内検索 / twitter / 関連書籍 / アンドロイド アプリ

サイト内検索は、WordPress が処理していた旧い検索欄（id="search-2"）のこと。今の検索欄
（id="site-search"）は add_sidebar_search.py が入れるもので、このスクリプトは触らない。

対象は全 HTML と `_automation/templates/sidebar.html`。部品は id と見出しの両方が
一致したときだけ外し、見出しと外側のウィジェット要素ごと消す。サイドバーの外と、
該当箇所以外のバイトは変えない。何度実行しても結果は同じ。

  python3 _automation/remove_sidebar_widgets.py --dry-run   # 件数だけ表示
  python3 _automation/remove_sidebar_widgets.py             # 書き換える
"""
import argparse
import collections
import os
import re
import sys

import check_links as cl

SIDE_START = '<div id="side"'
SIDE_END = "</div><!-- /side -->"
# (ウィジェットの id, 見出し)。id は WordPress の採番なので、見出しでも確かめる。
WIDGETS = [
    ("search-2", "サイト内検索"),
    ("custom_html-4", "twitter"),
    ("custom_html-3", "関連書籍"),
    ("text-12", "アンドロイド アプリ"),
]
DIV = re.compile(r"<div\b|</div>", re.I)


def element_end(text, start):
    """start から始まる div の、閉じタグの直後の位置。釣り合わなければ None。"""
    depth = 0
    for m in DIV.finditer(text, start):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return m.end()
    return None


def strip_widgets(text, stats):
    """サイドバーの中から WIDGETS を外した文字列を返す。"""
    a = text.find(SIDE_START)
    if a < 0:
        return text
    b = text.find(SIDE_END, a)
    if b < 0:
        stats["サイドバーの終端が見つからない"] += 1
        return text
    side = text[a:b]
    for wid, title in WIDGETS:
        start = side.find(f'<div id="{wid}" ')
        if start < 0:
            continue
        end = element_end(side, start)
        heading = f'<span class="side-title-inner">{title}</span>'
        if end is None or heading not in side[start:end]:
            stats[f"外さなかった {title}（id は一致、中身が想定と違う）"] += 1
            continue
        side = side[:start] + side[end:]
        stats[f"外した {title}"] += 1
    return text[:a] + side + text[b:]


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
        after = strip_widgets(before, stats)
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if any(not k.startswith("外した ") for k in stats):
        sys.exit(1)


if __name__ == "__main__":
    main()
