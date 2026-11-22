#!/usr/bin/env python3
"""`<head>` から、実体の無いフィードを指す `<link rel="alternate">` を外す。

WordPress は記事ごとのコメントフィード（`/<slug>/feed/`）とカテゴリのフィード
（`/category/<slug>/feed/`）を `<head>` で知らせていた。静的化でフィードは取り込まれて
いないので、どれも 404 になる。

外すのは、type が RSS / Atom / JSON Feed で、href がこのサイトの中を指し、その先が
リポジトリに無いものだけ。フィードを置いた URL を指すものは残す。タグの行ごと外し、
ほかのバイトは変えない。何度実行しても結果は同じ。

生成側（`_automation/templates/`・`sitelib.py`）はフィードのリンクを出さない。WordPress
時代の HTML を取り込み直したときは、このスクリプトを掛け直す。

  python3 _automation/remove_dead_feeds.py --dry-run   # 件数だけ表示
  python3 _automation/remove_dead_feeds.py             # 書き換える
"""
import argparse
import collections
import os
import re

import check_links as cl

FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/feed+json")
# 行頭の字下げから行末の改行まで、タグ1つだけの行
LINK_LINE = re.compile(r"^[ \t]*(<link\b[^>]*>)[ \t]*(?:\r?\n|$)", re.M | re.I)
ATTR = re.compile(r"""([a-zA-Z:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def attrs(tag):
    return {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTR.finditer(tag)}


def strip_feeds(text, path, site, stats):
    end = text.lower().find("</head>")
    if end < 0:
        return text
    head = text[:end]
    out, pos = [], 0
    for m in LINK_LINE.finditer(head):
        a = attrs(m.group(1))
        if a.get("rel", "").lower() != "alternate" or a.get("type", "").lower() not in FEED_TYPES:
            continue
        kind, target = cl.classify(a.get("href", ""), path, None)
        if kind != "internal":
            stats["残した（サイトの外を指す）"] += 1
            continue
        if site.exists(target):
            stats["残した（フィードがある）"] += 1
            continue
        out.append(head[pos:m.start()])
        pos = m.end()
        stats["外した"] += 1
    if not out:
        return text
    out.append(head[pos:])
    return "".join(out) + text[end:]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに件数だけ表示")
    args = ap.parse_args()

    files = cl.tracked_files()
    site = cl.Site(files)
    stats = collections.Counter()
    changed = 0
    for f in files:
        if not f.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(cl.ROOT, f)
        with open(path, encoding="utf-8", newline="") as fh:
            before = fh.read()
        after = strip_feeds(before, f, site, stats)
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
