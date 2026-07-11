#!/usr/bin/env python3
"""定型パーツ抽出スクリプト（一度だけ実行）。

既存記事 settlement/index.html を「唯一の真実」として、全ページ共通の
定型ブロック（head内のCSS/JS群・ヘッダ/ナビ・サイドバー・フッタ/スクリプト）を
_automation/templates/ に切り出す。可変部分（タイトル・本文など）はコード側で
組み立てるため、ここでは触らない。

抽出する定型パーツ:
  head_assets.html  : head内の dns-prefetch 〜 </head> 直前（テーマCSS/JS・GA等）
  header_nav.html   : <body>直後の fb-root 〜 </nav>（ロゴ・SNS・グローバルナビ）
  sidebar.html      : <div id="side"> 〜 </div><!-- /side -->（検索・案内・ランキング・広告枠）
  footer.html       : <footer id="footer"> 〜 </html>（コピーライト・各種スクリプト）
                      ※ 記事ID依存の解析タグは {{POST_ID}} / {{SLUG}} トークン化する
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "settlement" / "index.html"
OUT = ROOT / "_automation" / "templates"
OUT.mkdir(parents=True, exist_ok=True)

html = SRC.read_text(encoding="utf-8")


def slice_between(text, start_marker, end_marker, include_end=True):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i : j + (len(end_marker) if include_end else 0)]


# 1) head_assets: dns-prefetch から </head> 直前まで（定型のCSS/JS/GA/favicon）
head_assets = slice_between(
    html,
    "<link rel='dns-prefetch' href='//stats.wp.com' />",
    "</head>",
    include_end=False,
).rstrip() + "\n"

# --- head_assets に混入する「記事固有 & 静的サイトでは実体のない」リンクを除去 ---
# コメントフィード(alternate rss)・oembed・shortlink・amphtml は静的出力に実体が無く
# dangling になるため丸ごと削除する。
head_assets = re.sub(
    r'<link rel="alternate" type="application/rss\+xml"[^>]*?/settlement/feed/" />\s*',
    "", head_assets)
head_assets = re.sub(
    r'<link rel="alternate" type="application/(?:json|text/xml)\+oembed"[^>]*?/embed\?url=[^>]*?/>\s*',
    "", head_assets)
head_assets = re.sub(
    r'<link rel="alternate" type="text/xml\+oembed"[^>]*?/>\s*', "", head_assets)
head_assets = re.sub(r"<link rel='shortlink'[^>]*?/>\s*", "", head_assets)
head_assets = re.sub(r'<link rel="amphtml"[^>]*?>', "", head_assets)

# --- 残る記事ID依存部分をトークン化（wpp設定のID・wp-json REST リンク）---
head_assets = head_assets.replace('"ID":548,', '"ID":{{POST_ID}},')
head_assets = head_assets.replace(
    "/wp-json/wp/v2/posts/548", "/wp-json/wp/v2/posts/{{POST_ID}}")

(OUT / "head_assets.html").write_text(head_assets, encoding="utf-8")

# 2) header_nav: <body>直後の fb-root から </nav> まで
header_nav = slice_between(html, '<div id="fb-root"></div>', "</nav>", include_end=True)
(OUT / "header_nav.html").write_text(header_nav + "\n", encoding="utf-8")

# 3) sidebar: <div id="side" ... から </div><!-- /side --> まで
sidebar = slice_between(html, '<div id="side"', "</div><!-- /side -->", include_end=True)
(OUT / "sidebar.html").write_text(sidebar + "\n", encoding="utf-8")

# 4) footer: <footer id="footer"> から </html> まで。記事ID/slug依存部分をトークン化。
footer = slice_between(html, '<footer id="footer">', "</html>", include_end=True)
# WPCOM_sharing_counts の {".../settlement/":548}
footer = footer.replace(
    r'{"https:\/\/www.malpractice-committee.tech.server-on.net\/settlement\/":548}',
    r'{"https:\/\/www.malpractice-committee.tech.server-on.net\/{{SLUG}}\/":{{POST_ID}}}',
)
# _stq view の post":"548"
footer = footer.replace('\\"post\\":\\"548\\"', '\\"post\\":\\"{{POST_ID}}\\"')
# clickTrackerInit の "548"
footer = footer.replace('"clickTrackerInit", "102782097", "548"',
                        '"clickTrackerInit", "102782097", "{{POST_ID}}"')
(OUT / "footer.html").write_text(footer + "\n", encoding="utf-8")

# 5) post_share: <div class="post-share"> 〜 <aside class="post-author"> 直前（FB案内・定型）
post_share = slice_between(html, '<div class="post-share">',
                           '<aside class="post-author"', include_end=False).rstrip() + "\n"
(OUT / "post_share.html").write_text(post_share, encoding="utf-8")

# 6) post_author: <aside class="post-author" 〜 </aside>（著者枠・定型）
post_author = slice_between(html, '<aside class="post-author"', "</aside>", include_end=True)
(OUT / "post_author.html").write_text(post_author + "\n", encoding="utf-8")

# 7) comments: <div id="comments" 〜 </div><!-- #comments -->。記事ID/slug依存をトークン化。
comments = slice_between(html, '<div id="comments"', "</div><!-- #comments -->", include_end=True)
comments = comments.replace("/settlement/#respond", "/{{SLUG}}/#respond")
comments = comments.replace("value='548' id='comment_post_ID'",
                            "value='{{POST_ID}}' id='comment_post_ID'")
(OUT / "comments.html").write_text(comments + "\n", encoding="utf-8")

# 抽出結果の要約を表示
for name in ["head_assets.html", "header_nav.html", "sidebar.html", "footer.html"]:
    p = OUT / name
    print(f"{name:20s} {len(p.read_text(encoding='utf-8')):6d} bytes")

# 健全性チェック: 記事固有語が定型パーツに残っていないか
leaks = []
for name in ["head_assets.html", "header_nav.html", "sidebar.html", "footer.html"]:
    t = (OUT / name).read_text(encoding="utf-8")
    for bad in ["med-takaoka", "高岡", "6000", "settlement/"]:
        if bad in t:
            leaks.append(f"{name}: '{bad}'")
if leaks:
    print("WARNING 記事固有語の残留:", leaks)
else:
    print("OK 定型パーツに記事固有語の残留なし")
