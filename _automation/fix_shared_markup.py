#!/usr/bin/env python3
"""全ページに共通する定型ブロックの不具合を、生成側と同じ形に直す。

週次更新のレビューで繰り返し指摘され、定型部分なので週次の PR では直せなかったもの。
生成側（`sitelib.py`・`build_category.py`・`build_search.py`・`templates/post_share.html`）
は同じ形に直してあり、このスクリプトは既存ページをそれに揃える。

  規則1: <body> の属性 `itemschope` の綴りを `itemscope` に直す。
  規則2: JSON-LD のパンくずの先頭 "家"（Home の機械翻訳）を、画面のパンくずと同じ
          "ホーム" にする。
  規則3: 記事末の「SNSでもご購読できます。」欄に2つ目の `<div id="fb-root">` があり、
          id が重複している。<body> 直後の1つを残して、この欄のものを外す。
  規則4: 共有欄の Twitter / Facebook ボタンが `<記事URL>?share=twitter` を指している。
          WordPress が共有画面へ転送していた形で、静的配信では記事が開き直すだけなので、
          各サービスの共有画面を直接指す（`sitelib.share_hrefs`）。ツイートの文面には、
          そのボタンを含む記事の見出しを使う。
  規則5: 一覧カードのアイキャッチは画像だけのリンクで、alt が空のためリンクに名前が無い。
          alt にそのカードの見出しを入れる。

対象は Git が追跡している全 HTML。該当箇所以外のバイトは変えない。何度実行しても結果は同じ。

  python3 _automation/fix_shared_markup.py --dry-run   # 件数だけ表示
  python3 _automation/fix_shared_markup.py             # 書き換える
"""
import argparse
import bisect
import collections
import html
import os
import re
import sys
import urllib.parse

import json

import check_links as cl
import sitelib

HOME = f'"item":"{sitelib.ORIGIN}/"'
HOME_SP = f'"item": "{sitelib.ORIGIN}/"'
FB_ROOT = '<div id="fb-root"></div>'
FB_DUP = 'MalpracticeCommittee">facebook</a></h3>\t\t' + FB_ROOT

ARTICLE_RE = re.compile(r'<article id="post-\d+"')
HEADLINE_RE = re.compile(
    r'<h1 class="post-title" itemprop="headline">(.*?)</h1>'
    r'|<h2 class="post-title" itemprop="headline"><a href="([^"]*)">(.*?)</a></h2>', re.S)
SHARE_RE = re.compile(r'href="([^"?]+)\?share=(twitter|facebook)"')
THUMB_RE = re.compile(
    r'(<div class="post-thumbnail">\s*<a href="[^"]*" rel="nofollow"><img [^>]*?\balt=")(")')
TAG_RE = re.compile(r"<[^>]+>")

with open(os.path.join(cl.ROOT, "_automation", "manifest.json"), encoding="utf-8") as _fh:
    # カテゴリページの説明欄の共有バーは記事カードの外にあるので、見出しを manifest から引く
    TITLES = {f"{sitelib.ORIGIN}/{p['slug']}/": p["title"] for p in json.load(_fh)["posts"]}


def headline_at(text, pos, starts, url=None):
    """pos を含む記事カード（直前の <article id="post-N">）の見出し。無ければ空文字。

    一覧カードの見出しはリンクなので、url を渡したときはリンク先が一致するものだけを使う。
    """
    i = bisect.bisect_right(starts, pos) - 1
    if i < 0:
        return ""
    m = HEADLINE_RE.search(text, starts[i], pos)
    if not m:
        return ""
    if m.group(2) is not None and url is not None and m.group(2) != url:
        return ""
    return html.unescape(TAG_RE.sub("", m.group(1) or m.group(3))).strip()


def headline_for(text, url):
    """ページ内で url へリンクしている一覧カードの見出し。無ければ空文字。"""
    for m in HEADLINE_RE.finditer(text):
        if m.group(2) == url:
            return html.unescape(TAG_RE.sub("", m.group(3))).strip()
    return ""


def fix(text, stats):
    n = text.count('itemschope="itemscope"')
    if n:
        text = text.replace('itemschope="itemscope"', 'itemscope="itemscope"')
        stats["規則1 itemscope"] += n

    for old, new in ((f'"name":"家",{HOME}', f'"name":"ホーム",{HOME}'),
                     (f'"name": "家", {HOME_SP}', f'"name": "ホーム", {HOME_SP}')):
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            stats["規則2 JSON-LD パンくず"] += n

    dup = text.count(FB_DUP)
    if dup and text.count(FB_ROOT) > dup:
        text = text.replace(FB_DUP, FB_DUP[:-len(FB_ROOT)].rstrip("\t"))
        stats["規則3 fb-root の重複"] += dup
    elif dup:
        stats["規則3 外さなかった（<body> 直後の fb-root が無い）"] += dup

    starts = [m.start() for m in ARTICLE_RE.finditer(text)]

    def share(m):
        url = urllib.parse.unquote(html.unescape(m.group(1)))
        title = (headline_at(text, m.start(), starts, m.group(1))
                 or TITLES.get(m.group(1), "") or headline_for(text, m.group(1)))
        if not title:
            stats["規則4 見出しが見つからずURLだけ渡した"] += 1
        tw, fb = sitelib.share_hrefs(url, title)
        stats[f"規則4 共有リンク {m.group(2)}"] += 1
        return f'href="{tw if m.group(2) == "twitter" else fb}"'

    text = SHARE_RE.sub(share, text)

    def thumb(m):
        href = re.search(r'<a href="([^"]*)"', m.group(1)).group(1)
        title = headline_at(text, m.start(), starts, href)
        if not title:
            stats["規則5 見出しが見つからず alt を空のまま残した"] += 1
            return m.group(0)
        stats["規則5 一覧カードの画像リンク alt"] += 1
        return m.group(1) + sitelib.esc_attr(title) + m.group(2)

    # 規則4 で文字列の長さが変わったので、記事の開始位置を取り直す
    starts = [m.start() for m in ARTICLE_RE.finditer(text)]
    text = THUMB_RE.sub(thumb, text)
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
    if any("外さなかった" in k or "見つからず" in k for k in stats):
        sys.exit(1)


if __name__ == "__main__":
    main()
