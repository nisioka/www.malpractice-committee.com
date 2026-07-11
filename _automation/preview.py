#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ローカルでサイト全体を実CSS付きでブラウズするための簡易プレビューサーバ。

サイトのHTMLは本番の絶対URL（https://www.malpractice-committee.tech.server-on.net/…）で
CSS・画像・リンクを参照しているため、そのままローカルで開いてもスタイルが当たらない。
このサーバは配信時に本番ホストをアクセス中のローカルホストへ動的に書き換えるので、
CSS/画像/内部リンクがすべてローカルの実ファイルに解決され、サイトを丸ごと回遊確認できる。

使い方:
  python3 _automation/preview.py            # http://localhost:8787 で起動
  python3 _automation/preview.py --port 9000
ブラウザで http://localhost:8787/ を開く（記事は /<slug>/ で見られる）。
"""
import argparse
import functools
import http.server
import pathlib
import socketserver

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORIGIN = "https://www.malpractice-committee.tech.server-on.net"


class RewriteHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def send_head(self):
        # HTML はメモリ上で書き換えて返す。それ以外(CSS/画像等)は通常配信。
        path = self.translate_path(self.path)
        p = pathlib.Path(path)
        if p.is_dir():
            p = p / "index.html"
        if p.suffix.lower() in (".html", ".htm") and p.is_file():
            host = self.headers.get("Host", f"localhost:{self.server.server_address[1]}")
            body = p.read_text(encoding="utf-8", errors="ignore").replace(ORIGIN, f"http://{host}")
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self._body = data
            return None  # copyfile はしない
        return super().send_head()

    def do_GET(self):
        head = self.send_head()
        if head is None and hasattr(self, "_body"):
            self.wfile.write(self._body)
            del self._body
        elif head:
            try:
                self.copyfile(head, self.wfile)
            finally:
                head.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    with socketserver.ThreadingTCPServer(("0.0.0.0", args.port), RewriteHandler) as httpd:
        print(f"プレビュー起動: http://localhost:{args.port}/  (Ctrl+C で停止)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n停止しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
