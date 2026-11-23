#!/usr/bin/env python3
"""構造化データ（JSON-LD）の著者・発行者を、サイト名「医療ミス調査会」の組織にする。

`<head>` の JSON-LD（`<script type="application/ld+json">`）は、著者・発行者として名前「管理者」の
Person を指していた。WordPress のときの投稿者の表示名がそのまま入った移行の名残で、「管理者」は
役職で名前ではない。WordPress 時代のページは、著者の `url` が実体の無い著者ページ
（`/author/fushigibana/`）を指してもいた。これをサイトの組織にそろえる（2026-11 のオーナー判断）。

1ブロックごとに次のように書き換える。ほかの項目と項目の並びは変えない。
- 名前「管理者」の Person のノードのうち最初の1つを、組織のノード
  `{"@type": "Organization", "@id": "<トップ>/#organization", "name": "医療ミス調査会", "url": "<トップ>/"}`
  に置き換え、残りの「管理者」の Person のノード（実体の無い著者ページを指すもの）は外す
- 外したノードを指していた参照（`author`・`publisher`・`creator`・`about` など、`{"@id": ...}` の形の
  もの）を、すべて組織のノードへの参照にする

JSON の書き方はブロックごとに元のままにする。WordPress（All in One SEO）が出したブロックは
`/` と日本語をエスケープした詰めた書き方、今の生成側（`sitelib.py`）が出したブロックは
エスケープしない書き方。書き換える前に、読み込んだ JSON を同じ書き方で書き戻すと元のバイト列に
戻ることを確かめ、戻らないブロックは触らずに「残した」として数える（終了コード 1）。
何度実行しても結果は同じ。

触らないもの:
- 「管理者」以外の Person（今は無い）
- 著者・発行者を持たない JSON-LD（`build_category.py` が作る病院ページなど）
- `wp-json/` の oEmbed の写し（`author_name` が「管理者」）。schema.org の構造化データではなく、
  ページの oEmbed の宣言が指す URL（`/wp-json/oembed/1.0/embed`）にも置かれていない。
  `wp-json/` は原則触らない
- 本文の中の「管理者」（「院長などの管理者」など）。記事の中身なので触らない

画面の著者欄と、それに付いていた microdata（`itemprop="author"`）は `remove_post_author.py` で
外してある。生成側（`sitelib.build_jsonld`）も同じ組織のノードを出すので、記事を足しても
「管理者」は入らない。

対象は Git が追跡している全 HTML。WordPress 時代の HTML を取り込み直したときは、
このスクリプトを掛け直す。

  python3 _automation/set_jsonld_organization.py --dry-run   # 件数だけ表示
  python3 _automation/set_jsonld_organization.py             # 書き換える
"""
import argparse
import collections
import json
import os
import re
import sys

import check_links as cl
import sitelib

OLD_NAME = "管理者"
ORG_ID = f"{sitelib.ORIGIN}/#organization"
ORG_NODE = sitelib.ORGANIZATION

JSONLD = re.compile(
    r'(<script type="application/ld\+json"[^>]*>)(\s*)(.*?)(\s*)(</script>)', re.S)


def dumps_wp(obj):
    """WordPress（PHP の json_encode）の書き方: 詰めて、`/` と非 ASCII をエスケープする。"""
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":")).replace("/", "\\/")


def dumps_py(obj):
    """今の生成側（sitelib.py・build_category.py）の書き方。"""
    return json.dumps(obj, ensure_ascii=False)


def is_old_person(node):
    return (isinstance(node, dict) and node.get("@type") == "Person"
            and node.get("name") == OLD_NAME)


def repoint(obj, old_ids, stats):
    """`{"@id": 旧ID}` の参照を、組織への参照に置き換える（入れ子もたどる）。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict) and set(v) == {"@id"} and v["@id"] in old_ids:
                obj[k] = {"@id": ORG_ID}
                stats[f"組織への参照に置き換えた {k}"] += 1
            else:
                repoint(v, old_ids, stats)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, dict) and set(v) == {"@id"} and v["@id"] in old_ids:
                obj[i] = {"@id": ORG_ID}
                stats["組織への参照に置き換えた (配列の要素)"] += 1
            else:
                repoint(v, old_ids, stats)


def fix_block(raw, stats):
    """1つの JSON-LD の中身を書き換える。書き換えないときは raw をそのまま返す。"""
    try:
        data = json.loads(raw)
    except ValueError:
        stats["残した JSON-LD（JSON として読めない）"] += 1
        return raw
    graph = data.get("@graph") if isinstance(data, dict) else None
    if not isinstance(graph, list) or not any(is_old_person(n) for n in graph):
        return raw

    for dumps in (dumps_wp, dumps_py):
        if dumps(data) == raw:
            break
    else:
        stats["残した JSON-LD（元の書き方を再現できない）"] += 1
        return raw

    old_ids = {n["@id"] for n in graph if is_old_person(n) and "@id" in n}
    has_org = any(isinstance(n, dict) and n.get("@id") == ORG_ID for n in graph)
    new_graph = []
    for n in graph:
        if is_old_person(n):
            stats["外した「管理者」の Person のノード"] += 1
            if not has_org:
                new_graph.append(dict(ORG_NODE))
                has_org = True
                stats["足した 組織のノード"] += 1
            continue
        new_graph.append(n)
    data["@graph"] = new_graph
    repoint(data, old_ids, stats)

    out = dumps(data)
    # description などの本文の中の「管理者」は記事の中身なので、ノードと ID だけを見る
    if any(is_old_person(n) for n in data["@graph"]) or any(
            f'"{i}"' in json.dumps(data, ensure_ascii=False) for i in old_ids):
        stats["残した JSON-LD（「管理者」の Person か、それへの参照が残る）"] += 1
    return out


def fix(text, stats):
    def sub(m):
        new = fix_block(m.group(3), stats)
        if new == m.group(3):
            return m.group(0)
        return m.group(1) + m.group(2) + new + m.group(4) + m.group(5)
    return JSONLD.sub(sub, text)


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
        after = fix(before, stats)
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
