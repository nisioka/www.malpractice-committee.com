#!/usr/bin/env python3
"""壊れたサイト内参照のうち、機械的に直せるものを一括で直す。

  規則1: img / source の srcset から、実体の無い候補を落とす。
          残りが src と同じ1件だけになったら srcset 属性ごと削除する。
  規則2: a href が /<親>/<slug> の形で 404 になり、/<slug>/ が実在するとき、
          /<slug>/ へ書き換える。

対象は全 HTML と `_automation/` の生成スクリプト・テンプレート。該当箇所以外の
バイトは変えない。何度実行しても結果は同じ。

  python3 _automation/fix_refs.py --dry-run   # 件数だけ表示
  python3 _automation/fix_refs.py             # 書き換える
"""
import argparse
import collections
import html
import os
import re

import check_links as cl

SITE = "https://www.malpractice-committee.tech.server-on.net"
TAG = re.compile(r"<(?:img|source)\b[^>]*>", re.I)
SRCSET = re.compile(r'(\s+)srcset="([^"]*)"')
SRC = re.compile(r'\ssrc="([^"]*)"')
HREF = re.compile(r'(<a\b[^>]*?\shref=")' + re.escape(SITE) + r'/([^"/?#]+)/([^"/?#]+)(")', re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに件数だけ表示")
    args = ap.parse_args()

    files = cl.tracked_files()
    site = cl.Site(files)
    stats = collections.Counter()

    def fix_srcset(m, f):
        tag = m.group(0)
        sm = SRCSET.search(tag)
        if not sm:
            return tag
        keep, dropped = [], 0
        for cand in (c.strip() for c in sm.group(2).split(",")):
            if not cand:
                continue
            where, val = cl.classify(html.unescape(cand.split()[0]), f, None)
            # 外部と画像 CDN 経由は実体を確かめられないので触らない
            if where == "internal" and not site.exists(cl.unquote(val)):
                dropped += 1
            else:
                keep.append(cand)
        if not dropped:
            return tag
        stats["srcset から落とした候補"] += dropped
        src = SRC.search(tag)
        only_src = (len(keep) == 1 and src and keep[0].split()[0] == src.group(1)
                    and keep[0].split()[1:] in ([], ["1x"]))
        if not keep or only_src:
            stats["srcset 属性ごと削除した img"] += 1
            return tag[:sm.start()] + tag[sm.end():]
        stats["候補だけ落とした img"] += 1
        return (tag[:sm.start()] + sm.group(1) + 'srcset="' + ", ".join(keep) + '"'
                + tag[sm.end():])

    def fix_href(m):
        parent, slug = m.group(2), m.group(3)
        if "." in slug or site.exists("/" + cl.unquote(parent) + "/" + cl.unquote(slug)):
            return m.group(0)
        if not site.exists("/" + cl.unquote(slug) + "/"):
            return m.group(0)
        stats["書き換えた href"] += 1
        return m.group(1) + SITE + "/" + slug + "/" + m.group(4)

    changed = 0
    for f in files:
        is_page = f.lower().endswith((".html", ".htm"))
        is_generator = (f.startswith("_automation/") and f.endswith(".py")
                        and os.path.basename(f) not in ("check_links.py", "fix_refs.py"))
        if not (is_page or is_generator):
            continue
        path = os.path.join(cl.ROOT, f)
        with open(path, encoding="utf-8", newline="") as fh:
            before = fh.read()
        after = TAG.sub(lambda m: fix_srcset(m, f), before)
        after = HREF.sub(fix_href, after)
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
