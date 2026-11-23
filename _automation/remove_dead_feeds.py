#!/usr/bin/env python3
"""実体の無いフィードへのリンクを外す。

WordPress は記事ごとのコメントフィード（`/<slug>/feed/`）とカテゴリのフィード
（`/category/<slug>/feed/`）を `<head>` の `<link rel="alternate">` で知らせ、ヘッダーの
RSS アイコンと記事下の「Feedly でフォローする」でサイトのフィード（`/feed/`）の購読を
勧めていた。静的化でフィードは取り込まれていないので、どれも 404 のフィードを指す。

外すのは次の2つで、どちらもフィードの URL がこのサイトの中を指し、その先がリポジトリに
無いものだけ。フィードを置いた URL を指すものは残す。ほかのバイトは変えない。何度実行しても
結果は同じ。

- `<head>` の `<link rel="alternate">` のうち type が RSS / Atom / JSON Feed のもの。タグの行ごと外す
- Feedly の購読画面（`cloud.feedly.com/#subscription/feed/<フィードのURL>`）へのリンクを持つ
  `<li>`。ヘッダーのアイコンの並びと、記事下の「SNSでもご購読できます。」の欄にある。
  `<li>` が1行を占めていれば行ごと外す

対象は全 HTML と `_automation/templates/`（`header_nav.html`・`post_share.html`）。
WordPress 時代の HTML を取り込み直したときは、このスクリプトを掛け直す。

  python3 _automation/remove_dead_feeds.py --dry-run   # 件数だけ表示
  python3 _automation/remove_dead_feeds.py             # 書き換える
"""
import argparse
import collections
import os
import re
import urllib.parse

import check_links as cl

FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/feed+json")
# 行頭の字下げから行末の改行まで、タグ1つだけの行
LINK_LINE = re.compile(r"^[ \t]*(<link\b[^>]*>)[ \t]*(?:\r?\n|$)", re.M | re.I)
ATTR = re.compile(r"""([a-zA-Z:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
# Feedly の購読リンクを1つだけ持つ <li>。前後の字下げと改行も捕まえ、行を占めるときは行ごと外す。
FEEDLY_LI = re.compile(
    r"(^[ \t]*)?<li\b[^>]*>\s*<a\b[^>]*\bhref=[\"']https?://cloud\.feedly\.com/#subscription"
    r"(?:%2F|/)feed(?:%2F|/)([^\"'#]+)[\"'][^>]*>(?:(?!</li>).)*?</li>([ \t]*\r?\n)?",
    re.S | re.M | re.I)


def attrs(tag):
    return {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTR.finditer(tag)}


def is_dead(url, path, site, stats, label):
    """url がサイトの中の、実体の無いフィードか。残すときは理由を数える。"""
    kind, target = cl.classify(url, path, None)
    if kind != "internal":
        stats[f"残した {label}（サイトの外を指す）"] += 1
        return False
    if site.exists(target):
        stats[f"残した {label}（フィードがある）"] += 1
        return False
    return True


def strip_feedly(text, path, site, stats):
    out, pos = [], 0
    for m in FEEDLY_LI.finditer(text):
        if not is_dead(urllib.parse.unquote(m.group(2)), path, site, stats, "Feedly"):
            continue
        # 行を占める <li> は行ごと、行の途中のものは <li> だけ外す
        whole_line = m.group(1) is not None and m.group(3) is not None
        start = m.start() if whole_line else m.start() + len(m.group(1) or "")
        end = m.end() if whole_line else m.end() - len(m.group(3) or "")
        out.append(text[pos:start])
        pos = end
        stats["外した Feedly"] += 1
    if not out:
        return text
    out.append(text[pos:])
    return "".join(out)


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
        if not is_dead(a.get("href", ""), path, site, stats, "rel=alternate"):
            continue
        out.append(head[pos:m.start()])
        pos = m.end()
        stats["外した rel=alternate"] += 1
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
        after = strip_feedly(strip_feeds(before, f, site, stats), f, site, stats)
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
