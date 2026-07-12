#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRで追加/変更された HTML ページを実CSS付きでスクリーンショットする。

GitHub Actions の pr-preview.yml から呼ばれるが、単体でもローカル実行できる。

処理:
  1. `git diff --name-only --diff-filter=AM <base>...HEAD -- '*.html'` で
     追加(A)・変更(M)された HTML を検出（削除は除外）。固定ページ決め打ちをしないので
     今後の新記事も自動的に対象になる。ページ送り(page/N)は枚数が多く価値が低いため除外。
  2. リポジトリ直下をローカル HTTP サーバで配信。配信時に本番ホストをローカルホストへ
     書き換える（**ページ本体もサブリソースも同一オリジン http://127.0.0.1 になるので、
     CORS制約のあるwebフォント= FontAwesome等も正しく適用され豆腐化しない**）。
  3. 各対象ページを http://127.0.0.1:PORT/<path> としてヘッドレス Chromium でフルページ描画。
  4. 各ページから出典リンク（出典：<a href=…>）を抽出。
  5. out_dir に PNG と manifest.tsv（PNG / パス / 表示ラベル / 出典URL / 出典名）を吐く。

使い方:
  python3 _automation/pr_preview.py --base origin/master --out /tmp/previews
環境変数:
  CHROME_BIN … chromium/chrome 実行ファイル（未設定なら既知パスを探索）
  PREVIEW_MAX … 撮影する最大ページ数（既定 12。超過分はスキップして警告）
"""
import argparse
import http.server
import os
import pathlib
import re
import socketserver
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORIGIN = "https://www.malpractice-committee.tech.server-on.net"
SOURCE_RE = re.compile(r'出典：<a href="([^"]+)"[^>]*>([^<]+)</a>')

CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and pathlib.Path(c).is_file():
            return c
    for base in ("/opt/pw-browsers",):
        p = pathlib.Path(base)
        if p.is_dir():
            hits = list(p.glob("chromium-*/chrome-linux/chrome"))
            if hits:
                return str(hits[0])
    raise SystemExit("Chromium/Chrome が見つからない（CHROME_BIN を設定してください）")


def changed_html(base: str) -> list[str]:
    """追加(A)を先頭、変更(M)を後ろに並べて返す。ページ送り・AMP・テンプレは除外。"""
    def diff(flt):
        cmd = ["git", "diff", "--name-only", f"--diff-filter={flt}", f"{base}...HEAD", "--", "*.html"]
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        return [f for f in out.stdout.splitlines() if f.strip()]

    skip = ("_automation/", "/amp/", "Pnoamp=")

    def keep(f):
        return not any(s in f for s in skip) and not re.match(r"page/\d+/", f)

    added = [f for f in diff("A") if keep(f)]
    modified = [f for f in diff("M") if keep(f)]
    return added + modified


class RewriteHandler(http.server.SimpleHTTPRequestHandler):
    """HTMLは本番ホストをアクセス中のローカルホストへ書き換えて配信（同一オリジン化）。"""

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *a):  # サーバログを抑制
        pass

    def do_GET(self):
        path = self.translate_path(self.path)
        p = pathlib.Path(path)
        if p.is_dir():
            p = p / "index.html"
        if p.suffix.lower() in (".html", ".htm") and p.is_file():
            host = self.headers.get("Host", "127.0.0.1")
            body = p.read_text(encoding="utf-8", errors="ignore").replace(ORIGIN, f"http://{host}")
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                pass
            return
        super().do_GET()


def start_server(port_holder: list):
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), RewriteHandler)
    httpd.daemon_threads = True
    port_holder.append(httpd.server_address[1])
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def label_for(path: str) -> str:
    p = path[:-len("index.html")] if path.endswith("index.html") else path
    return "/" + p.strip("/") + "/" if p.strip("/") else "/ (トップ)"


def source_of(rel: str):
    """記事ページから出典リンク (URL, 名称) を抽出。無ければ ('', '')。"""
    f = ROOT / rel
    if not f.is_file():
        return "", ""
    m = SOURCE_RE.search(f.read_text(encoding="utf-8", errors="ignore"))
    return (m.group(1), m.group(2)) if m else ("", "")


def screenshot(chrome: str, url: str, out_png: pathlib.Path) -> bool:
    cmd = [
        chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--virtual-time-budget=12000",
        "--window-size=1280,3400", f"--screenshot={out_png}", url,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        print(f"撮影タイムアウト/失敗: {url} ({e})", file=sys.stderr)
        return False
    return out_png.is_file() and out_png.stat().st_size > 0


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("PREVIEW_BASE", "origin/master"))
    ap.add_argument("--out", default="/tmp/previews")
    ap.add_argument("--files", nargs="*", help="明示指定（省略時は git diff から検出）")
    args = ap.parse_args(argv[1:])

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = args.files or changed_html(args.base)
    if not files:
        print("変更されたHTMLページなし（プレビュー対象なし）", file=sys.stderr)
        return 0
    limit = int(os.environ.get("PREVIEW_MAX", "12"))
    dropped = files[limit:]
    files = files[:limit]

    chrome = find_chrome()
    port_holder: list = []
    httpd = start_server(port_holder)
    port = port_holder[0]

    manifest = []
    try:
        for i, rel in enumerate(files):
            if not (ROOT / rel).is_file():
                continue
            url = f"http://127.0.0.1:{port}/{rel}"
            png = out_dir / f"page_{i:02d}.png"
            if screenshot(chrome, url, png):
                src_url, src_name = source_of(rel)
                manifest.append((png.name, rel, label_for(rel), src_url, src_name))
                print(f"撮影OK: {rel} -> {png.name}", file=sys.stderr)
            else:
                print(f"撮影失敗: {rel}", file=sys.stderr)
    finally:
        httpd.shutdown()

    for row in manifest:
        print("\t".join(row))
    if dropped:
        print(f"__DROPPED__\t{len(dropped)}\t(上限{limit}超過のため未撮影)", file=sys.stderr)
    (out_dir / "manifest.tsv").write_text(
        "".join("\t".join(r) + "\n" for r in manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
