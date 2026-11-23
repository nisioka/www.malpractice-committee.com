#!/usr/bin/env python3
"""SNS（Facebook・X（Twitter）・Google+）の部品を、全ページとテンプレートから外す。

サイトの Facebook ページと X のアカウントはもう運用していないので、フォロー・共有のボタン、
アカウントへのリンク、埋め込みの部品とその読み込みスクリプトを外す。RSS・Feedly の購読
リンクは `remove_dead_feeds.py` が外している。外すのは次のもので、ほかのバイトは変えない。
何度実行しても結果は同じ。

- `<body>` 直後の `<div id="fb-root">` と Facebook SDK（connect.facebook.net）の読み込み
- ヘッダーの SNS アイコン（`<div id="header-sns">`。Facebook ページと X のアカウントへのリンク）
- 記事の見出しの下と記事の末尾のツイートボタン・Google+ ボタン（`bzb-sns-btn`）と、
  ツイートボタンの読み込み（platform.twitter.com）。見出しの下の枠が空になったら枠ごと外す
- 共有バー（「共有:」）の Twitter・Facebook などの SNS のボタン。メールで送るボタンは
  SNS ではないので残す
- 記事下の「SNSでもご購読できます。」の欄（`<div class="post-share">`。Facebook ページの
  埋め込みと X のアカウントへのリンク）
- フッターの Google+ の読み込み（apis.google.com/js/platform.js）、Jetpack の Facebook 埋め込みの
  読み込み（facebook-embed.min.js とその設定）、共有ボタンを小窓で開く処理（Twitter・Facebook 用）
- `<head>` の Facebook ページ埋め込みの部品のスタイル（jetpack_facebook_likebox-inline-css）
- `<head>` のメタタグのうち、運用していないアカウントを指すもの（`twitter:site`・
  `twitter:creator`・`article:publisher`・`fb:app_id`・`fb:admins`・`fb:pages`）。他人がリンクを
  貼ったときのプレビューに使う OGP（`og:*`）と `twitter:card` は残す

- WordPress のときに共有ボタンの先（`<記事>/?share=facebook`）を辿って取り込まれた、SNS の
  画面そのものの写し（`<記事>/Pshare=facebook.html`。Facebook のログイン画面だった）。URL は残し、
  中身を記事へ転送するだけのページ（`retire_amp.py` の転送ページと同じ形）に置き換える

本文の中の記事としての SNS への言及やリンク（`twitter-introduce/` など）は記事の中身なので触らない。

対象は Git が追跡している全 HTML（`_automation/templates/` を含む）。WordPress 時代の HTML を
取り込み直したときは、このスクリプトを掛け直す。

  python3 _automation/remove_sns.py --dry-run   # 件数だけ表示
  python3 _automation/remove_sns.py             # 書き換える
"""
import argparse
import collections
import os
import re
import sys

import check_links as cl
from remove_sidebar_widgets import element_end
from retire_amp import CANONICAL, page_title, redirect_page

# 共有バー（Jetpack の sharedaddy）の SNS のボタン。email・print は SNS ではないので残す。
SNS_SHARE = ("twitter", "x", "facebook", "linkedin", "tumblr", "pinterest", "pocket", "reddit",
             "telegram", "jetpack-whatsapp", "mastodon", "nextdoor", "threads", "bluesky")

FB_SDK = re.compile(
    r"<div id=\"fb-root\"></div>\s*<script>\(function\(d, s, id\) \{(?:(?!</script>).)*?"
    r"connect\.facebook\.net(?:(?!</script>).)*?</script>\n*", re.S)
FB_ROOT = re.compile(r"[ \t]*<div id=\"fb-root\"></div>[ \t]*\n?")
HEADER_SNS = re.compile(r"^[ \t]*<div id=\"header-sns\"[^>]*><ul>(?:(?!</ul>).)*</ul></div>[ \t]*\n",
                        re.S | re.M)
SNS_BTNS = re.compile(r"[ \t]*<!-- ソーシャルボタン -->(?:(?!<!-- /bzb-sns-btns -->).)*"
                      r"<!-- /bzb-sns-btns -->[ \t]*\n?", re.S)
EMPTY_HEADER_META = re.compile(r"\n[ \t]*<div class=\"post-header-meta\">\s*</div>")
SHARE_LI = re.compile(r"<li class=\"share-(?:%s)\">(?:(?!</li>).)*</li>" % "|".join(SNS_SHARE), re.S)
GOOGLE_PLATFORM = re.compile(
    r"[ \t]*<script src=\"https://apis\.google\.com/js/platform\.js\"[^>]*>(?:(?!</script>).)*"
    r"</script>[ \t]*\n?", re.S)
FB_EMBED = re.compile(
    r"<script type=\"text/javascript\" id=\"jetpack-facebook-embed-js-extra\">(?:(?!</script>).)*</script>\n?"
    r"|<script type=\"text/javascript\" src=\"[^\"]*/facebook-embed\.min\.js[^\"]*\" "
    r"id=\"jetpack-facebook-embed-js\"></script>\n?", re.S)
LIKEBOX_CSS = re.compile(
    r"<style id='jetpack_facebook_likebox-inline-css' type='text/css'>(?:(?!</style>).)*</style>\n?", re.S)
SHARING_AFTER = re.compile(
    r"<script type=\"text/javascript\" id=\"sharing-js-js-after\">((?:(?!</script>).)*)</script>\n?", re.S)
SHARE_SELECTOR = re.compile(r"a\.share-([a-z-]+)")
ACCOUNT_META = re.compile(
    r"^[ \t]*<meta\b[^>]*\b(?:name|property)=\"(twitter:site|twitter:creator|article:publisher|"
    r"fb:app_id|fb:admins|fb:pages)\"[^>]*>[ \t]*\n", re.M)
POST_SHARE = '<div class="post-share">'
SHARE_CAPTURE = re.compile(r"(?:^|/)Pshare=(?:%s)\.html$" % "|".join(SNS_SHARE))
SHARE_MARK = "<!-- SNS の共有画面の写しだったページ。記事へ転送する（_automation/remove_sns.py が生成） -->"


def retire_share_capture(f, text, stats):
    """`<記事>/Pshare=facebook.html` などを、記事へ転送するだけのページにする。"""
    if SHARE_MARK in text:
        return text
    article = os.path.join(cl.ROOT, os.path.dirname(f), "index.html")
    if not os.path.isfile(article):
        stats["残した 共有画面の写し（記事ページが無い）"] += 1
        return text
    with open(article, encoding="utf-8") as fh:
        art = fh.read()
    m = CANONICAL.search(art)
    if not m:
        stats["残した 共有画面の写し（記事に canonical が無い）"] += 1
        return text
    stats["SNS の共有画面の写し → 記事への転送ページ"] += 1
    return redirect_page(m.group(1), page_title(art), SHARE_MARK)


def strip_post_share(text, stats):
    """記事下の「SNSでもご購読できます。」の欄を、行を占めていれば行ごと外す。"""
    out = []
    pos = 0
    while True:
        i = text.find(POST_SHARE, pos)
        if i < 0:
            break
        end = element_end(text, i)
        if end is None:
            stats["残した post-share（閉じタグが釣り合わない）"] += 1
            break
        line = text.rfind("\n", 0, i) + 1
        start = line if not text[line:i].strip() else i
        m = re.compile(r"[ \t]*\n").match(text, end)
        if start == line and m:
            end = m.end()
        out.append(text[pos:start])
        pos = end
        stats["記事下の「SNSでもご購読できます。」の欄"] += 1
    out.append(text[pos:])
    return "".join(out)


def sub_count(pattern, repl, text, stats, label):
    text, n = pattern.subn(repl, text)
    if n:
        stats[label] += n
    return text


def strip_sharing_after(text, stats):
    """共有ボタンを小窓で開く処理。SNS のボタンだけを扱うスクリプトなら丸ごと外す。"""
    def repl(m):
        services = set(SHARE_SELECTOR.findall(m.group(1)))
        if services and services <= set(SNS_SHARE):
            stats["共有ボタンを小窓で開く処理（sharing-js-js-after）"] += 1
            return ""
        stats["残した sharing-js-js-after（SNS 以外のボタンも扱う）"] += 1
        return m.group(0)
    return SHARING_AFTER.sub(repl, text)


def fix(text, stats):
    text = sub_count(FB_SDK, "", text, stats, "fb-root と Facebook SDK の読み込み")
    text = sub_count(FB_ROOT, "", text, stats, "残っていた fb-root")
    text = sub_count(HEADER_SNS, "", text, stats, "ヘッダーの SNS アイコン（header-sns）")
    text = sub_count(SNS_BTNS, "", text, stats, "ツイート・Google+ ボタン（bzb-sns-btn）")
    text = sub_count(EMPTY_HEADER_META, "", text, stats, "空になった見出しの下の枠（post-header-meta）")
    text = sub_count(SHARE_LI, "", text, stats, "共有バーの SNS のボタン")
    text = strip_post_share(text, stats)
    text = sub_count(GOOGLE_PLATFORM, "", text, stats, "Google+ の読み込み（platform.js）")
    text = sub_count(FB_EMBED, "", text, stats, "Facebook 埋め込みの読み込み（facebook-embed）")
    text = sub_count(LIKEBOX_CSS, "", text, stats, "Facebook ページ埋め込みのスタイル（likebox）")
    text = strip_sharing_after(text, stats)

    def meta(m):
        stats[f"メタタグ {m.group(1)}"] += 1
        return ""
    text = ACCOUNT_META.sub(meta, text)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="書き換えずに件数だけ表示")
    args = ap.parse_args()

    stats = collections.Counter()
    changed = 0
    for f in cl.tracked_files():
        if not f.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(cl.ROOT, f)
        with open(path, encoding="utf-8", newline="") as fh:
            before = fh.read()
        after = (retire_share_capture(f, before, stats) if SHARE_CAPTURE.search(f)
                 else fix(before, stats))
        if after != before:
            changed += 1
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(after)

    verb = "書き換え対象" if args.dry_run else "書き換えた"
    print(f"{verb}ファイル: {changed}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if any(k.startswith("残した") for k in stats):
        sys.exit(1)


if __name__ == "__main__":
    main()
