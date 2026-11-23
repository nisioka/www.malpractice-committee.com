#!/usr/bin/env python3
"""サイドバーの「人気記事」を、`_automation/popular.json` の記事リストから作り直す。

静的配信ではアクセス数を実行時に数えられないので、載せる記事は `popular.json` に
上から表示順で書いておき、このスクリプトが全ページのサイドバーへ同じ中身で埋め込む。
リストに書けるのは記事ページがある slug だけで、無い slug があれば何も書き換えずに止まる。

各項目の見出しと日付は manifest（記事ページ）から取るので、記事のタイトルを直したら
このスクリプトを掛け直す。サムネイルは次の順に探し、無ければ文字だけにする。

  1. WordPress Popular Posts が作った 75x75 の画像（wp-content/uploads/wordpress-popular-posts/<post_id>-featured-75x75.*）
  2. 記事のアイキャッチの 150x150 版（WordPress が作った <名前>-150x150.<拡張子>）

対象は全 HTML と `_automation/templates/sidebar.html`。WordPress のときの部品
（id="wpp-2"、見出し「閲覧ランキング」）が残っていれば置き換え、今の部品（id="popular-posts"）が
あれば下の組み立てと同じ中身に揃える。どちらも無いサイドバーには「医療ミス調査会」の部品の
直後に入れる。サイドバーの外のバイトは変えない。何度実行しても結果は同じ。

  python3 _automation/build_popular.py --dry-run   # 件数だけ表示
  python3 _automation/build_popular.py             # 書き換える
"""
import argparse
import collections
import html
import json
import os
import re
import sys

import check_links as cl
import sitelib
from remove_sidebar_widgets import SIDE_END, SIDE_START, element_end

LIST = os.path.join(cl.ROOT, "_automation", "popular.json")
MANIFEST = os.path.join(cl.ROOT, "_automation", "manifest.json")

WIDGET_ID = "popular-posts"
TITLE = "人気記事"
# WordPress Popular Posts が出していた部品。見出しでも確かめてから置き換える。
OLD_WIDGET_ID = "wpp-2"
OLD_TITLE = "閲覧ランキング"
# 部品が無いサイドバーでは、この部品の直後に入れる。
ANCHOR = '<div id="custom_html-5" '

WPP_THUMBS = os.path.join("wp-content", "uploads", "wordpress-popular-posts")
THUMB_SRC_RE = re.compile(r'<div class="post-thumbnail">\s*(?:<a [^>]*>)?<img [^>]*?\bsrc="([^"]+)"')


def load_posts():
    """popular.json の slug を manifest の記事に引き当てる。引けない slug があれば止める。"""
    with open(LIST, encoding="utf-8") as fh:
        slugs = json.load(fh)["posts"]
    with open(MANIFEST, encoding="utf-8") as fh:
        by_slug = {p["slug"]: p for p in json.load(fh)["posts"]}
    errors = []
    if not slugs:
        errors.append("posts が空")
    dup = sorted({s for s in slugs if slugs.count(s) > 1})
    if dup:
        errors.append(f"同じ slug が2回以上ある: {dup}")
    for s in slugs:
        if s not in by_slug or not os.path.isfile(os.path.join(cl.ROOT, s, "index.html")):
            errors.append(f"記事ページが無い slug: {s}（manifest に無いなら先に build_manifest.py）")
    if errors:
        raise SystemExit("popular.json を直してください:\n  " + "\n  ".join(errors))
    return [by_slug[s] for s in slugs]


def thumbnail(post):
    """サムネイルの、リポジトリ直下からのパス。無ければ None。"""
    d = os.path.join(cl.ROOT, WPP_THUMBS)
    prefix = f'{post["post_id"]}-featured-75x75.'
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if name.startswith(prefix) and "@" not in name:
            return f"{WPP_THUMBS}/{name}".replace(os.sep, "/")
    with open(os.path.join(cl.ROOT, post["slug"], "index.html"), encoding="utf-8") as fh:
        m = THUMB_SRC_RE.search(fh.read())
    if m and m.group(1).startswith(sitelib.ORIGIN + "/"):
        rel = m.group(1)[len(sitelib.ORIGIN) + 1:]
        base, ext = os.path.splitext(re.sub(r"-\d+x\d+(?=\.[^.]+$)", "", rel))
        small = f"{base}-150x150{ext}"
        if os.path.isfile(os.path.join(cl.ROOT, small)):
            return small
    return None


def build_widget(posts):
    items = []
    for p in posts:
        href = f'{sitelib.ORIGIN}/{p["slug"]}/'
        title = sitelib.esc_text(html.unescape(p["title"]))
        img = thumbnail(p)
        thumb = (f'<img src="{sitelib.ORIGIN}/{img}" width="75" height="75" alt="" '
                 'class="wpp-thumbnail" decoding="async" loading="lazy">') if img else ""
        items.append(
            "<li>\n"
            f'<a href="{href}">{thumb}<span class="wpp-post-title">{title}</span></a>\n'
            f'<span class="wpp-meta post-stats"><span class="wpp-date">{sitelib.disp_date(p["date"])}</span></span>\n'
            "</li>\n"
        )
    return (
        f'<div id="{WIDGET_ID}" class="popular-posts side-widget"><div class="side-widget-inner">\n'
        f'<h4 class="side-title"><span class="side-title-inner">{TITLE}</span></h4>'
        '<ul class="wpp-list wpp-list-with-thumbnails">\n'
        + "".join(items)
        + "</ul>\n</div></div>"
    )


def apply_widget(text, widget, stats):
    """サイドバーの人気記事を widget にした文字列を返す。"""
    a = text.find(SIDE_START)
    if a < 0:
        return text
    b = text.find(SIDE_END, a)
    if b < 0:
        stats["サイドバーの終端が見つからない"] += 1
        return text
    side = text[a:b]
    start = side.find(f'<div id="{WIDGET_ID}" ')
    if start < 0:
        start = side.find(f'<div id="{OLD_WIDGET_ID}" ')
        if start >= 0:
            end = element_end(side, start)
            heading = f'<span class="side-title-inner">{OLD_TITLE}</span>'
            if end is None or heading not in side[start:end]:
                stats["置き換えなかった（id は一致、中身が想定と違う）"] += 1
                return text
            side = side[:start] + widget + side[end:]
            stats["旧い部品を置き換えた"] += 1
            return text[:a] + side + text[b:]
        at = side.find(ANCHOR)
        end = element_end(side, at) if at >= 0 else None
        if end is None:
            stats["入れる位置が見つからない"] += 1
            return text
        side = side[:end] + "\n" + widget + side[end:]
        stats["入れた"] += 1
        return text[:a] + side + text[b:]
    end = element_end(side, start)
    if end is None:
        stats["部品の終端が見つからない"] += 1
        return text
    if side[start:end] == widget:
        stats["そのまま"] += 1
        return text
    side = side[:start] + widget + side[end:]
    stats["作り直した"] += 1
    return text[:a] + side + text[b:]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに件数だけ表示")
    args = ap.parse_args()

    widget = build_widget(load_posts())
    stats = collections.Counter()
    changed = 0
    for f in cl.tracked_files():
        if not f.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(cl.ROOT, f)
        with open(path, encoding="utf-8", newline="") as fh:
            before = fh.read()
        after = apply_widget(before, widget, stats)
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if any(k not in ("旧い部品を置き換えた", "入れた", "作り直した", "そのまま") for k in stats):
        sys.exit(1)


if __name__ == "__main__":
    main()
