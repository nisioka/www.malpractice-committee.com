#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""サイト内検索の索引と検索結果ページを再生成する（決定論）。

  search/search-index.json … 全記事の題名・日付・病院名・本文テキスト
  search/index.html        … 検索結果ページ（定型パーツは templates/ を流用）

検索はブラウザ側だけで動く。`search/search.js` が索引を読み、入力された語を
部分一致で探す。日本語は分かち書きされないので、語に区切って索引を引く方式ではなく、
本文そのものを持たせて文字列として探す。記事数が数百のうちは全件を走査しても一瞬で終わる。

対象は manifest.json の記事。AMP・Pnoamp などの重複バリアントと、一覧・カテゴリページは
同じ本文の写しなので含めない。実行前に build_manifest.py で manifest を最新化しておくこと。

使い方:
  python3 _automation/build_manifest.py
  python3 _automation/build_search.py
  python3 _automation/build_search.py --check   # 書き換えずに、再生成結果と一致するかだけ見る
"""
import argparse
import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "_automation" / "manifest.json"
OUT_DIR = ROOT / "search"
INDEX = OUT_DIR / "search-index.json"
PAGE = OUT_DIR / "index.html"

SECTION_RE = re.compile(r'<section class="post-content" itemprop="text">(.*?)</section>', re.S)
# 本文ではない部品。共有ボタン、関連記事の枠、書籍の商品枠、目次。
SKIP_CLASSES = {"sharedaddy", "jp-relatedposts", "booklink-box"}
SKIP_IDS = {"toc_container"}
# 中身を読まない要素。商品枠は script の document.write と noscript の iframe で出来ている。
SKIP_TAGS = {"script", "style", "noscript", "iframe"}
# 前後で語が切れる要素。空白を挟まないと、段落の終わりと次の段落の頭がつながって一致する。
BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
              "tr", "td", "th", "table", "blockquote", "figure", "figcaption",
              "dl", "dt", "dd", "section"}


class BodyText(HTMLParser):
    """記事本文の HTML から、読める文字だけを取り出す。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_tag = None   # 読み飛ばし中の要素名
        self._skip_depth = 0    # 同じ名前の要素の入れ子の深さ

    def handle_starttag(self, tag, attrs):
        if self._skip_tag:
            if tag == self._skip_tag:
                self._skip_depth += 1
            return
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if tag in SKIP_TAGS or classes & SKIP_CLASSES or a.get("id") in SKIP_IDS:
            self._skip_tag, self._skip_depth = tag, 1
            return
        if tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_startendtag(self, tag, attrs):
        # `<br />` のように自分で閉じる要素。閉じタグが来ないので読み飛ばしを始めない。
        if not self._skip_tag and tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self._skip_tag:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth == 0:
                    self._skip_tag = None
            return
        if tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self._skip_tag:
            self.parts.append(data)


def body_text(article_html: str) -> str:
    m = SECTION_RE.search(article_html)
    if not m:
        return ""
    p = BodyText()
    p.feed(m.group(1))
    p.close()
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


def build_docs(manifest: dict) -> list:
    docs = []
    for p in sorted(manifest["posts"], key=lambda x: x["post_id"], reverse=True):
        page = ROOT / p["slug"] / "index.html"
        if not page.is_file():
            continue
        doc = {
            "s": p["slug"],
            # manifest の題名は HTML の実体参照が残ったまま。検索は文字そのものと比べる。
            "t": html.unescape(p["title"]),
            "d": p["date"][:10],
            "h": manifest["categories"].get(p["category_slug"], ""),
            "b": body_text(page.read_text(encoding="utf-8", errors="replace")),
        }
        # 病院のページが無いカテゴリがある。無いものへはリンクさせない。
        if (ROOT / "category" / p["category_slug"] / "index.html").is_file():
            doc["c"] = p["category_slug"]
        docs.append(doc)
    return docs


def render_index(docs: list) -> str:
    """1記事1行。記事が増えても差分が増えた行だけになる。"""
    lines = [json.dumps(d, ensure_ascii=False, separators=(",", ":")) for d in docs]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def search_head() -> str:
    url = f"{sitelib.ORIGIN}/search/"
    return (
        f"\t\t<title>サイト内検索 | {sitelib.SITE_NAME}</title>\n"
        # 検索結果は語ごとに無数にあり、中身は記事の写し。検索エンジンには載せない。
        '\t\t<meta name="robots" content="noindex, follow" />\n'
        f'\t\t<link rel="canonical" href="{url}" />\n\n'
        f'<meta property="og:title" content="サイト内検索" />\n'
        '<meta property="og:type" content="website" />\n'
        f'<meta property="og:url" content="{url}" />\n'
        '<meta property="og:locale" content="ja_JP" />\n'
        f'<meta property="og:site_name" content="{sitelib.SITE_NAME}" />\n'
    )


def render_page() -> str:
    head_assets = sitelib.fill_tokens(sitelib.partial("head_assets.html"), 0, "search").rstrip("\n")
    header_nav = sitelib.partial("header_nav.html").rstrip("\n")
    sidebar = sitelib.partial("sidebar.html").rstrip("\n")
    footer = sitelib.fill_tokens(sitelib.partial("footer.html"), 0, "search").rstrip("\n")
    breadcrumb = (
        '<ol class="breadcrumb clearfix" itemscope="itemscope" itemtype="http://schema.org/BreadcrumbList">'
        '<li itemprop="itemListElement" itemscope="itemscope" itemtype="http://schema.org/ListItem">'
        f'<a href="{sitelib.ORIGIN}" itemprop="item"><i class="fa fa-home"></i> '
        '<span itemprop="name">ホーム</span></a><meta itemprop="position" content="1" /> / </li>'
        '<li itemprop="itemListElement" itemscope="itemscope" itemtype="http://schema.org/ListItem">'
        '<i class="fa fa-search"></i> <span itemprop="name">サイト内検索</span>'
        '<meta itemprop="position" content="2" /></li></ol>'
    )
    return f"""{sitelib.HEAD_OPEN}{search_head()}{head_assets}
<link rel='stylesheet' id='site-search-css' href='{sitelib.ORIGIN}/search/search.css' type='text/css' media='all' />
{sitelib.ADSENSE_HEAD}</head>

<body id="#top" class="site-search left-content default" itemschope="itemscope" itemtype="http://schema.org/WebPage">

  {header_nav}


<div id="content">

<div class="wrap">
    {breadcrumb}
  <div id="main" class="col-md-8" role="main">

    <div class="main-inner">

    <section class="cat-content">
      <header class="cat-header">
        <h1 class="post-title">サイト内検索</h1>
      </header>
      <form role="search" method="get" class="site-search-form" action="{sitelib.ORIGIN}/search/">
        <div>
        <input type="text" value="" name="q" id="site-search-q" aria-label="サイト内検索" />
        <button type="submit" aria-label="検索">&#xf002;</button>
        </div>
      </form>
      <p id="site-search-status" class="site-search-status" role="status" aria-live="polite"></p>
      <noscript><p class="site-search-status">検索には JavaScript が必要です。病院名からは<a href="{sitelib.ORIGIN}/hospital-info/">病院一覧</a>で探せます。</p></noscript>
      <div id="site-search-results" class="cat-content-area"></div>
      <p class="site-search-more"><button type="button" id="site-search-more" hidden>さらに表示</button></p>
    </section>

    </div><!-- /main-inner -->
  </div><!-- /main -->

  {sidebar}

</div><!-- /wrap -->


</div><!-- /content -->

<script src="{sitelib.ORIGIN}/search/search.js" defer></script>
{footer}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="書き換えずに、再生成結果が今のファイルと一致するかだけ見る")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    docs = build_docs(manifest)
    outputs = [(INDEX, render_index(docs)), (PAGE, render_page())]

    empty = [d["s"] for d in docs if not d["b"]]
    size = len(outputs[0][1].encode("utf-8"))
    print(f"記事: {len(docs)} 件 / 索引: {size:,} バイト")
    if empty:
        print(f"WARN 本文を取り出せなかった記事({len(empty)}): {empty[:10]}")

    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, text in outputs
                 if not path.is_file() or path.read_text(encoding="utf-8") != text]
        if stale:
            print(f"再生成が必要: {stale}")
            return 1
        print("一致")
        return 0

    OUT_DIR.mkdir(exist_ok=True)
    for path, text in outputs:
        path.write_text(text, encoding="utf-8")
        print(f"再生成: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
