#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""病院索引（hospital-info）を全網羅で再生成する。

manifest から「記事のある病院カテゴリ」を全て集め、五十音（あ行〜わ行＋その他）で
グルーピングして、各病院→カテゴリページへのリンク＋記事件数＋記事一覧リンクを出力する。
既存 hospital-info/index.html のテーマ定型はそのまま流用し、本文(section.post-content)だけ
差し替える。旧 nisioka.github.io リンクも正規ホストへ是正される。

五十音判定に pykakasi を使う（未導入なら pip 導入を促し「その他」に集約）。
"""
import html as htmllib
import json
import pathlib
import re
import sys

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "hospital-info" / "index.html"
MANIFEST = ROOT / "_automation" / "manifest.json"

# 病院ではないトピック/組織カテゴリ（索引から除外）
NON_HOSPITAL = {"others", "mhlw", "medical-accident-investigation-system",
                "jcqhc", "notice", "case-study-introduction"}

ROWS = [
    ("あ行", "あいうえおぁぃぅぇぉ"),
    ("か行", "かきくけこがぎぐげご"),
    ("さ行", "さしすせそざじずぜぞ"),
    ("た行", "たちつてとだぢづでどっ"),
    ("な行", "なにぬねの"),
    ("は行", "はひふへほばびぶべぼぱぴぷぺぽ"),
    ("ま行", "まみむめも"),
    ("や行", "やゆよゃゅょ"),
    ("ら行", "らりるれろ"),
    ("わ行", "わをん"),
]
CHAR_TO_ROW = {c: name for name, chars in ROWS for c in chars}


def get_reading():
    try:
        import pykakasi
        kks = pykakasi.kakasi()

        def yomi(name):
            return "".join(r["hira"] for r in kks.convert(name))
        return yomi
    except Exception:
        return None


def row_of(reading: str) -> str:
    for ch in reading:
        if ch in CHAR_TO_ROW:
            return CHAR_TO_ROW[ch]
    return "その他"


def esc(s):
    return htmllib.escape(s, quote=False)


def build_content(manifest, yomi) -> str:
    cats = manifest["categories"]
    posts = manifest["posts"]
    by_cat = {}
    for p in posts:
        by_cat.setdefault(p["category_slug"], []).append(p)

    # 病院エントリを構築
    entries = []
    for slug, plist in by_cat.items():
        if slug in NON_HOSPITAL or not slug:
            continue
        name = cats.get(slug, slug)
        reading = yomi(name) if yomi else ""
        entries.append({
            "slug": slug, "name": name, "reading": reading,
            "row": row_of(reading) if yomi else "その他",
            "posts": sorted(plist, key=lambda x: x["post_id"], reverse=True),
        })

    # 行ごとにまとめ、読み順にソート
    order = [r[0] for r in ROWS] + ["その他"]
    grouped = {r: [] for r in order}
    for e in entries:
        grouped[e["row"]].append(e)
    for r in grouped:
        grouped[r].sort(key=lambda e: (e["reading"] or e["slug"], e["slug"]))

    total_h = len(entries)
    total_a = sum(len(e["posts"]) for e in entries)
    out = [f'      \n      \n<p>医療ミス・医療過誤・医療事故を報じた病院の索引です。'
           f'全{total_h}病院・{total_a}記事を五十音順にまとめています。'
           f'病院名をクリックすると、その病院の記事一覧が開きます。</p>\n']
    for row in order:
        if not grouped[row]:
            continue
        out.append(f"<h2>{row}</h2>\n<ul>\n")
        for e in grouped[row]:
            cat_url = f"{sitelib.ORIGIN}/category/{e['slug']}/"
            out.append(f'<li><a href="{cat_url}">{esc(e["name"])}</a>（{len(e["posts"])}件）\n<ul>\n')
            for p in e["posts"]:
                art_url = f"{sitelib.ORIGIN}/{p['slug']}/"
                out.append(f'<li><a href="{art_url}">{esc(p["title"])}</a></li>\n')
            out.append("</ul>\n</li>\n")
        out.append("</ul>\n")
    return "".join(out)


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    yomi = get_reading()
    if yomi is None:
        print("注意: pykakasi 未導入のため五十音分類できません。"
              "`pip install pykakasi` を推奨（全病院を『その他』に集約します）。")

    content = build_content(manifest, yomi)
    html = PAGE.read_text(encoding="utf-8")
    new_html, n = re.subn(
        r'(<section class="post-content" itemprop="text">).*?(</section>)',
        lambda m: m.group(1) + "\n" + content + "      " + m.group(2),
        html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("section.post-content が見つからない")
    PAGE.write_text(new_html, encoding="utf-8")
    print(f"再生成: hospital-info/index.html")


if __name__ == "__main__":
    sys.exit(main())
