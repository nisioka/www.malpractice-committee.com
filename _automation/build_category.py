#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""カテゴリ（病院）ページに新記事を反映する。

カテゴリページには3つの形があり、形ごとに扱いを変える。

- 病院ページ（`<div class="hp-wrap">`）: 基本情報・地図と「関連記事」のカードを手作業で
  整えたもの。**作り直さず**、`<ul class="hp-cards">` に新記事のカードを日付順の位置で
  差し込む。カードはアイキャッチがあれば画像つき、無ければ文字だけの形。
- WordPress 由来の一覧（`<div class="post-loop-wrap">`）: トップと同じ形の記事カード。
  作り直さず、新記事のカードを日付順の位置で差し込み、`firstpost` を先頭のカードに移す。
  ページ送りのあるカテゴリでも、1ページ目に足すだけで後ろのページへは送らない。
- このスクリプトが作った簡易一覧（日付＋タイトルのリンク）と、ページが無い新病院:
  manifest のそのカテゴリの全記事から作り直す。

「新記事」は generate_article.py の引き継ぎファイル `_generated.json` の記事。
病院ページは病院の概要記事などを意図して載せていないので、manifest にあってページに無い
記事を全部足すことはしない。`--posts` で manifest の post_id を指定すると、
`_generated.json` の代わりにその記事を新記事として扱う（取り込み直したページの復元用）。

テーマ定型（head_assets/header_nav/sidebar/footer）は記事ページと共通の検証済みパーツを流用。
footer は記事ではないページ用（sitelib.archive_footer）で、統計に記事IDを渡さない。

使い方:
  python3 _automation/build_category.py [<slug> ...] [--posts=<post_id>,<post_id>]
  （slug 省略時は新記事のカテゴリを対象）
"""
import json
import pathlib
import re
import sys

import rebuild_listings
import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "_automation" / "manifest.json"
GENERATED = ROOT / "_automation" / "_generated.json"

HP_UL_RE = re.compile(r'(<ul class="hp-cards">\n)(.*?)(\n?[ \t]*</ul>)', re.S)
HP_NOTE_RE = re.compile(r'<p class="hp-note">.*?</p>', re.S)
HP_DATE_RE = re.compile(r'<span class="hp-card-date">(\d{4}\.\d{2}\.\d{2})</span>')
HP_HREF_RE = re.compile(r'<a href="/([^"]+)/">')
THUMB_SRC_RE = re.compile(r'<div class="post-thumbnail">\s*(?:<a [^>]*>)?<img [^>]*?\bsrc="([^"]+)"')
CARD_ID_RE = re.compile(r'<article id="post-(\d+)"')
CARD_DATE_RE = re.compile(r'datetime="([^"]+)"')


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
    posts = sorted(posts, key=newest_first)
    head = cat_head(slug, name)
    head_assets = sitelib.fill_tokens(sitelib.partial("head_assets.html"), 0, slug).rstrip("\n")
    header_nav = sitelib.partial("header_nav.html").rstrip("\n")
    sidebar = sitelib.partial("sidebar.html").rstrip("\n")
    footer = sitelib.archive_footer().rstrip("\n")
    items = "\n\n".join(cat_article_item(p) for p in posts)
    breadcrumb = (
        '<ol class="breadcrumb clearfix" itemscope="itemscope" itemtype="http://schema.org/BreadcrumbList">'
        '<li itemprop="itemListElement" itemscope="itemscope" itemtype="http://schema.org/ListItem">'
        f'<a href="{sitelib.ORIGIN}" itemprop="item"><i class="fa fa-home"></i> '
        '<span itemprop="name">ホーム</span></a><meta itemprop="position" content="1" /> / </li>'
        '<li itemprop="itemListElement" itemscope="itemscope" itemtype="http://schema.org/ListItem">'
        f'<i class="fa fa-folder"></i> <span itemprop="name">{sitelib.esc_text(name)}</span>'
        '<meta itemprop="position" content="2" /></li></ol>'
    )
    body_class = f"archive category category-{slug} left-content default"
    return f"""{sitelib.HEAD_OPEN}{head}{head_assets}
{sitelib.ADSENSE_HEAD}</head>

<body id="#top" class="{body_class}" itemscope="itemscope" itemtype="http://schema.org/WebPage">

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


def newest_first(p):
    """並べ替えのキー。公開日時の新しい順、同時刻は post_id の大きい順。"""
    return (-int(re.sub(r"\D", "", p["date"][:19]) or 0), -p["post_id"])


def read_article(slug):
    path = ROOT / slug / "index.html"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def hp_card(p):
    """病院ページの「関連記事」カード1枚（<li>）。既存カードと同じ書式。"""
    href = f'/{p["slug"]}/'
    title = sitelib.esc_text(p["title"])
    date = sitelib.disp_date(p["date"])
    m = THUMB_SRC_RE.search(read_article(p["slug"]))
    if m:
        src = m.group(1)
        if src.startswith(sitelib.ORIGIN + "/"):
            src = src[len(sitelib.ORIGIN):]
        return (f'        <li class="hp-card"><a href="{href}"><img class="hp-card-thumb" src="{src}" '
                f'alt="" loading="lazy"><span class="hp-card-body"><span class="hp-card-title">{title}</span>'
                f'<span class="hp-card-date">{date}</span></span></a></li>')
    return (f'        <li class="hp-card hp-card-text"><a href="{href}"><span class="hp-card-body">'
            '<span class="hp-card-tag">記事</span><span class="hp-card-title">'
            f'<span class="hp-card-quote">“</span>{title}</span>'
            f'<span class="hp-card-date">{date}</span></span></a></li>')


def add_hp_cards(page, posts):
    """病院ページの <ul class="hp-cards"> に、まだ無い記事のカードを日付順の位置で足す。"""
    m = HP_UL_RE.search(page)
    present = {h for h in HP_HREF_RE.findall(m.group(2))} if m else set()
    if all(p["slug"] in present for p in posts):
        return page, []
    if not m:
        note = HP_NOTE_RE.search(page)
        if not note:
            raise SystemExit("病院ページに「関連記事」の欄も注記も見つからない")
        # 関連記事がまだ1件も無い病院ページ: 注記の後ろに欄ごと作る
        page = (page[:note.end()] + '\n      <h2 class="hp-sec-title">関連記事</h2>\n'
                '      <ul class="hp-cards">\n      </ul>' + page[note.end():])
        m = HP_UL_RE.search(page)
    lines = [l for l in m.group(2).split("\n") if l.strip()]
    added = []
    for p in sorted(posts, key=newest_first):
        if p["slug"] in present:
            continue
        d = sitelib.disp_date(p["date"])
        at = next((i for i, l in enumerate(lines)
                   if (dm := HP_DATE_RE.search(l)) and dm.group(1) <= d), len(lines))
        lines.insert(at, hp_card(p))
        present.add(p["slug"])
        added.append(p)
    body = "\n".join(lines)
    return page[:m.start(2)] + body + ("\n" if not m.group(3).startswith("\n") else "") \
        + page[m.end(2):], added


def add_loop_cards(page, posts):
    """WordPress 由来の一覧に、まだ無い記事のカードを日付順の位置で足す。

    既存カードとカード間の文字列には触らず、差し込む位置にだけカードと区切りを足す。
    """
    wm = rebuild_listings.WRAP_RE.search(page)
    inner = wm.group(2)

    def key_of(card):
        return newest_first({"date": CARD_DATE_RE.search(card).group(1),
                             "post_id": int(CARD_ID_RE.match(card).group(1))})

    spans = rebuild_listings.find_cards(inner)
    gaps = [inner[x[1]:y[0]] for x, y in zip(spans, spans[1:])]
    sep = max(set(gaps), key=gaps.count) if gaps else "\n\n"
    present = {int(CARD_ID_RE.match(c).group(1)) for _, _, c in spans}
    added = []
    for p in sorted(posts, key=newest_first):
        if p["post_id"] in present:
            continue
        art = read_article(p["slug"])
        if not art:
            raise SystemExit(f"記事ページが無い: {p['slug']}/index.html")
        card = sitelib.card_from_article(art, p["post_id"], p["slug"], p["category_slug"],
                                         p["title"], p["date"]).lstrip()
        spans = rebuild_listings.find_cards(inner)
        at = next((i for i, (_, _, c) in enumerate(spans) if key_of(c) >= newest_first(p)), None)
        if at is None:
            pos = spans[-1][1]
            inner = inner[:pos] + sep + card + inner[pos:]
        else:
            pos = spans[at][0]
            inner = inner[:pos] + card + sep + inner[pos:]
        present.add(p["post_id"])
        added.append(p)
    if not added:
        return page, added
    # firstpost は先頭のカードだけに付ける（後ろから置き換えて位置をずらさない）
    spans = rebuild_listings.find_cards(inner)
    for i, (x, y, c) in reversed(list(enumerate(spans))):
        c2 = rebuild_listings.strip_firstpost(c)
        if i == 0:
            c2 = rebuild_listings.add_firstpost(c2)
        inner = inner[:x] + c2 + inner[y:]
    return page[:wm.start(2)] + inner + page[wm.end(2):], added


def load_new_posts(manifest, argv):
    """新記事（manifest の形）。--posts 指定が優先、無ければ _generated.json。"""
    by_id = {p["post_id"]: p for p in manifest["posts"]}
    opt = next((a for a in argv if a.startswith("--posts=")), None)
    if opt:
        ids = [int(x) for x in opt.split("=", 1)[1].split(",") if x.strip()]
    elif GENERATED.is_file():
        ids = [a["post_id"] for a in json.loads(GENERATED.read_text(encoding="utf-8"))]
    else:
        ids = []
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"manifest に無い post_id: {missing}（先に build_manifest.py を実行）")
    return [by_id[i] for i in ids]


def main(argv):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cats = manifest["categories"]
    by_cat = {}
    for p in manifest["posts"]:
        by_cat.setdefault(p["category_slug"], []).append(p)

    new_posts = load_new_posts(manifest, argv)
    slugs = [a for a in argv[1:] if not a.startswith("--")]
    if not slugs:
        slugs = sorted({p["category_slug"] for p in new_posts})
    if not slugs:
        print("対象カテゴリslugを指定してください")
        return 1

    for slug in slugs:
        name = cats.get(slug, slug)
        posts = by_cat.get(slug, [])
        new_here = [p for p in new_posts if p["category_slug"] == slug]
        out = ROOT / "category" / slug / "index.html"
        page = out.read_text(encoding="utf-8") if out.is_file() else ""
        if 'class="hp-wrap"' in page:
            html, added = add_hp_cards(page, new_here)
            kind = "病院ページにカードを追加"
        elif 'class="post-loop-wrap"' in page:
            html, added = add_loop_cards(page, new_here)
            kind = "一覧にカードを追加"
            if added and 'class="pagination"' in page:
                print(f"  注意: category/{slug}/ はページ送りがある。1ページ目に足しただけで、"
                      "後ろのページへは送っていない")
        else:
            html = build_category_page(slug, name, posts)
            added = posts
            kind = "簡易一覧を作り直し" if page else "新規作成"
        if html != page:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
        print(f"{kind}: category/{slug}/  ({name}, {len(added)}記事)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
