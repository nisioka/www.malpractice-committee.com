#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""既存の全記事を走査して manifest.json を生成する。

manifest.json = {
  "categories": { "<slug>": "<日本語病院名>", ... },   # wp-json 由来
  "posts": [ {post_id, slug, date, category_slug, title}, ... ]  # 新しい順
}

これが重複判定・一覧再生成・病院索引生成の唯一の情報源になる。
記事本文の走査は実ファイル（<slug>/index.html）を正とする（wp-json は不完全なため）。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_automation" / "manifest.json"

# 記事ではないトップレベルディレクトリ（走査から除外）
NON_ARTICLE = {
    "page", "category", "wp-content", "wp-includes", "wp-json", "_automation",
    "author", "movie", "twitter-introduce", ".git", ".github",
}


def load_categories() -> dict:
    """slug -> 日本語名 を作る。

    第一ソース: category/<slug>/index.html の <title>（利用者が実際に見る名称・最も正確）
    補完ソース: wp-json/wp/v2/categories/*（カテゴリページが無い場合）
    """
    cats = {}
    # 補完: wp-json
    cdir = ROOT / "wp-json" / "wp" / "v2" / "categories"
    if cdir.is_dir():
        for f in cdir.iterdir():
            if f.is_file():
                try:
                    obj = json.loads(f.read_text(encoding="utf-8"))
                    if obj.get("slug"):
                        cats[obj["slug"]] = obj.get("name", obj["slug"])
                except (ValueError, OSError):
                    continue
    # 第一ソース: カテゴリページの <title>（上書き優先）
    catroot = ROOT / "category"
    if catroot.is_dir():
        for d in catroot.iterdir():
            page = d / "index.html"
            if page.is_file():
                try:
                    html = page.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                m = re.search(r"<title>(.*?)\s*\|\s*", html, re.S)
                if m:
                    cats[d.name] = m.group(1).strip()
    return cats


def parse_article(html: str):
    """記事HTMLから post_id / date / category_slug / title を抽出。記事でなければ None。"""
    # 本文が単一記事（single-post）でなければ記事ページではない
    if "single-post" not in html:
        return None
    m_id = re.search(r'<article id="post-(\d+)"', html)
    if not m_id:
        return None
    post_id = int(m_id.group(1))
    m_cat = re.search(r'category-([a-z0-9\-]+)"', html)
    category_slug = m_cat.group(1) if m_cat else ""
    m_date = re.search(r'class="date updated"[^>]*datetime="([^"]+)"', html)
    date = m_date.group(1) if m_date else ""
    m_title = re.search(r'<h1 class="post-title"[^>]*>(.*?)</h1>', html, re.S)
    title = re.sub(r"<[^>]+>", "", m_title.group(1)).strip() if m_title else ""
    # フッタのカテゴリリンクから slug と日本語表示名を取得（最も確実な per-post ソース）
    m_catlink = re.search(
        r'<a href="[^"]*/category/([a-z0-9\-]+)/" rel="category tag">(.*?)</a>', html, re.S)
    if m_catlink:
        category_slug = m_catlink.group(1)
        category_name = re.sub(r"<[^>]+>", "", m_catlink.group(2)).strip()
    else:
        category_name = ""
    return {"post_id": post_id, "category_slug": category_slug, "date": date,
            "title": title, "category_name": category_name}


def main():
    categories = load_categories()
    posts = []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name in NON_ARTICLE or d.name.startswith("."):
            continue
        index = d / "index.html"
        if not index.is_file():
            continue
        try:
            html = index.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        info = parse_article(html)
        if info is None:
            continue
        info["slug"] = d.name
        posts.append(info)
        # カテゴリ名の欠けを記事フッタ由来で補完
        cs, cn = info.get("category_slug"), info.get("category_name")
        if cs and cn and cs not in categories:
            categories[cs] = cn

    # 新しい順（post_id 降順 = 概ね日付降順）
    posts.sort(key=lambda p: p["post_id"], reverse=True)
    # category_name は補完に使ったので posts からは落としてスリム化
    for p in posts:
        p.pop("category_name", None)

    manifest = {"categories": categories, "posts": posts}
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"posts: {len(posts)}  categories: {len(categories)}")
    print(f"max post_id: {posts[0]['post_id'] if posts else 'N/A'}")
    # カテゴリ名が取れない記事を警告
    missing = sorted({p["category_slug"] for p in posts
                      if p["category_slug"] and p["category_slug"] not in categories})
    if missing:
        print(f"WARN wp-json に病院名が無いカテゴリ({len(missing)}): {missing[:10]}")


if __name__ == "__main__":
    main()
