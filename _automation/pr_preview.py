#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRで追加/変更された HTML ページを実CSS付きでスクリーンショットする。

GitHub Actions の pr-preview.yml から呼ばれるが、単体でもローカル実行できる。

処理:
  1. `git diff --name-only --diff-filter=AM <base>...HEAD -- '*.html'` で
     追加(A)・変更(M)された HTML を検出（削除は除外）。固定ページ決め打ちをしないので
     今後の新記事も自動的に対象になる。
  2. リポジトリ直下をローカル HTTP サーバで配信。
  3. 各対象 HTML の絶対ホスト（本番URL）を http://localhost:PORT に置換したコピーを作り、
     ヘッドレス Chromium でフルページ描画 → PNG 保存（実CSS/画像/フォントが当たる）。
  4. out_dir に PNG を吐き、標準出力に「file<TAB>slug/path」の一覧を出す。

使い方:
  python3 _automation/pr_preview.py --base origin/master --out /tmp/previews
環境変数:
  CHROME_BIN … chromium/chrome 実行ファイル（未設定なら既知パスを探索）
  PREVIEW_MAX … 撮影する最大ページ数（既定 25。超過分はスキップして警告）
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
    # PLAYWRIGHT パス配下を総当り
    for base in ("/opt/pw-browsers",):
        p = pathlib.Path(base)
        if p.is_dir():
            hits = list(p.glob("chromium-*/chrome-linux/chrome"))
            if hits:
                return str(hits[0])
    raise SystemExit("Chromium/Chrome が見つからない（CHROME_BIN を設定してください）")


def changed_html(base: str) -> list[str]:
    """追加(A)を先頭、変更(M)を後ろに並べて返す。

    ページ送り(page/N)は「カードが1件ずつずれるだけ」で見た目の確認価値が低く枚数も多いため
    プレビュー対象から除外する（新記事・カテゴリ・トップ・病院索引に集中）。AMP/モバイル複製と
    ツール自身のテンプレも除外。
    """
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


def start_server(port_holder: list):
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", 0), lambda *a, **k: handler(*a, directory=str(ROOT), **k))
    port_holder.append(httpd.server_address[1])
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def label_for(path: str) -> str:
    """index.html を除いた見やすいスラッグ表示。"""
    p = path[:-len("index.html")] if path.endswith("index.html") else path
    return "/" + p.strip("/") + "/" if p.strip("/") else "/ (トップ)"


def screenshot(chrome: str, url: str, out_png: pathlib.Path) -> bool:
    cmd = [
        chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--virtual-time-budget=10000",
        "--window-size=1280,3400", f"--screenshot={out_png}", url,
    ]
    # タイムアウト/描画失敗は当該ページを飛ばして継続（1枚のハングで全体を落とさない）
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
            src = ROOT / rel
            if not src.is_file():
                continue
            html = src.read_text(encoding="utf-8", errors="ignore")
            html = html.replace(ORIGIN, f"http://127.0.0.1:{port}")
            tmp = out_dir / f"_render_{i}.html"
            tmp.write_text(html, encoding="utf-8")
            png = out_dir / f"page_{i:02d}.png"
            ok = screenshot(chrome, tmp.as_uri(), png)
            tmp.unlink(missing_ok=True)
            if ok:
                manifest.append((png.name, rel, label_for(rel)))
                print(f"撮影OK: {rel} -> {png.name}", file=sys.stderr)
            else:
                print(f"撮影失敗: {rel}", file=sys.stderr)
    finally:
        httpd.shutdown()

    # 標準出力: PNG名<TAB>相対パス<TAB>表示ラベル
    for png, rel, label in manifest:
        print(f"{png}\t{rel}\t{label}")
    if dropped:
        print(f"__DROPPED__\t{len(dropped)}\t(上限{limit}超過のため未撮影)", file=sys.stderr)
    (out_dir / "manifest.tsv").write_text(
        "".join(f"{p}\t{r}\t{l}\n" for p, r, l in manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
