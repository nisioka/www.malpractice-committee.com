#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""カテゴリ（病院）ページを生成・再生成する。

- 新病院: category/<slug>/index.html を新規作成（記事リンク一覧付き）。
- 既存病院に新記事: そのカテゴリページを再生成して新記事を先頭に反映。

テーマ定型（head_assets/header_nav/sidebar/footer）は記事ページと共通の検証済みパーツを流用。
記事一覧は日付＋タイトルリンクのシンプルな形式で全記事を新しい順に並べる。

使い方:
  python3 _automation/build_category.py <slug> [<slug> ...]
  （slug 省略時は _automation/_generated.json のカテゴリを対象）
"""
import json
import pathlib
import sys

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "_automation" / "manifest.json"


def cat_head(slug, name):
    url = f"{sitelib.ORIGIN}/category/{slug}/"
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "@id": f"{url}#collectionpage", "url": url,
             "name": f"{name} | {sitelib.SITE_NAME}", "inLanguage": "ja",
             "isPartOf": {"@id": f"{sitelib.ORIGIN}/#website"}},
            {"@type": "WebSite", "@id": f"{sitelib.ORIGIN}/#website", "url": f"{sitelib.ORIGIN}/",
             "name": sitelib.SITE_NAME, "inLanguage": "ja"},
        ],
    }
    return (
        "\t\t<!-- All in One SEO 4.6.1.1 - aioseo.com -->\n"
        f"\t\t<title>{sitelib.esc_text(name)} | {sitelib.SITE_NAME}</title>\n"
        '\t\t<meta name="robots" content="max-snippet:-1, max-image-preview:large, max-video-preview:-1" />\n'
        f'\t\t<meta name="google-site-verification" content="{sitelib.GSV}" />\n'
        f'\t\t<link rel="canonical" href="{url}" />\n'
        '\t\t<meta name="generator" content="All in One SEO (AIOSEO) 4.6.1.1" />\n'
        '\t\t<meta name="google" content="nositelinkssearchbox" />\n'
        '\t\t<script type="application/ld+json" class="aioseo-schema">\n'
        f"\t\t\t{json.dumps(jsonld, ensure_ascii=False)}\n"
        "\t\t</script>\n\t\t<!-- All in One SEO -->\n\n"
        '<meta name="keywords" content="" />\n<meta name="description" content="" />\n'
        '<meta name="robots" content="index" />\n'
        '<meta property="fb:admins" content="197947167205693" />\n'
        '<meta property="fb:app_id" content="764065833702089" />\n'
        f'<meta property="og:title" content="{sitelib.esc_attr(name)}" />\n'
        '<meta property="og:type" content="article" />\n'
        f'<meta property="og:url" content="{url}" />\n'
        '<meta property="og:locale" content="ja_JP" />\n'
        f'<meta property="og:site_name" content="{sitelib.SITE_NAME}" />\n'
        '<meta content="summary" name="twitter:card" />\n'
        '<meta content="MediMalpComm" name="twitter:site" />\n'
    )


def cat_article_item(p):
    return (f'        <article id="post-{p["post_id"]}" class="post-{p["post_id"]} post type-post '
            f'status-publish format-standard hentry category-{p["category_slug"]}" '
            'itemscope="itemscope" itemtype="http://schema.org/BlogPosting">\n'
            '      <header class="post-header">\n        <ul class="post-meta list-inline">\n'
            f'          <li class="date updated" itemprop="datePublished" datetime="{p["date"]}">'
            f'<i class="fa fa-clock-o"></i> {sitelib.disp_date(p["date"])}</li>\n        </ul>\n'
            f'        <h2 class="post-title" itemprop="headline"><a href="{sitelib.ORIGIN}/{p["slug"]}/">'
            f'{sitelib.esc_text(p["title"])}</a></h2>\n      </header>\n    </article>')


def build_category_page(slug, name, posts):
    posts = sorted(posts, key=lambda x: x["post_id"], reverse=True)
    pid = posts[0]["post_id"] if posts else 0
    head = cat_head(slug, name)
    head_assets = sitelib.fill_tokens(sitelib.partial("head_assets.html"), pid, slug).rstrip("\n")
    header_nav = sitelib.partial("header_nav.html").rstrip("\n")
    sidebar = sitelib.partial("sidebar.html").rstrip("\n")
    footer = sitelib.fill_tokens(sitelib.partial("footer.html"), pid, slug).rstrip("\n")
    items = "\n\n".join(cat_article_item(p) for p in posts)
    breadcrumb = (
        '<ol class="breadcrumb clearfix"><li itemscope="itemscope" itemtype="http://data-vocabulary.org/Breadcrumb">'
        f'<a href="{sitelib.ORIGIN}" itemprop="url"><i class="fa fa-home"></i> '
        '<span itemprop="title">ホーム</span></a> / </li>'
        f'<li><i class="fa fa-folder"></i> {sitelib.esc_text(name)}</li></ol>'
    )
    body_class = f"archive category category-{slug} left-content default"
    return f"""{sitelib.HEAD_OPEN}{head}{head_assets}
{sitelib.ADSENSE_HEAD}</head>

<body id="#top" class="{body_class}" itemschope="itemscope" itemtype="http://schema.org/WebPage">

  {header_nav}


<div id="content">

<div class="wrap">
    {breadcrumb}
  <div id="main" class="col-md-8">

    <div class="main-inner">

    <section class="cat-content">
      <header class="cat-header">
        <h1 class="post-title">{sitelib.esc_text(name)}</h1>
      </header>
      <div class="cat-content-area">
{items}
      </div>
    </section>

    </div><!-- /main-inner -->
  </div><!-- /main -->

  {sidebar}

</div><!-- /wrap -->


</div><!-- /content -->

{footer}
"""


def main(argv):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cats = manifest["categories"]
    by_cat = {}
    for p in manifest["posts"]:
        by_cat.setdefault(p["category_slug"], []).append(p)

    slugs = argv[1:]
    if not slugs:
        gen = ROOT / "_automation" / "_generated.json"
        if gen.is_file():
            data = json.loads(gen.read_text(encoding="utf-8"))
            slugs = sorted({a["category_slug"] for a in data})
    if not slugs:
        print("対象カテゴリslugを指定してください")
        return 1

    for slug in slugs:
        name = cats.get(slug, slug)
        posts = by_cat.get(slug, [])
        html = build_category_page(slug, name, posts)
        out = ROOT / "category" / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"再生成: category/{slug}/  ({name}, {len(posts)}記事)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
