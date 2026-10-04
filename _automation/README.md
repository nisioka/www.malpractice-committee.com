# _automation — 医療ミス調査会 サイト自動更新ツール

WordPressを静的HTML化した本サイトに、**新しいニュース記事を既存と同じ体裁で追加**し、
**病院索引を全網羅で再生成**するための決定論スクリプト群です。生成はすべて Python 標準
ライブラリ（＋病院索引の五十音分類にのみ任意で `pykakasi`）で行い、外部APIは使いません。

## 設計
既存記事 `settlement/index.html` を「唯一の真実」とし、全ページ共通の定型ブロックを
`templates/` に抽出（`extract_partials.py`）。可変部分だけをコードで組み立てることで、
定型部分を**バイト単位で一致**させたまま新規ページを生成します。

## スクリプト
| スクリプト | 役割 |
|---|---|
| `extract_partials.py` | 既存記事から定型パーツ(head/nav/sidebar/footer等)を `templates/` へ抽出（初回のみ） |
| `sitelib.py` | 生成ロジック共通ライブラリ（記事ページ・一覧カード・ページ送り・JSON-LD 等） |
| `build_manifest.py` | 全記事を走査し `manifest.json`（重複判定・索引の情報源）を生成 |
| `generate_article.py` | 構造化JSON → 記事ページ(PC版 index.html)を生成、post_id採番 |
| `build_category.py` | 病院カテゴリページを生成/再生成 |
| `rebuild_listings.py` | トップ + page/N の一覧を非破壊シフトで再生成（`--check`で回帰テスト） |
| `build_hospital_index.py` | 病院索引 `hospital-info/index.html` を全網羅で再生成 |
| `build_sitemap.py` | `sitemap.xml` をルートに全網羅で再生成（manifest + 実在ページから） |
| `check_links.py` | 全HTML/CSSのサイト内参照（画像・CSS・JS・リンク）を実体と突き合わせ、壊れ方の種類ごとに集計 |
| `fix_refs.py` | 上記のうち機械的に直せるものを一括修正（実体の無い `srcset` 候補の削除、`/<親>/<slug>` 形の記事リンクの書き換え）。冪等 |
| `remove_sidebar_widgets.py` | サイドバーから機能していない部品（WordPress が処理していた旧い検索欄・twitter・関連書籍・アンドロイド アプリ）を枠ごと外す。全ページとテンプレートが対象。冪等 |
| `build_search.py` | サイト内検索の索引 `search/search-index.json` と検索結果ページ `search/index.html` を再生成（`--check` で一致だけ確認） |
| `add_sidebar_search.py` | サイドバーの先頭にサイト内検索の入力欄を入れる。全ページとテンプレートが対象。冪等 |

## 手動での使い方（例）
```bash
pip install pykakasi                                    # 病院索引の五十音分類（任意）
python3 _automation/build_manifest.py
python3 _automation/generate_article.py article.json    # → _generated.json も出力
python3 _automation/build_manifest.py
python3 _automation/build_category.py
python3 _automation/rebuild_listings.py
python3 _automation/build_hospital_index.py
python3 _automation/build_sitemap.py
python3 _automation/build_search.py
```

## 回帰テスト
```bash
python3 _automation/rebuild_listings.py --check   # 新規0件で全ページがバイト一致すればOK
python3 _automation/build_search.py --check       # 検索の索引と結果ページが記事・テンプレートと揃っていればOK
python3 _automation/check_links.py                # 参照切れの集計（--strict で1件でもあれば終了コード1）
```

## 週次自動更新
クラウド定期実行の手順は `PLAYBOOK.md` を参照。

## 既知の事項
- サイト内URLは `www.malpractice-committee.tech.server-on.net`（MyDNS無料ドメイン）で焼き込み。
  新規ページもこれに合わせる。独自ドメイン移行時は別途URL正規化が必要。
- ページ送りは元から page/11・page/12 が欠番（到達不能記事あり）。番号体系はURL温存のため触らない。
- AdSense は無料ドメインでは所有権認証不可のため無効。生成ページにはコメント雛形のみ仕込み済み
  （`sitelib.ADSENSE_HEAD`）。独自ドメイン整備後に有効化可能。
- サイドバーの部品は「サイト内検索」「医療ミス調査会」「閲覧ランキング」の3つ。Amazonアフィリエイト(mitsuwo-22)の
  「関連書籍」枠は配信元が応答しなくなったため、他の機能していない部品と合わせて外した。
- サイト内検索はブラウザ側だけで動く。索引は記事の本文をそのまま持つ JSON で、`search/search.js` が
  部分一致で探す。日本語は分かち書きされないので、語に区切る方式を採っていない
  （比較は `docs/IMPROVEMENTS.md`）。外部のライブラリやビルドは要らない。
