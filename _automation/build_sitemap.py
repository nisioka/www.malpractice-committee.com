#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sitemap.xml をルートに全網羅で再生成する（決定論）。

manifest.json（記事・病院カテゴリ）と実在する固定ページ（トップ / page/N /
hospital-info / manifest に載らない記事・固定ページ）から生成する。AMP・Pnoamp・
Preplytocom 等の重複バリアントは含めない。

載せるのは、検索結果に出してよいページだけ。ページの HTML を読み、次のどちらかに
当たるものは落とす（落とした件数は種類ごとに表示する）。

  - `<meta name="robots">` に noindex がある（page/N のページ送りなど）
  - `rel="canonical"` が無い、または自分以外を指している

`<loc>` にはページ自身の canonical をそのまま使う（日本語の slug も canonical と同じ
パーセントエンコードになる）。実行前に build_manifest.py で manifest を最新化しておくこと。

使い方:
  python3 _automation/build_manifest.py
  python3 _automation/build_sitemap.py
"""
import collections
import json
import pathlib
import re
from urllib.parse import unquote

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = pathlib.Path(__file__).resolve().parent / "manifest.json"

# トップ直下で、記事・固定ページではないディレクトリ（manifest 外のページを探すときに除く）
NOT_PAGES = {"page", "category", "hospital-info", "_automation", "docs", "scripts",
             "node_modules", "wp-content", "wp-includes", "wp-json"}
ROBOTS_RE = re.compile(r'<meta name=["\']robots["\'] content=["\']([^"\']*)["\']', re.I)
CANONICAL_RE = re.compile(r'<link rel=["\']canonical["\'] href=["\']([^"\']+)["\']')


def url_entry(loc: str, lastmod: str = "") -> str:
    lm = f"\n    <lastmod>{lastmod}</lastmod>" if lastmod else ""
    return f"  <url>\n    <loc>{loc}</loc>{lm}\n  </url>\n"


def listing_pages():
    nums = [1]
    page_dir = ROOT / "page"
    if page_dir.is_dir():
        for d in page_dir.iterdir():
            if d.is_dir() and d.name.isdigit() and (d / "index.html").is_file():
                nums.append(int(d.name))
    return sorted(set(nums))


def sitemap_loc(rel: str, skipped: collections.Counter):
    """rel（ROOT からのディレクトリ。トップは ""）のページを載せるなら loc、載せないなら None。"""
    page = ROOT / rel / "index.html"
    if not page.is_file():
        skipped["ページが無い"] += 1
        return None
    html = page.read_text(encoding="utf-8", errors="replace")
    if any("noindex" in r.lower() for r in ROBOTS_RE.findall(html)):
        skipped["noindex"] += 1
        return None
    own = f"{sitelib.ORIGIN}/{rel}/" if rel else f"{sitelib.ORIGIN}/"
    m = CANONICAL_RE.search(html)
    if not m or unquote(m.group(1)) != unquote(own):
        skipped["canonical が自分以外"] += 1
        return None
    return m.group(1)


def main():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = []
    skipped = collections.Counter()

    def add(rel: str, lastmod: str = ""):
        loc = sitemap_loc(rel, skipped)
        if loc:
            entries.append(url_entry(loc, lastmod))

    # トップ + ページ送り（欠番はそのまま）
    for n in listing_pages():
        add("" if n == 1 else f"page/{n}")

    # 記事（新しい順）
    for p in sorted(m["posts"], key=lambda x: x["post_id"], reverse=True):
        add(p["slug"], p["date"][:10])

    # 病院カテゴリ
    for slug in sorted(m["categories"]):
        if (ROOT / "category" / slug / "index.html").is_file():
            add(f"category/{slug}")

    # 病院索引
    if (ROOT / "hospital-info" / "index.html").is_file():
        add("hospital-info")

    # manifest に載らない記事・固定ページ（movie / twitter-introduce / kifmec など）
    posts = {p["slug"] for p in m["posts"]}
    for d in sorted(ROOT.iterdir(), key=lambda x: x.name):
        if (d.is_dir() and not d.name.startswith(".") and d.name not in NOT_PAGES
                and d.name not in posts and (d / "index.html").is_file()):
            add(d.name)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(entries)
        + "</urlset>\n"
    )
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"sitemap.xml: {len(entries)} URLs")
    for k, v in sorted(skipped.items()):
        print(f"  載せなかった（{k}）: {v}")


if __name__ == "__main__":
    main()
