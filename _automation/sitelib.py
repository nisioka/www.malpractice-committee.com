#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""医療ミス調査会サイト 生成ロジック共通ライブラリ。

_automation/templates/ の定型パーツ（extract_partials.py が生成）を読み込み、
可変部分だけをコードで組み立てて、既存記事とバイト単位で近い出力を作る。

用語:
  ORIGIN  : サイト内リンクの正規オリジン（既存の焼き込みに合わせる）
  PUBLIC  : 共有ウィジェットが使うオリジン（現在は ORIGIN と同一の正規ホスト）
"""
import html
import json
import pathlib
import re
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = ROOT / "_automation" / "templates"

ORIGIN = "https://www.malpractice-committee.tech.server-on.net"
PUBLIC = "https://www.malpractice-committee.tech.server-on.net"
SITE_NAME = "医療ミス調査会"
GSV = "H1KgfloTeWRYi-qgex21ur4c_holl4FXFgq9XaCAzz0"

# ---- 定型パーツ読み込み --------------------------------------------------

def partial(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


HEAD_OPEN = (
    "<!DOCTYPE HTML>\n"
    '<html lang="ja">\n'
    '<head prefix="og: http://ogp.me/ns# fb: http://ogp.me/ns/fb# article: http://ogp.me/ns/article#">\n'
    "\t<meta charset=\"UTF-8\">\n"
    "\t\n"
    "\t<meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">\n"
    "\t<!--[if lt IE 9]>\n"
    "    <script src=\"http://html5shiv.googlecode.com/svn/trunk/html5.js\"></script>\n"
    "  <![endif]-->\n\n\n"
)


def fill_tokens(text: str, post_id, slug: str) -> str:
    return text.replace("{{POST_ID}}", str(post_id)).replace("{{SLUG}}", slug)


# Google AdSense 雛形（現在は無効化）。
# 独自ドメインでの所有権認証・審査通過後、下記コメントを外し ca-pub-XX... を差し込めば有効化できる。
# サイト全体へ一括適用する場合は _automation/inject_adsense.py（将来）で全HTMLに挿入する。
ADSENSE_HEAD = (
    "<!-- Google AdSense（未有効化。独自ドメイン認証後に下行を有効化）\n"
    '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>\n'
    "-->\n"
)


# ---- 小道具 --------------------------------------------------------------

def esc_attr(s: str) -> str:
    """HTML属性値用エスケープ。"""
    return html.escape(s, quote=True)


def esc_text(s: str) -> str:
    return html.escape(s, quote=False)


def disp_date(dt_iso: str) -> str:
    """2020-06-01T11:24:00+09:00 -> 2020.06.01"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", dt_iso)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else dt_iso


def page_url(n: int) -> str:
    """ページ番号 -> URL。1ページ目は /page/1/ ではなくルート。"""
    return f"{ORIGIN}/" if n == 1 else f"{ORIGIN}/page/{n}/"


def build_pagination(current: int, last: int) -> str:
    """WordPress のページ送りを完全再現。

    番号窓 = current-4 .. current+4 を [1, last] にclamp。
    左矢印: 前ページへ(‹) は current>1、先頭へ(«) は窓が1を含まない時。
    右矢印: 次ページへ(›) は current<last、末尾へ(») は窓が last を含まない時。
    ※ 右矢印(›)のみ href がダブルクォート、他はシングルクォート（既存出力に合わせる）。
    """
    if last <= 1:
        return ""
    win_start = max(1, current - 4)
    win_end = min(last, current + 4)
    p = ['<div class="pagination">']
    if current > 1:
        if win_start > 1:
            p.append(f"<a href='{ORIGIN}/'><i class='fa fa-angle-double-left'></i></a>")
        p.append(f"<a href='{page_url(current - 1)}'><i class='fa fa-angle-left'></i></a>")
    for n in range(win_start, win_end + 1):
        if n == current:
            p.append(f'<span class="current">{n}</span>')
        else:
            p.append(f"<a href='{page_url(n)}' class=\"inactive\">{n}</a>")
    if current < last:
        p.append(f'<a href="{page_url(current + 1)}"><i class=\'fa fa-angle-right\'></i></a>')
        if win_end < last:
            p.append(f"<a href='{page_url(last)}'><i class='fa fa-angle-double-right'></i></a>")
    p.append("</div>")
    return "".join(p)


# ---- 本文（記事・一覧カード共通） ---------------------------------------

def build_content_div(data: dict) -> str:
    """本文段落 + 出典行 を <div> でまとめる（記事本体・一覧カード共通）。"""
    body = data["body_html"].strip()
    src = (
        f'<p style="text-align: right;">出典：'
        f'<a href="{esc_attr(data["source_url"])}">{esc_text(data["source_name"])}</a></p>'
    )
    return f"<div>\n{body}\n{src}\n</div>"


def build_sharebar(post_id, slug: str, title: str) -> str:
    """sharedaddy 共有バー（記事・一覧カード共通）。"""
    u = f"{ORIGIN}/{slug}/"
    subj = urllib.parse.quote(f"[共有投稿] {title}")
    body_url = urllib.parse.quote(f"{PUBLIC}/{slug}/")
    return (
        '<div class="sharedaddy sd-sharing-enabled"><div class="robots-nocontent sd-block sd-social '
        'sd-social-icon-text sd-sharing"><h3 class="sd-title">共有:</h3><div class="sd-content"><ul>'
        f'<li class="share-twitter"><a rel="nofollow noopener noreferrer" data-shared="sharing-twitter-{post_id}" '
        f'class="share-twitter sd-button share-icon" href="{u}?share=twitter" target="_blank" '
        'title="クリックして Twitter で共有" ><span>Twitter</span></a></li>'
        f'<li class="share-facebook"><a rel="nofollow noopener noreferrer" data-shared="sharing-facebook-{post_id}" '
        f'class="share-facebook sd-button share-icon" href="{u}?share=facebook" target="_blank" '
        'title="Facebook で共有するにはクリックしてください" ><span>Facebook</span></a></li>'
        '<li class="share-email"><a rel="nofollow noopener noreferrer" data-shared="" '
        f'class="share-email sd-button share-icon" href="mailto:?subject={subj}&body={body_url}&share=email" '
        'target="_blank" title="クリックして友達にメールでリンクを送信"><span>メールアドレス</span></a></li>'
        '<li class="share-end"></li></ul></div></div></div>'
    )


def build_social_buttons(slug: str, title: str) -> str:
    """bzb-sns-btn（Tweet + g-plusone）。記事のヘッダ/フッタ2箇所で使用。"""
    return (
        '<!-- ソーシャルボタン -->\n'
        '  <ul class="bzb-sns-btn ">\n'
        '      <li class="bzb-twitter">\n'
        f'      <a href="https://twitter.com/share" class="twitter-share-button"  '
        f'data-url="{ORIGIN}/{slug}/"  data-text="{esc_attr(title)}">Tweet</a>\n'
        "      <script>!function(d,s,id){var js,fjs=d.getElementsByTagName(s)[0],"
        "p=/^http:/.test(d.location)?'http':'https';if(!d.getElementById(id)){js=d.createElement(s);"
        "js.id=id;js.async=true;js.src=p+'://platform.twitter.com/widgets.js';"
        "fjs.parentNode.insertBefore(js,fjs);}}(document, 'script', 'twitter-wjs');</script>\n"
        '    </li>    <li class="bzb-googleplus">\n'
        f'      <div class="g-plusone" data-href="{urllib.parse.quote(PUBLIC + "/" + slug + "/", safe="")}" ></div>\n'
        '    </li>\n'
        '  </ul>\n'
        '  <!-- /bzb-sns-btns -->'
    )


def build_thumbnail(data: dict, linked: bool) -> str:
    """アイキャッチ画像。image が無ければ空文字。"""
    img = data.get("image")
    if not img:
        return ""
    src = img["url"]
    w = img.get("width", 285)
    h = img.get("height", 214)
    tag = (
        f'<img width="{w}" height="{h}" src="{esc_attr(src)}" '
        'class="attachment-post-thumbnail size-post-thumbnail wp-post-image" alt="" decoding="async" '
        f'srcset="{esc_attr(src)} {w}w" sizes="(max-width: {w}px) 100vw, {w}px" />'
    )
    if linked:
        tag = f'<a href="{ORIGIN}/{data["slug"]}/" rel="nofollow">{tag}</a>'
    return f'<div class="post-thumbnail">\n          {tag}        </div>'


# ---- JSON-LD -------------------------------------------------------------

def build_jsonld(data: dict) -> str:
    slug = data["slug"]
    url = f"{ORIGIN}/{slug}/"
    graph = [
        {
            "@type": "Article",
            "@id": f"{url}#article",
            "headline": data["title"],
            "author": {"@id": f"{ORIGIN}/#person"},
            "publisher": {"@id": f"{ORIGIN}/#person"},
            "datePublished": data["date"],
            "dateModified": data.get("modified", data["date"]),
            "inLanguage": "ja",
            "mainEntityOfPage": {"@id": f"{url}#webpage"},
            "isPartOf": {"@id": f"{url}#webpage"},
            "articleSection": data["hospital_name"],
        },
        {
            "@type": "BreadcrumbList",
            "@id": f"{url}#breadcrumblist",
            "itemListElement": [
                {"@type": "ListItem", "@id": f"{ORIGIN}/#listItem", "position": 1,
                 "name": "家", "item": f"{ORIGIN}/", "nextItem": f"{url}#listItem"},
                {"@type": "ListItem", "@id": f"{url}#listItem", "position": 2,
                 "name": data["title"], "previousItem": f"{ORIGIN}/#listItem"},
            ],
        },
        {"@type": "Person", "@id": f"{ORIGIN}/#person", "name": "管理者"},
        {
            "@type": "WebPage", "@id": f"{url}#webpage", "url": url,
            "name": f'{data["title"]} | {SITE_NAME}',
            "description": data["description"], "inLanguage": "ja",
            "isPartOf": {"@id": f"{ORIGIN}/#website"},
            "breadcrumb": {"@id": f"{url}#breadcrumblist"},
            "datePublished": data["date"], "dateModified": data.get("modified", data["date"]),
        },
        {
            "@type": "WebSite", "@id": f"{ORIGIN}/#website", "url": f"{ORIGIN}/",
            "name": SITE_NAME,
            "description": "あなたとあなたの家族、あなたの大切な人の命に直結する場所、それが病院。",
            "inLanguage": "ja", "publisher": {"@id": f"{ORIGIN}/#person"},
        },
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


# ---- 記事ページ用の可変head ---------------------------------------------

def build_article_head(data: dict) -> str:
    slug = data["slug"]
    title = data["title"]
    desc = data["description"]
    kw = data.get("keywords", data["hospital_name"])
    jsonld = build_jsonld(data)
    return (
        "\t\t<!-- All in One SEO 4.6.1.1 - aioseo.com -->\n"
        f"\t\t<title>{esc_text(title)} | {SITE_NAME}</title>\n"
        f'\t\t<meta name="description" content="{esc_attr(desc)}" />\n'
        '\t\t<meta name="robots" content="max-snippet:-1, max-image-preview:large, max-video-preview:-1" />\n'
        f'\t\t<meta name="google-site-verification" content="{GSV}" />\n'
        f'\t\t<meta name="keywords" content="{esc_attr(kw)}" />\n'
        f'\t\t<link rel="canonical" href="{ORIGIN}/{slug}/" />\n'
        '\t\t<meta name="generator" content="All in One SEO (AIOSEO) 4.6.1.1" />\n'
        '\t\t<meta name="google" content="nositelinkssearchbox" />\n'
        '\t\t<script type="application/ld+json" class="aioseo-schema">\n'
        f"\t\t\t{jsonld}\n"
        "\t\t</script>\n"
        "\t\t<!-- All in One SEO -->\n\n"
        f'<meta name="keywords" content="{esc_attr(kw)}" />\n'
        f'<meta name="description" content="{esc_attr(desc)}" />\n'
        '<meta name="robots" content="index" />\n'
        '<meta property="fb:admins" content="197947167205693" />\n'
        '<meta property="fb:app_id" content="764065833702089" />\n'
        f'<meta property="og:title" content="{esc_attr(title)}" />\n'
        '<meta property="og:type" content="article" />\n'
        f'<meta property="og:description" content="{esc_attr(desc)}" />\n'
        f'<meta property="og:url" content="{ORIGIN}/{slug}/" />\n'
        + (f'<meta property="og:image" content="{esc_attr(data["image"]["url"])}" />\n'
           if data.get("image") else "")
        + '<meta property="og:locale" content="ja_JP" />\n'
        f'<meta property="og:site_name" content="{SITE_NAME}" />\n'
        '<meta content="summary" name="twitter:card" />\n'
        '<meta content="MediMalpComm" name="twitter:site" />\n'
    )


# ---- 記事本体 <article> --------------------------------------------------

def build_article(data: dict) -> str:
    pid = data["post_id"]
    slug = data["slug"]
    catslug = data["category_slug"]
    catname = data["hospital_name"]
    title = data["title"]
    thumb_cls = " has-post-thumbnail" if data.get("image") else ""
    social = build_social_buttons(slug, title)
    thumb = build_thumbnail(data, linked=False)
    content = build_content_div(data)
    sharebar = build_sharebar(pid, slug, title)
    comments = fill_tokens(partial("comments.html"), pid, slug).rstrip("\n")

    return f"""        <article id="post-{pid}" class="post-{pid} post type-post status-publish format-standard{thumb_cls} hentry category-{catslug}" itemscope="itemscope" itemtype="http://schema.org/BlogPosting">

      <header class="post-header">
        <ul class="post-meta list-inline">
          <li class="date updated" itemprop="datePublished" datetime="{data["date"]}"><i class="fa fa-clock-o"></i> {disp_date(data["date"])}</li>
        </ul>
        <h1 class="post-title" itemprop="headline">{esc_text(title)}</h1>
        <div class="post-header-meta">
            {social}        </div>
      </header>

      <section class="post-content" itemprop="text">

                {thumb}
{content}
{sharebar}
<div id='jp-relatedposts' class='jp-relatedposts' >
	<h3 class="jp-relatedposts-headline"><em>関連</em></h3>
</div>
      </section>

      <footer class="post-footer">

        {social}
        <ul class="post-footer-list">
          <li class="cat"><i class="fa fa-folder"></i> <a href="{ORIGIN}/category/{catslug}/" rel="category tag">{esc_text(catname)}</a></li>
                  </ul>
      </footer>


      {partial("post_share.html").rstrip(chr(10))}

          {partial("post_author.html").rstrip(chr(10))}

{comments}

    </article>"""


# ---- 一覧カード（トップ/ページ送り/カテゴリ共通） -----------------------

def build_list_card(data: dict, first: bool = False) -> str:
    pid = data["post_id"]
    slug = data["slug"]
    catslug = data["category_slug"]
    title = data["title"]
    first_cls = " firstpost" if first else ""
    thumb_cls = " has-post-thumbnail" if data.get("image") else ""
    content = build_content_div(data)
    sharebar = build_sharebar(pid, slug, title)
    # build_thumbnail は <div class="post-thumbnail">…</div> を丸ごと返す（画像無しは空文字）
    thumb_block = ("                " + build_thumbnail(data, linked=True)) if data.get("image") else ""

    return f"""        <article id="post-{pid}" class="post-{pid} post type-post status-publish format-standard{thumb_cls} hentry category-{catslug}{first_cls}" itemscope="itemscope" itemtype="http://schema.org/BlogPosting">

      <header class="post-header">
        <ul class="post-meta list-inline">
          <li class="date updated" itemprop="datePublished" datetime="{data["date"]}"><i class="fa fa-clock-o"></i> {disp_date(data["date"])}</li>
        </ul>
        <h2 class="post-title" itemprop="headline"><a href="{ORIGIN}/{slug}/">{esc_text(title)}</a></h2>
      </header>

      <section class="post-content" itemprop="text">

{thumb_block}

{content}
{sharebar}      </section>

    </article>"""


# ---- 既存記事ページ → 一覧カード（本文verbatim再利用） -----------------

_SECTION_RE = re.compile(
    r'<section class="post-content" itemprop="text">(.*?)</section>', re.S)
_REL_RE = re.compile(r"<div id='jp-relatedposts'.*?</div>\s*", re.S)
_ART_ID_RE = re.compile(r'<article id="post-(\d+)"[^>]*class="([^"]*)"')


def card_from_article(article_html: str, post_id: int, slug: str, category_slug: str,
                      title: str, date: str, first: bool = False) -> str:
    """既存の記事ページHTMLから一覧カードを組み立てる。

    本文(section.post-content の中身)は verbatim 再利用し、関連記事ブロックだけ除去する。
    これにより既存記事の本文・アフィリエイト枠等をそのまま維持する。
    """
    m = _SECTION_RE.search(article_html)
    section_inner = m.group(1) if m else ""
    section_inner = _REL_RE.sub("", section_inner).rstrip()
    thumb_cls = " has-post-thumbnail" if "post-thumbnail" in section_inner else ""
    first_cls = " firstpost" if first else ""
    return f"""        <article id="post-{post_id}" class="post-{post_id} post type-post status-publish format-standard{thumb_cls} hentry category-{category_slug}{first_cls}" itemscope="itemscope" itemtype="http://schema.org/BlogPosting">

      <header class="post-header">
        <ul class="post-meta list-inline">
          <li class="date updated" itemprop="datePublished" datetime="{date}"><i class="fa fa-clock-o"></i> {disp_date(date)}</li>
        </ul>
        <h2 class="post-title" itemprop="headline"><a href="{ORIGIN}/{slug}/">{esc_text(title)}</a></h2>
      </header>

      <section class="post-content" itemprop="text">
{section_inner}
      </section>

    </article>"""


# ---- ページ全体の組み立て（記事ページ） ---------------------------------

def assemble_article_page(data: dict) -> str:
    pid = data["post_id"]
    slug = data["slug"]
    catslug = data["category_slug"]
    catname = data["hospital_name"]
    title = data["title"]

    head = build_article_head(data)
    head_assets = fill_tokens(partial("head_assets.html"), pid, slug).rstrip("\n")
    header_nav = partial("header_nav.html").rstrip("\n")
    sidebar = partial("sidebar.html").rstrip("\n")
    footer = fill_tokens(partial("footer.html"), pid, slug).rstrip("\n")
    article = build_article(data)

    body_class = (f"post-template-default single single-post postid-{pid} "
                  "single-format-standard left-content default")
    breadcrumb = (
        '<ol class="breadcrumb clearfix"><li itemscope="itemscope" itemtype="http://data-vocabulary.org/Breadcrumb">'
        f'<a href="{ORIGIN}" itemprop="url"><i class="fa fa-home"></i> <span itemprop="title">ホーム</span></a> / </li>'
        '<li itemscope="itemscope" itemtype="http://data-vocabulary.org/Breadcrumb">'
        f'<a href="{ORIGIN}/category/{catslug}/" itemprop="url"><i class="fa fa-folder"></i> '
        f'<span itemprop="title">{esc_text(catname)}</span></a> / </li>'
        f'<li><i class="fa fa-file-text"></i> {esc_text(title)}</li></ol>'
    )

    return f"""{HEAD_OPEN}{head}{head_assets}
{ADSENSE_HEAD}</head>

<body id="#top" class="{body_class}" itemschope="itemscope" itemtype="http://schema.org/WebPage">

  {header_nav}


<div id="content">


<div class="wrap">


    {breadcrumb}
  <div id="main" class="col-md-8" role="main" itemprop="mainContentOfPage" itemscope="itemscope" itemtype="http://schema.org/Blog">


    <div class="main-inner">



{article}




    </div><!-- /main-inner -->


  </div><!-- /main -->

  {sidebar}


</div><!-- /wrap -->


</div><!-- /content -->

{footer}
"""
