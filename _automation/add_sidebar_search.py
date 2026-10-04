#!/usr/bin/env python3
"""サイドバーの先頭に、サイト内検索の入力欄を入れる。

対象は全 HTML と `_automation/templates/sidebar.html`。入力欄は検索結果ページ
`/search/` へ語を渡すだけのフォームで、検索そのものは `search/search.js` が行う。

入れる位置は「医療ミス調査会」の部品の直前（WordPress のときと同じ位置）。既に入っていれば
下の WIDGET と同じ中身に揃えるので、何度実行しても結果は同じ。WIDGET を書き換えてから
実行すれば、全ページの入力欄が新しい中身に置き換わる。サイドバーの外のバイトは変えない。

WordPress が処理していた旧い検索欄（id="search-2"）が残っているページは書き換えない。
先に remove_sidebar_widgets.py で外すこと。

  python3 _automation/add_sidebar_search.py --dry-run   # 件数だけ表示
  python3 _automation/add_sidebar_search.py             # 書き換える
"""
import argparse
import collections
import os
import sys

import check_links as cl
import sitelib
from remove_sidebar_widgets import SIDE_END, SIDE_START, element_end

WIDGET_ID = "site-search"
OLD_WIDGET_ID = "search-2"
# この部品の直前に入れる。サイドバーのある全ページにある。
ANCHOR = '<div id="custom_html-5" '
# 入力欄とボタンの id はテーマの CSS（#searchform）が見た目を当てる先。ボタンの中身は
# FontAwesome の虫眼鏡。label は CSS で隠されるので、読み上げ用の名前は aria-label で付ける。
WIDGET = (
    f'<div id="{WIDGET_ID}" class="widget_search side-widget"><div class="side-widget-inner">'
    '<h4 class="side-title"><span class="side-title-inner">サイト内検索</span></h4>'
    f'<form role="search" method="get" id="searchform" action="{sitelib.ORIGIN}/search/" >\n'
    '  <div>\n'
    '  <input type="text" value="" name="q" id="s" aria-label="サイト内検索" />\n'
    '  <button type="submit" id="searchsubmit" aria-label="検索">&#xf002;</button>\n'
    '  </div>\n'
    '  </form></div></div>'
)


def add_widget(text, stats):
    """サイドバーに WIDGET を入れた文字列を返す。"""
    a = text.find(SIDE_START)
    if a < 0:
        return text
    b = text.find(SIDE_END, a)
    if b < 0:
        stats["サイドバーの終端が見つからない"] += 1
        return text
    side = text[a:b]
    if f'<div id="{OLD_WIDGET_ID}" ' in side:
        stats["旧い検索欄が残っている（先に remove_sidebar_widgets.py を掛ける）"] += 1
        return text
    start = side.find(f'<div id="{WIDGET_ID}" ')
    if start >= 0:
        end = element_end(side, start)
        if end is None:
            stats["入力欄の終端が見つからない"] += 1
            return text
        if side[start:end] == WIDGET:
            stats["そのまま"] += 1
            return text
        side = side[:start] + WIDGET + side[end:]
        stats["置き換えた"] += 1
    else:
        at = side.find(ANCHOR)
        if at < 0:
            stats["入れる位置が見つからない"] += 1
            return text
        side = side[:at] + WIDGET + side[at:]
        stats["入れた"] += 1
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
        after = add_widget(before, stats)
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if any(k not in ("入れた", "置き換えた", "そのまま") for k in stats):
        sys.exit(1)


if __name__ == "__main__":
    main()
