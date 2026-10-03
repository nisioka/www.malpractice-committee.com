#!/usr/bin/env python3
"""サイト内参照の存在チェック。

全 HTML / CSS の参照（img・source の src/srcset、link、script、iframe、a href、
CSS の url()）を取り出し、サイト内を指すものをリポジトリ内のファイルの有無と突き合わせる。
外部 URL は叩かず、ホスト別の件数だけを出す。`_automation/templates/` の部品も走査対象。

「あるはず」の判定は GitHub Pages の配信に合わせる（大文字小文字を区別、クエリ文字列は無視、
ディレクトリは index.html があれば可）。

  python3 _automation/check_links.py            # 集計を表示
  python3 _automation/check_links.py --json out.json   # 全件を JSON に書き出す
  python3 _automation/check_links.py --strict   # 壊れた参照が1件でもあれば終了コード1
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_HOSTS = {
    "www.malpractice-committee.tech.server-on.net",
    "malpractice-committee.tech.server-on.net",
}
# Jetpack の画像 CDN。`i0.wp.com/<元ホスト>/<パス>` の形で元サイトの画像を中継する。
PHOTON_HOSTS = {"i0.wp.com", "i1.wp.com", "i2.wp.com", "i3.wp.com"}
SKIP_SCHEMES = ("data:", "mailto:", "javascript:", "tel:", "about:", "blob:")

# (タグ, 属性) -> 参照の種類
URL_ATTRS = {
    ("img", "src"): "img",
    ("img", "data-src"): "img",
    ("img", "data-lazy-src"): "img",
    ("amp-img", "src"): "img",
    ("source", "src"): "img",
    ("video", "src"): "media",
    ("video", "poster"): "img",
    ("audio", "src"): "media",
    ("script", "src"): "script",
    ("amp-iframe", "src"): "iframe",
    ("iframe", "src"): "iframe",
    ("a", "href"): "a",
    ("area", "href"): "a",
    ("form", "action"): "form",
}
SRCSET_ATTRS = {
    ("img", "srcset"), ("img", "data-srcset"), ("img", "data-lazy-srcset"),
    ("amp-img", "srcset"), ("source", "srcset"),
}
# link は rel によって意味が変わる。読み込まれるものだけを資産として扱う。
LINK_ASSET_RELS = {"stylesheet", "icon", "shortcut", "apple-touch-icon",
                   "apple-touch-icon-precomposed", "preload", "manifest"}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
CSS_IMPORT = re.compile(r"@import\s+(['\"])(.*?)\1", re.I)


def tracked_files():
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--cached", "--others",
                          "--exclude-standard"],
                         check=True, capture_output=True).stdout
    files = [p for p in out.decode("utf-8").split("\0") if p]
    return [p for p in files if os.path.exists(os.path.join(ROOT, p))]


class Refs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []      # (種類, URL)
        self.base = None
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "base" and a.get("href"):
            self.base = a["href"]
        if tag == "style":
            self._in_style = True
        if tag == "link" and a.get("href"):
            rels = set(a.get("rel", "").lower().split())
            if rels & LINK_ASSET_RELS:
                self.refs.append(("link", a["href"]))
            else:
                self.refs.append(("link-meta", a["href"]))
        if tag == "meta" and a.get("content"):
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:image", "og:image:secure_url", "twitter:image",
                       "msapplication-tileimage"):
                self.refs.append(("meta-image", a["content"]))
        for (t, attr), kind in URL_ATTRS.items():
            if t == tag and a.get(attr):
                self.refs.append((kind, a[attr]))
        for (t, attr) in SRCSET_ATTRS:
            if t == tag and a.get(attr):
                for cand in a[attr].split(","):
                    cand = cand.strip().split()
                    if cand:
                        self.refs.append(("srcset", cand[0]))
        if a.get("style"):
            for m in CSS_URL.finditer(a["style"]):
                self.refs.append(("css-url", m.group(2)))

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            for m in CSS_URL.finditer(data):
                self.refs.append(("css-url", m.group(2)))
            for m in CSS_IMPORT.finditer(data):
                self.refs.append(("css-url", m.group(2)))


def css_refs(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    refs = [("css-url", m.group(2)) for m in CSS_URL.finditer(text)]
    refs += [("css-url", m.group(2)) for m in CSS_IMPORT.finditer(text)]
    return refs


class Site:
    def __init__(self, files):
        self.files = set(files)
        self.dirs = set()
        for f in files:
            d = os.path.dirname(f)
            while d:
                self.dirs.add(d)
                d = os.path.dirname(d)

    def exists(self, path):
        """GitHub Pages が 200（または / への 301）で返すパスか。"""
        path = path.strip("/")
        if path == "":
            return "index.html" in self.files
        if path in self.files:
            return True
        if path in self.dirs:
            return (path + "/index.html") in self.files
        return (path + ".html") in self.files


def classify(url, src_file, base):
    """-> (区分, 値)。区分は skip / external / photon / internal。"""
    url = url.strip()
    if not url or url.startswith("#") or url.lower().startswith(SKIP_SCHEMES):
        return "skip", None
    if "{{" in url or "<%" in url:
        return "skip", None
    try:
        parts = urlsplit(url)
    except ValueError:
        return "invalid", url
    host = (parts.hostname or "").lower()
    if parts.scheme and parts.scheme not in ("http", "https"):
        return "skip", None
    if host:
        if host in PHOTON_HOSTS:
            segs = parts.path.lstrip("/").split("/", 1)
            if segs[0].lower() in SITE_HOSTS:
                return "photon", "/" + (segs[1] if len(segs) > 1 else "")
            return "external", host
        if host not in SITE_HOSTS:
            return "external", host
        return "internal", parts.path or "/"
    path = parts.path
    if not path:           # "?query" だけ、など
        return "skip", None
    if path.startswith("/"):
        return "internal", path
    base_dir = os.path.dirname(src_file)
    if base:
        b = urlsplit(base)
        if b.hostname and b.hostname.lower() not in SITE_HOSTS:
            return "external", b.hostname.lower()
        base_dir = os.path.dirname(b.path.lstrip("/")) if b.path else ""
    return "internal", "/" + os.path.normpath(os.path.join(base_dir, path)).replace(os.sep, "/")


def bucket(path):
    """壊れた参照のパスを、原因が同じもの同士でまとめるための分類。"""
    p = path.strip("/")
    if re.search(r"wp-content/uploads/wordpress-popular-posts/", p):
        return "uploads: 人気記事のサムネイル"
    if p.startswith("wp-content/uploads/"):
        if re.search(r"-\d+x\d+\.(jpe?g|png|gif|webp)$", p, re.I):
            return "uploads: リサイズ版の画像"
        return "uploads: 画像"
    if p.startswith("wp-content/themes/"):
        return "wp-content/themes"
    if p.startswith("wp-content/plugins/"):
        return "wp-content/plugins"
    if p.startswith("wp-content/"):
        return "wp-content: その他"
    if p.startswith("wp-includes/"):
        return "wp-includes"
    if p.startswith("wp-json"):
        return "wp-json"
    if re.match(r"(wp-login|wp-admin|xmlrpc|wp-comments-post|wp-trackback)", p):
        return "WordPress の動的エンドポイント"
    if p == "feed" or p.endswith("/feed") or "/feed/" in p + "/":
        return "フィード"
    if p.startswith("category/"):
        return "カテゴリページ"
    if p.startswith("tag/"):
        return "タグページ"
    if p.startswith("author/"):
        return "著者ページ"
    if p.startswith("page/"):
        return "一覧のページ送り"
    if re.search(r"(^|/)amp$", p):
        return "AMP 版"
    if re.search(r"/(page|comment-page)-?\d*", p):
        return "記事内のページ送り・コメントページ"
    if re.match(r"\d{4}(/\d{2})?(/\d{2})?$", p):
        return "日付アーカイブ"
    if "." in os.path.basename(p):
        return "その他のファイル"
    return "記事・固定ページ"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="壊れた参照の全件を書き出すファイル")
    ap.add_argument("--strict", action="store_true", help="壊れた参照があれば終了コード1")
    ap.add_argument("--examples", type=int, default=3, help="種類ごとの代表例の数")
    args = ap.parse_args()

    files = tracked_files()
    site = Site(files)
    counts = collections.Counter()
    broken = []            # (種類, 分類, 参照元, 元のURL, 解決後のパス)
    photon = collections.Counter()
    external = collections.Counter()
    invalid = []
    scanned = collections.Counter()

    for f in files:
        low = f.lower()
        if low.endswith((".html", ".htm")):
            scanned["html"] += 1
            p = Refs()
            with open(os.path.join(ROOT, f), encoding="utf-8", errors="replace") as fh:
                p.feed(fh.read())
            refs, base = p.refs, p.base
        elif low.endswith(".css"):
            scanned["css"] += 1
            with open(os.path.join(ROOT, f), encoding="utf-8", errors="replace") as fh:
                refs, base = css_refs(fh.read()), None
        else:
            continue
        for kind, url in refs:
            where, val = classify(url, f, base)
            counts[(kind, where)] += 1
            if where == "invalid":
                invalid.append((f, url))
            elif where == "external":
                external[(kind, val)] += 1
            elif where in ("internal", "photon"):
                path = unquote(val)
                ok = site.exists(path)
                if where == "photon":
                    photon[(kind, "実体あり" if ok else "実体なし")] += 1
                if not ok:
                    broken.append((kind, bucket(path), f, url, path))

    print(f"走査: HTML {scanned['html']} 件 / CSS {scanned['css']} 件 / "
          f"リポジトリ内のファイル {len(files)} 件")
    print()
    print("== 参照の内訳（種類 × 向き先）")
    for (kind, where), n in sorted(counts.items()):
        print(f"  {kind:11s} {where:9s} {n:7d}")
    print()
    print(f"== 壊れているサイト内参照: {len(broken)} 件 "
          f"（重複を除いた参照先 {len({b[4] for b in broken})} 件）")
    groups = collections.defaultdict(list)
    for b in broken:
        groups[(b[0], b[1])].append(b)
    for (kind, bk), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        targets = collections.Counter(i[4] for i in items)
        pages = len({i[2] for i in items})
        print(f"  {len(items):6d} 件  {kind:10s} {bk}  "
              f"（参照先 {len(targets)} 種 / 参照元 {pages} ファイル）")
        for t, n in targets.most_common(args.examples):
            src = next(i[2] for i in items if i[4] == t)
            print(f"           {n:5d}x {t}   ← {src}")
    print()
    print("== 画像 CDN（i0.wp.com）経由のサイト内画像")
    for (kind, st), n in sorted(photon.items()):
        print(f"  {kind:10s} {st} {n:6d}")
    print()
    print("== 外部ホスト（読み込まれる資産のみ。a href は除く）上位")
    asset = collections.Counter()
    for (kind, host), n in external.items():
        if kind not in ("a", "link-meta", "form"):
            asset[(kind, host)] += n
    for (kind, host), n in asset.most_common(40):
        print(f"  {n:6d}  {kind:10s} {host}")
    if invalid:
        print()
        print(f"== 解釈できない URL: {len(invalid)} 件")
        for f, u in invalid[:5]:
            print(f"  {u!r}  ← {f}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump([dict(kind=b[0], bucket=b[1], source=b[2], url=b[3], path=b[4])
                       for b in broken], fh, ensure_ascii=False, indent=1)
    if args.strict and broken:
        sys.exit(1)


if __name__ == "__main__":
    main()
