#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""構造化JSONから記事ページ（PC版 index.html）を生成する。

使い方:
    python3 _automation/generate_article.py <input.json>

入力JSON（1件 or 配列）:
{
  "slug": "example-slug",            # URL・ディレクトリ名（英小文字/ハイフン）
  "title": "記事タイトル",
  "date": "2026-07-11T10:00:00+09:00",
  "hospital_name": "○○病院",         # カテゴリ日本語名
  "category_slug": "example-hosp",   # カテゴリslug（既存病院なら既存slugを流用）
  "description": "meta用の短い要約",
  "keywords": "○○病院",             # 省略時は hospital_name
  "body_html": "<p>本文段落…</p>",   # 出典行は含めない（source_* から自動付与）
  "source_name": "朝日新聞",
  "source_url": "https://...",
  "post_id": 1071,                    # 省略時は manifest 最大+1 を自動採番
  "image": {"url": "...", "width": 285, "height": 214}  # 任意。無ければ画像なし
}

このスクリプトは記事ページのみを書き出す。トップ/ページ送り/カテゴリ/病院索引の
更新は rebuild_listings.py・build_hospital_index.py が担当する。
"""
import json
import pathlib
import sys

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "_automation" / "manifest.json"


def load_manifest():
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"categories": {}, "posts": []}


def next_post_id(manifest):
    ids = [p["post_id"] for p in manifest.get("posts", [])]
    return (max(ids) + 1) if ids else 1


def normalize(article, manifest, used_ids):
    a = dict(article)
    a.setdefault("keywords", a["hospital_name"])
    a.setdefault("modified", a["date"])
    if "post_id" not in a:
        pid = next_post_id(manifest)
        while pid in used_ids:
            pid += 1
        a["post_id"] = pid
    used_ids.add(a["post_id"])
    return a


def write_article(a):
    out_dir = ROOT / a["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    html = sitelib.assemble_article_page(a)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return out_dir / "index.html"


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 1
    data = json.loads(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
    articles = data if isinstance(data, list) else [data]
    manifest = load_manifest()
    known_cats = manifest.get("categories", {})
    used_ids = set()

    enriched = []
    for art in articles:
        a = normalize(art, manifest, used_ids)
        enriched.append(a)
        path = write_article(a)
        new_cat = a["category_slug"] not in known_cats
        flag = "  [新カテゴリ]" if new_cat else ""
        print(f"生成: {path.relative_to(ROOT)}  post_id={a['post_id']}  "
              f"category={a['category_slug']}{flag}")
        if new_cat:
            print(f"      ↳ 新病院 '{a['hospital_name']}' → カテゴリページ "
                  f"category/{a['category_slug']}/ の作成が必要（rebuild時に対応）")

    # 採番済みデータを後続工程（rebuild_listings / category生成）に引き継ぐ
    gen_out = ROOT / "_automation" / "_generated.json"
    gen_out.write_text(json.dumps(enriched, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"引き継ぎデータ: {gen_out.relative_to(ROOT)}（{len(enriched)}件）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
