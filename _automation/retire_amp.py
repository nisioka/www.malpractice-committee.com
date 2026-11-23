#!/usr/bin/env python3
"""AMP 版をやめ、AMP の URL を正規ページへ転送するページに置き換える。

WordPress の AMP プラグインが出していた AMP 版（`<slug>/amp/` など）は、静的化のあと
新しい記事では作っておらず、Search Console では「URL が見つかりませんでした（404）」と
「参照している AMP URL は AMP ではありません」が出ていた。AMP には検索順位上の利点が
もう無いので、次のようにして AMP をやめる。

  1. 全ページの `<link rel="amphtml">` を外す（AMP 版を名乗らない）。
  2. AMP 文書（`<html amp>` / `<html ⚡>`）を、正規ページへ転送するだけのページに置き換える。
     転送先は同じ内容の通常ページ（`<x>/amp/` なら `<x>/`）。そのページが無いときは
     AMP 文書自身の `rel="canonical"`。
  3. `rel="amphtml"` が指していたのに実体の無かった `<path>/amp/` にも、同じ転送ページを置く。
     Google はこれらの URL を知っているので、404 のまま残さない。

GitHub Pages ではサーバー側の 301 が使えないので、転送は `rel="canonical"` と即時の
`meta refresh`（Google は恒久的な転送として扱う）で行い、`location.replace` も添える。

`rel="amphtml"` のタグ以外のバイトは変えない。何度実行しても結果は同じ。

  python3 _automation/retire_amp.py --dry-run   # 件数だけ表示
  python3 _automation/retire_amp.py             # 書き換える
"""
import argparse
import collections
import html
import json
import os
import re
import sys
from urllib.parse import unquote

import check_links as cl

ORIGIN = "https://www.malpractice-committee.tech.server-on.net"
AMPHTML = re.compile(r'<link rel="amphtml" href="([^"]*)"\s*/?>')
AMP_DOC = re.compile(r"<html\b[^>]*\s(?:amp|⚡)(?=[\s>=])", re.I)
CANONICAL = re.compile(r'<link rel=["\']canonical["\'] href=["\']([^"\']+)["\']')
TITLE = re.compile(r"<title>(.*?)</title>", re.S)
MARK = "<!-- AMP 版は廃止。正規ページへ転送する（_automation/retire_amp.py が生成） -->"


def redirect_page(url: str, title: str, mark: str = MARK) -> str:
    """url へ転送するだけのページ。title は元ページの <title> の中身（エスケープ済み）。

    mark は生成元を示すコメント（`remove_sns.py` も同じ形の転送ページを作る）。
    """
    attr = html.escape(url, quote=True)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ja">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        f"{mark}\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f'<link rel="canonical" href="{attr}">\n'
        f'<meta http-equiv="refresh" content="0; url={attr}">\n'
        f"<script>location.replace({json.dumps(url)} + location.hash);</script>\n"
        "</head>\n"
        "<body>\n"
        f'<p>このページは移動しました。<a href="{attr}">{title}</a></p>\n'
        "</body>\n"
        "</html>\n"
    )


def page_title(text: str) -> str:
    m = TITLE.search(text)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else "医療ミス調査会"


def amp_canonical(text: str):
    m = CANONICAL.search(text)
    return m.group(1) if m and m.group(1).startswith(ORIGIN + "/") else None


def counterpart_url(f: str):
    """AMP 文書と同じ内容の通常ページの URL（そのページ自身の canonical）。無ければ None。

    `<x>/amp/index.html` は `<x>/`、`<x>/Pamp.html`（`?amp` の写し）は `<x>/` が相手。
    複数ページに分かれた記事の 2 ページ目の AMP 版は canonical が 1 ページ目を指しているので、
    canonical ではなく相手のページへ送る。
    """
    d = os.path.dirname(f)
    if os.path.basename(f) == "index.html" and os.path.basename(d) == "amp":
        d = os.path.dirname(d)
    page = os.path.join(cl.ROOT, d, "index.html")
    if not os.path.isfile(page):
        return None
    with open(page, encoding="utf-8", errors="surrogateescape") as fh:
        url = amp_canonical(fh.read())
    want = f"{ORIGIN}/{d}/" if d else f"{ORIGIN}/"
    return url if url and unquote(url) == want else None


def local_path(url: str):
    """サイト内 URL → リポジトリ内のファイル（ディレクトリなら index.html）。サイト外は None。"""
    if not url.startswith(ORIGIN + "/"):
        return None
    p = unquote(url[len(ORIGIN) + 1:].split("?", 1)[0].split("#", 1)[0])
    if p == "" or p.endswith("/"):
        p += "index.html"
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに件数だけ表示")
    args = ap.parse_args()

    stats = collections.Counter()
    writes = {}      # リポジトリ内パス -> 新しい中身
    missing = {}     # 実体の無い AMP のパス -> (転送先, タイトル)

    for f in cl.tracked_files():
        if not f.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(cl.ROOT, f)
        with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
            text = fh.read()

        if AMP_DOC.search(text[:4096]):
            url = counterpart_url(f) or amp_canonical(text)
            if not url:
                stats["置き換えなかった AMP 文書（転送先が決まらない）"] += 1
                print(f"  SKIP 転送先が決まらない: {f}", file=sys.stderr)
                continue
            new = redirect_page(url, page_title(text))
            if new != text:
                writes[f] = new
                stats["転送ページに置き換えた AMP 文書"] += 1
            continue

        if MARK in text:  # 前回このスクリプトが置いた転送ページ
            continue

        for m in AMPHTML.finditer(text):
            target = local_path(html.unescape(m.group(1)))
            # `?amp` は同じページが返るだけ、`/amp/` で実体が無ければ 404。どちらも外すだけ。
            # `/amp/` で実体が無いものには、正規ページへの転送を置く（Google が知っている URL）。
            if (target and target.endswith("/amp/index.html") and "?" not in m.group(1)
                    and not os.path.exists(os.path.join(cl.ROOT, target))):
                c = CANONICAL.search(text)
                if c and target not in missing:
                    missing[target] = (c.group(1), page_title(text))
        new, n = AMPHTML.subn("", text)
        if n:
            writes[f] = new
            stats["rel=amphtml を外したファイル"] += 1

    for target, (url, title) in sorted(missing.items()):
        if target in writes:
            continue
        writes[target] = redirect_page(url, title)
        stats["実体の無かった AMP の URL に置いた転送ページ"] += 1

    for k, v in sorted(stats.items()):
        print(f"{k}: {v}")
    print(f"書き換え対象ファイル: {len(writes)}")
    if args.dry_run:
        return 0
    for f, content in writes.items():
        path = os.path.join(cl.ROOT, f)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
