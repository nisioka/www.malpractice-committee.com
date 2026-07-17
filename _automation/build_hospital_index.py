#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""病院索引（hospital-info）を全網羅で再生成する。

manifest から「記事のある病院カテゴリ」を全て集め、五十音（あ行〜わ行＋その他）で
グルーピングして、各病院→カテゴリページへのリンク＋記事件数＋記事一覧リンクを出力する。
既存 hospital-info/index.html のテーマ定型はそのまま流用し、本文(section.post-content)だけ
差し替える。旧 nisioka.github.io リンクも正規ホストへ是正される。

五十音判定に pykakasi を使う（未導入なら pip 導入を促し「その他」に集約）。
"""
import html as htmllib
import json
import pathlib
import re
import sys

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "hospital-info" / "index.html"
MANIFEST = ROOT / "_automation" / "manifest.json"

# 病院ではないトピック/組織カテゴリ（索引から除外）
NON_HOSPITAL = {"others", "mhlw", "medical-accident-investigation-system",
                "jcqhc", "notice", "case-study-introduction"}

ROWS = [
    ("あ行", "あいうえおぁぃぅぇぉ"),
    ("か行", "かきくけこがぎぐげご"),
    ("さ行", "さしすせそざじずぜぞ"),
    ("た行", "たちつてとだぢづでどっ"),
    ("な行", "なにぬねの"),
    ("は行", "はひふへほばびぶべぼぱぴぷぺぽ"),
    ("ま行", "まみむめも"),
    ("や行", "やゆよゃゅょ"),
    ("ら行", "らりるれろ"),
    ("わ行", "わをん"),
]
CHAR_TO_ROW = {c: name for name, chars in ROWS for c in chars}


def get_reading():
    try:
        import pykakasi
        kks = pykakasi.kakasi()

        def yomi(name):
            return "".join(r["hira"] for r in kks.convert(name))
        return yomi
    except Exception:
        return None


def row_of(reading: str) -> str:
    for ch in reading:
        if ch in CHAR_TO_ROW:
            return CHAR_TO_ROW[ch]
    return "その他"


def esc(s):
    return htmllib.escape(s, quote=False)


def attr(s):
    """属性値用エスケープ（" ' & < > をすべて実体参照化）。"""
    return htmllib.escape(s, quote=True)


# 五十音ジャンプナビの1文字ラベル
ROW_LABEL = {
    "あ行": "あ", "か行": "か", "さ行": "さ", "た行": "た", "な行": "な",
    "は行": "は", "ま行": "ま", "や行": "や", "ら行": "ら", "わ行": "わ",
    "その他": "他",
}

# 索引ページ専用スタイル（.hidx 配下にスコープ）
HIDX_STYLE = """<style>
.hidx{--hidx-accent:#0b6ea8;line-height:1.7}
.hidx .hidx-summary{margin:.2em 0 1em;color:#444}
.hidx .hidx-summary strong{color:var(--hidx-accent)}
.hidx-tools{position:sticky;top:0;z-index:5;background:#fff;
  padding:.5em 0 .4em;margin-bottom:1em;border-bottom:1px solid #e2e2e2}
.hidx-tools input[type=search]{width:100%;box-sizing:border-box;
  padding:.6em .8em;font-size:16px;border:1px solid #bbb;border-radius:8px}
.hidx-nav{display:flex;flex-wrap:wrap;gap:.35em;margin-top:.5em}
.hidx-nav a{display:inline-block;min-width:2.1em;text-align:center;
  padding:.3em .1em;border:1px solid #cfd8dd;border-radius:6px;
  color:var(--hidx-accent);text-decoration:none;font-weight:600;font-size:.95em}
.hidx-nav a:hover{background:var(--hidx-accent);color:#fff;border-color:var(--hidx-accent)}
.hidx-row{margin:0 0 1.4em}
.hidx-row h2{scroll-margin-top:64px;border-left:5px solid var(--hidx-accent);
  padding:.15em .55em;margin:.2em 0 .5em;font-size:1.15em;background:#f3f7fa}
.hidx-list{list-style:none;margin:0;padding:0}
.hidx-item{padding:.4em .2em;border-bottom:1px dotted #e6e6e6}
.hidx-item.is-hidden{display:none}
.hidx-hosp{font-weight:600}
.hidx-count{display:inline-block;margin-left:.45em;padding:0 .5em;
  font-size:.78em;line-height:1.7;color:#555;background:#eef2f4;border-radius:10px}
.hidx-sep{color:#bbb;margin:0 .4em}
.hidx-art{color:#333}
.hidx-item details>summary{cursor:pointer;list-style:none;display:flex;
  align-items:center;gap:.1em}
.hidx-item details>summary::-webkit-details-marker{display:none}
.hidx-item details>summary::before{content:"\\25b6";color:#9aa;font-size:.7em;
  margin-right:.5em;transition:transform .15s}
.hidx-item details[open]>summary::before{transform:rotate(90deg)}
.hidx-sublist{list-style:none;margin:.4em 0 .2em;padding:.2em 0 .2em 1.9em;
  border-left:2px solid #eef2f4}
.hidx-sublist li{padding:.2em 0}
.hidx-noresult{display:none;padding:1em;color:#a33;background:#fff5f5;
  border:1px solid #f0caca;border-radius:8px}
.hidx.is-searching .hidx-noresult.is-visible{display:block}
@media (max-width:600px){.hidx-nav a{min-width:1.9em;padding:.35em 0}}
</style>
"""

# 絞り込み用スクリプト（JS無効でも一覧はそのまま閲覧可能）
HIDX_SCRIPT = """<script>
(function(){
  var root=document.querySelector('.hidx');
  if(!root)return;
  var q=document.getElementById('hidx-q');
  var items=[].slice.call(root.querySelectorAll('.hidx-item'));
  var rows=[].slice.call(root.querySelectorAll('.hidx-row'));
  var none=root.querySelector('.hidx-noresult');
  function norm(s){return (s||'').toLowerCase();}
  function apply(){
    var k=norm(q.value).trim();
    var searching=k.length>0;
    root.classList.toggle('is-searching',searching);
    var hit=0;
    items.forEach(function(it){
      var m=!searching||norm(it.getAttribute('data-text')).indexOf(k)>=0;
      it.classList.toggle('is-hidden',!m);
      if(m)hit++;
      var d=it.querySelector('details');
      if(d&&searching)d.open=true;
      else if(d&&!searching)d.open=false;
    });
    rows.forEach(function(r){
      var any=r.querySelector('.hidx-item:not(.is-hidden)');
      r.style.display=any?'':'none';
    });
    if(none)none.classList.toggle('is-visible',searching&&hit===0);
  }
  q.addEventListener('input',apply);
})();
</script>
"""


def build_content(manifest, yomi) -> str:
    cats = manifest["categories"]
    posts = manifest["posts"]
    by_cat = {}
    for p in posts:
        by_cat.setdefault(p["category_slug"], []).append(p)

    # 病院エントリを構築
    entries = []
    for slug, plist in by_cat.items():
        if slug in NON_HOSPITAL or not slug:
            continue
        name = cats.get(slug, slug)
        reading = yomi(name) if yomi else ""
        entries.append({
            "slug": slug, "name": name, "reading": reading,
            "row": row_of(reading) if yomi else "その他",
            "posts": sorted(plist, key=lambda x: x["post_id"], reverse=True),
        })

    # 行ごとにまとめ、読み順にソート
    order = [r[0] for r in ROWS] + ["その他"]
    grouped = {r: [] for r in order}
    for e in entries:
        grouped[e["row"]].append(e)
    for r in grouped:
        grouped[r].sort(key=lambda e: (e["reading"] or e["slug"], e["slug"]))

    total_h = len(entries)
    total_a = sum(len(e["posts"]) for e in entries)
    used_rows = [r for r in order if grouped[r]]

    out = ["      \n      \n", '<div class="hidx">\n', HIDX_STYLE]
    out.append(
        '<p class="hidx-summary">医療ミス・医療過誤・医療事故を報じた病院の索引です。'
        f'全<strong>{total_h}</strong>病院・<strong>{total_a}</strong>記事を五十音順にまとめています。'
        '病院名で記事一覧へ、記事名で本文へ移動できます。</p>\n')

    # 検索フィルタ＋五十音ジャンプナビ（sticky）
    out.append('<div class="hidx-tools">\n')
    out.append('<input type="search" id="hidx-q" '
               'placeholder="病院名・記事タイトルで絞り込み…" '
               'aria-label="索引を絞り込み" autocomplete="off">\n')
    out.append('<nav class="hidx-nav" aria-label="五十音ジャンプ">\n')
    for row in used_rows:
        out.append(f'<a href="#row-{row}">{ROW_LABEL[row]}</a>')
    out.append('\n</nav>\n</div>\n')
    out.append('<p class="hidx-noresult">該当する病院・記事が見つかりませんでした。'
               'キーワードを変えてお試しください。</p>\n')

    for row in used_rows:
        out.append(f'<div class="hidx-row" id="row-{row}">\n<h2>{row}</h2>\n')
        out.append('<ul class="hidx-list">\n')
        for e in grouped[row]:
            cat_url = f"{sitelib.ORIGIN}/category/{e['slug']}/"
            n = len(e["posts"])
            # 検索対象テキスト（病院名＋読み＋全記事タイトル）
            search_text = " ".join(
                [e["name"], e.get("reading", "")] + [p["title"] for p in e["posts"]])
            out.append(f'<li class="hidx-item" data-text="{attr(search_text)}">\n')
            if n == 1:
                # 1記事の病院は入れ子をやめて1行に平坦化
                p = e["posts"][0]
                art_url = f"{sitelib.ORIGIN}/{p['slug']}/"
                out.append(
                    f'<a class="hidx-hosp" href="{cat_url}">{esc(e["name"])}</a>'
                    f'<span class="hidx-count">{n}件</span>'
                    f'<span class="hidx-sep">—</span>'
                    f'<a class="hidx-art" href="{art_url}">{esc(p["title"])}</a>\n')
            else:
                # 複数記事は details で折りたたみ（初期は閉じる）
                out.append(
                    '<details>\n<summary>'
                    f'<a class="hidx-hosp" href="{cat_url}">{esc(e["name"])}</a>'
                    f'<span class="hidx-count">{n}件</span>'
                    '</summary>\n<ul class="hidx-sublist">\n')
                for p in e["posts"]:
                    art_url = f"{sitelib.ORIGIN}/{p['slug']}/"
                    out.append(f'<li><a href="{art_url}">{esc(p["title"])}</a></li>\n')
                out.append('</ul>\n</details>\n')
            out.append('</li>\n')
        out.append('</ul>\n</div>\n')

    out.append(HIDX_SCRIPT)
    out.append('</div>\n')
    return "".join(out)


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    yomi = get_reading()
    if yomi is None:
        print("注意: pykakasi 未導入のため五十音分類できません。"
              "`pip install pykakasi` を推奨（全病院を『その他』に集約します）。")

    content = build_content(manifest, yomi)
    html = PAGE.read_text(encoding="utf-8")
    new_html, n = re.subn(
        r'(<section class="post-content" itemprop="text">).*?(</section>)',
        lambda m: m.group(1) + "\n" + content + "      " + m.group(2),
        html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("section.post-content が見つからない")
    PAGE.write_text(new_html, encoding="utf-8")
    print(f"再生成: hospital-info/index.html")


if __name__ == "__main__":
    sys.exit(main())
