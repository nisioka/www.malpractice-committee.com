#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sitemap.xml をルートに全網羅で再生成する（決定論）。

manifest.json（記事・病院カテゴリ）と実在する固定ページ（トップ / page/N /
hospital-info）から生成する。AMP・Pnoamp・Preplytocom 等の重複バリアントは
含めない。実行前に build_manifest.py で manifest を最新化しておくこと。

使い方:
  python3 _automation/build_manifest.py
  python3 _automation/build_sitemap.py
"""
import json
import pathlib

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = pathlib.Path(__file__).resolve().parent / "manifest.json"


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


def main():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = []

    # トップ + ページ送り（欠番はそのまま）
    for n in listing_pages():
        loc = f"{sitelib.ORIGIN}/" if n == 1 else f"{sitelib.ORIGIN}/page/{n}/"
        entries.append(url_entry(loc))

    # 記事（新しい順）
    for p in sorted(m["posts"], key=lambda x: x["post_id"], reverse=True):
        entries.append(url_entry(f"{sitelib.ORIGIN}/{p['slug']}/", p["date"][:10]))

    # 病院カテゴリ
    for slug in sorted(m["categories"]):
        if (ROOT / "category" / slug / "index.html").is_file():
            entries.append(url_entry(f"{sitelib.ORIGIN}/category/{slug}/"))

    # 病院索引
    if (ROOT / "hospital-info" / "index.html").is_file():
        entries.append(url_entry(f"{sitelib.ORIGIN}/hospital-info/"))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(entries)
        + "</urlset>\n"
    )
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"sitemap.xml: {len(entries)} URLs")


if __name__ == "__main__":
    main()
