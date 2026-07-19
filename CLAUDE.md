# CLAUDE.md — AI作業ガイド

このリポジトリで作業するAIセッション（Claude Code等）向けのガイド。まずこのファイルを読み、
詳細は `_automation/README.md`（生成ツール設計）と `_automation/PLAYBOOK.md`（週次自動更新手順）を参照すること。

## サイト概要

- **医療ミス調査会** — 日本の医療事故・医療過誤ニュースをまとめるサイト。
- WordPressを**静的HTML化**したものをGitHub Pagesで配信。ビルドステップは無く、コミットされた
  HTMLがそのまま公開される（`.github/workflows/static.yml`、master への push で自動デプロイ）。
- 配信URL: `https://www.malpractice-committee.tech.server-on.net/`（MyDNS無料ドメイン）。
  **全ページに絶対URLで焼き込み済み**。独自ドメイン移行時は別途URL正規化が必要（現状は触らない）。

## リポジトリ構造

| パス | 内容 |
|---|---|
| `<slug>/index.html` | 記事ページ（ルート直下に記事slugディレクトリが約260個フラットに並ぶ） |
| `<slug>/amp/`, `<slug>/Pnoamp=mobile.html` 等 | WP時代のAMP/モバイル/返信バリアント（保守対象外・URL温存のため残置） |
| `index.html`, `page/N/` | 記事一覧（トップ + ページ送り。**page/11・12は元サイト由来の欠番**） |
| `category/<slug>/` | 病院別カテゴリページ |
| `hospital-info/` | 病院索引（全網羅再生成対象） |
| `sitemap.xml`, `robots.txt` | クロール基盤（sitemapは `build_sitemap.py` で再生成） |
| `wp-content/`, `wp-includes/`, `wp-json/` | WordPress遺産のアセット類（原則触らない） |
| `_automation/` | Python製の決定論生成ツール一式 + `manifest.json`（全記事メタの単一情報源） |
| `docs/IMPROVEMENTS.md` | 改善バックログ（対応済み/未対応の記録） |

## アーキテクチャの核心

- 既存記事 `settlement/index.html` を「唯一の真実」とし、共通定型ブロックを
  `_automation/templates/` に抽出。可変部だけをコードで組み立て、**定型部分をバイト単位で
  一致**させたまま新規ページを生成する方式。
- したがって**既存HTMLを横断修正する場合は、`_automation/templates/*.html`・`sitelib.py`・
  `build_category.py` 内の同じ文字列にも必ず同一修正を適用**すること。ズレると
  回帰テストが落ちる／新規生成ページだけ古い体裁になる。
- 記事メタ（post_id・slug・日付・病院カテゴリ）は `_automation/manifest.json` に集約。
  `build_manifest.py` が全記事の走査で再生成する（重複判定・索引・sitemapの情報源）。

## 記事追加の標準パイプライン（順番厳守）

入力JSONの形式とニュース選定ガードレールは `_automation/PLAYBOOK.md` を参照。

```bash
pip install pykakasi                                     # 任意（病院索引の五十音分類）
python3 _automation/generate_article.py articles.json    # 記事ページ生成＋post_id採番
python3 _automation/build_manifest.py                    # manifest 更新
python3 _automation/build_category.py                    # 病院カテゴリページ生成
python3 _automation/rebuild_listings.py                  # トップ＋page/N を非破壊シフト
python3 _automation/build_hospital_index.py              # 病院索引 再生成
python3 _automation/build_sitemap.py                     # sitemap.xml 再生成
```

## 検証方法

- **回帰テスト**: `python3 _automation/rebuild_listings.py --check`
  （新規0件で全一覧ページがバイト一致すれば合格。横断修正後は必ず実行）
- 生成/修正したページを chromium で開いて体裁確認。PRを作れば
  `.github/workflows/pr-preview.yml` が変更ページのスクリーンショットをPRにコメントする。
- 変更範囲の確認: `git status` で意図したファイルだけが変わっているか確認。

## 厳守ルール

1. **master へ直接 push しない**。作業ブランチ → PR → オーナーがMergeして公開。
2. **YMYL（医療分野）ガードレール**: 元記事本文を転載しない（事実の短い要約+出典リンクのみ）。
   事実が確認できない事案はスキップ。実在の病院・個人への推測・断定を書かない。
3. **URL体系の温存**: 既存slugの改名・ディレクトリ移動・AMP/バリアントページの削除・
   page/11,12欠番の「修正」はしない（リンク切れ・SEO毀損になる）。
4. テンプレートとページの**同期修正**（上記アーキテクチャ参照）。
5. 一時ファイル・中間生成物（`_generated.json` 等）をコミットしない。

## 既知の事項・罠

- **GA4有効**: 全ページに測定ID `G-JNHNKLLKNE` のGA4スニペットが有効化済み（旧Universal Analyticsは
  除去済み）。定型ブロックは `_automation/templates/head_assets.html` と同期。測定IDを差し替える場合は
  テンプレートと全ページの `G-JNHNKLLKNE` を一括置換すること。
- **AdSense無効**: 無料ドメインでは認証不可。`sitelib.ADSENSE_HEAD` にコメント雛形のみ。
- **Amazonアフィリエイト**（`mitsuwo-22`）はサイドバー「関連書籍」枠で全ページ有効。壊さない。
- コメント投稿フォームは静的化に伴い除去済み（過去コメントの表示は残存）。
- `wp-json/` は oEmbed discovery が参照するため残置（robots.txt でクロール除外済み）。
- `pykakasi` 無しでも動作する（病院索引が「その他」に集約されるだけ）。
