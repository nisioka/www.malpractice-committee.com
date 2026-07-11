#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""トップ + ページ送り（page/N）の一覧を再生成する（非破壊シフト方式）。

背景:
  既存サイトのページ送りは page/11・page/12 が欠落した既存バグを持つ。番号を振り直すと
  全記事URLが変わり SEO を壊すため、**ページ番号体系と各ページのページ送りnavには触れず**、
  「各ページのカード列を1件ずつ後ろへずらす」だけの非破壊更新にする。

方針:
  掲載順は公開済みページの実体を正とする。存在するページ番号を昇順に並べ
  ([1,2..10,13..30] のように欠番はそのまま)、各ページからカードを順に集約 → 新規カードを
  先頭に差し込み → 10件ずつ再チャンク → 各ページの prefix / pagination(suffix) は元のまま、
  カード列だけ差し替えて書き戻す。

  回帰テスト: 新規0件なら全ページがバイト単位で元に戻る（--check）。

使い方:
  python3 _automation/rebuild_listings.py [new_articles.json] [--check]
"""
import json
import pathlib
import re
import sys

import sitelib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PER_PAGE = 10

WRAP_RE = re.compile(r'(<div class="post-loop-wrap">)(.*?)(</div><!-- /post-loop-wrap -->)', re.S)
CARD_RE = re.compile(r'<article id="post-\d+".*?</article>', re.S)
CLASS_RE = re.compile(r'(<article id="post-\d+" class="[^"]*)"')


def page_path(n: int) -> pathlib.Path:
    return ROOT / "index.html" if n == 1 else ROOT / "page" / str(n) / "index.html"


def existing_pages():
    nums = [1]
    for d in (ROOT / "page").iterdir():
        if d.is_dir() and d.name.isdigit() and (d / "index.html").is_file():
            nums.append(int(d.name))
    return sorted(set(nums))


def split_wrap(html: str):
    """post-loop-wrap を分解。

    gaps[i] = カード間の文字列（gaps[0]=先頭カード前, gaps[len(cards)]=末尾カード後=pagination等）。
    カード間に固定モジュール（module--share等）が挟まる場合も gaps に保持され、位置ごとに復元される。
    """
    m = WRAP_RE.search(html)
    if not m:
        raise SystemExit("post-loop-wrap が見つからない")
    inner = m.group(2)
    spans = [(mm.start(), mm.end(), mm.group(0)) for mm in CARD_RE.finditer(inner)]
    cards = [s[2] for s in spans]
    gaps = [inner[:spans[0][0]]]  # prefix
    for a, b in zip(spans, spans[1:]):
        gaps.append(inner[a[1]:b[0]])
    gaps.append(inner[spans[-1][1]:])  # suffix
    # 標準セパレータ = 最頻の中間ギャップ
    mids = gaps[1:-1]
    sep = max(set(mids), key=mids.count) if mids else "\n\n        "
    # 標準と異なる中間ギャップ（＝固定モジュール等）を序数付きで保持
    specials = {i: g for i, g in enumerate(gaps) if 0 < i < len(gaps) - 1 and g != sep}
    return {
        "before": html[:m.start()], "open": m.group(1), "prefix": gaps[0], "cards": cards,
        "sep": sep, "specials": specials, "suffix": gaps[-1], "close": m.group(3),
        "after": html[m.end():],
    }


def join_cards(cards, sep, prefix, specials, suffix):
    out = [prefix]
    for i, c in enumerate(cards):
        if i > 0:
            out.append(specials.get(i, sep))
        out.append(c)
    out.append(suffix)
    return "".join(out)


def strip_firstpost(card: str) -> str:
    return card.replace(' firstpost"', '"', 1)


def add_firstpost(card: str) -> str:
    return CLASS_RE.sub(r'\1 firstpost"', card, count=1)


def main(argv):
    check = "--check" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    new_data = []
    if not check:
        # 引数優先、無ければ generate_article の引き継ぎファイルを既定で使う
        src = pathlib.Path(args[0]) if args else (ROOT / "_automation" / "_generated.json")
        if src.is_file():
            new_data = json.loads(src.read_text(encoding="utf-8"))
            if isinstance(new_data, dict):
                new_data = [new_data]

    pages = existing_pages()
    parts = {n: split_wrap(page_path(n).read_text(encoding="utf-8")) for n in pages}

    # 全カードを掲載順に集約
    all_cards = []
    for n in pages:
        all_cards.extend(parts[n]["cards"])

    # 新規カード（先頭へ）+ 既存(firstpost除去)。先頭のみ firstpost 付与。
    new_cards = [sitelib.build_list_card(a, first=False) for a in new_data]
    ordered = new_cards + [strip_firstpost(c) for c in all_cards]
    if ordered:
        ordered[0] = add_firstpost(ordered[0])

    # 既存ページ数ぶんの10件チャンクに割り当て（末尾ページのみ 10件超過を許容）
    total = len(ordered)
    n_pages = len(pages)
    chunks = [ordered[i * PER_PAGE:(i + 1) * PER_PAGE] for i in range(n_pages)]
    overflow = ordered[n_pages * PER_PAGE:]
    if overflow:
        # ページ数を増やさない方針: あふれ分は最終ページに載せる（nav不変を維持）
        chunks[-1].extend(overflow)

    mismatches = 0
    for i, n in enumerate(pages):
        p = parts[n]
        body = join_cards(chunks[i], p["sep"], p["prefix"], p["specials"], p["suffix"])
        new_html = p["before"] + p["open"] + body + p["close"] + p["after"]
        path = page_path(n)
        if check:
            if new_html != path.read_text(encoding="utf-8"):
                mismatches += 1
                _first_diff(path, path.read_text(encoding="utf-8"), new_html)
        else:
            path.write_text(new_html, encoding="utf-8")

    if check:
        print("CHECK:", "OK 全ページ既存とバイト一致" if mismatches == 0 else f"NG {mismatches}ページ差分")
        return 1 if mismatches else 0
    print(f"再生成: {n_pages}ページ / 全{total}カード（新規{len(new_cards)}件, 先頭ページに追加）")
    return 0


def _first_diff(path, a, b):
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            print(f"  差分 {path.relative_to(ROOT)} @ {i}: 既存{a[max(0,i-30):i+30]!r} / 生成{b[max(0,i-30):i+30]!r}")
            return
    if len(a) != len(b):
        print(f"  長さ差 {path.relative_to(ROOT)}: {len(a)} vs {len(b)}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
