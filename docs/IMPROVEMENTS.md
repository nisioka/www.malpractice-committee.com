# 改善バックログ

サイト全体の調査（2026-07）で見つかった改善点の記録。対応済み項目は ✅、未対応は優先度付きで残す。
新たに対応した際はこのファイルを更新すること。

## 対応済み（2026-07, ブランチ claude/data-vocabulary-schema-deprecation-v5d4wn）

- ✅ **data-vocabulary.org スキーマ廃止対応**（Search Console 指摘）: 全ページのパンくずを
  廃止された `data-vocabulary.org/Breadcrumb` から `schema.org/BreadcrumbList`（`ListItem` +
  `itemprop="item"/"name"/"position"` メタ）へ移行（621ファイル）。生成側も同期修正
  （`_automation/sitelib.py` 記事用・`_automation/build_category.py` カテゴリ用）。
  `hospital-info/` は既存HTMLのパンくずを温存する設計のためHTML側のみ更新。

## 対応済み（2026-07, ブランチ claude/blog-improvement-setup-tepgcw）

- ✅ **構造化データのタイポ修正**: 全ページの `http://scheme.org/SiteNavigationElement` →
  `schema.org`（約620ファイル + `_automation/templates/header_nav.html`）。
- ✅ **死んだUniversal Analytics除去**: 計測停止済みの `UA-67242789-1`（analytics.js）を全ページから
  除去し、コメントアウト済みGA4雛形（`G-XXXXXXXXXX` プレースホルダ）に置換。
  → **要オーナー作業**: GA4プロパティを作成し測定IDを全ページ一括置換して有効化。
- ✅ **robots.txt / sitemap.xml 新設**: `_automation/build_sitemap.py` で全網羅生成（418 URL）。
  重複バリアント（`Pnoamp=`/`Preplytocom=`）と `wp-json/` はクロール除外。
  → **要オーナー作業**: Google Search Console へ sitemap.xml を登録。
- ✅ **死んだ html5shiv 除去**: 閉鎖済み `html5shiv.googlecode.com`（404・mixed content）の
  IE<9向けスクリプト参照を全ページから除去。
- ✅ **陳腐化メタ・リンク除去**: Google+ `rel="publisher"`・ヘッダーのGoogle+アイコン・
  `fb:admins`/`fb:app_id` を全ページ+生成スクリプトから除去。
- ✅ **WordPress Popular Posts 設定JS除去**: 静的サイトでは機能しないAJAX設定
  （公開nonce含む）と `wpp.min.js` を全ページから除去（人気記事リストの静的表示は維持）。
- ✅ **非機能コメントフォーム除去**: 静的ホストでは送信できない `wp-comments-post.php` 宛
  フォームを全ページ+テンプレートから除去（過去コメントの表示は維持）。
- ✅ **wp-json宣言リンク除去**: `rel="https://api.w.org/"`・RSD（xmlrpc）宣言を全ページから除去。
  `Prsd_xmlrpc.xml` を削除。`wp-json/` 本体は oEmbed discovery が参照するため残置。
- ✅ **calil.jp リンクのHTTPS化**（サイドバー・本文の図書館リンク）。
- ✅ **ドキュメント整備**: `CLAUDE.md`（AI作業ガイド）新設、README拡充、
  sitemap生成をパイプライン（PLAYBOOK/README）に組み込み。

## 未対応（優先度順）

### 高
- **画像の最適化**（ユーザー指示により今回対象外）: `wp-content/uploads` が242MB。
  7MB級のJPEG原本が多数（例: `wp-content/uploads/2018/10/hirosaki.jpg` 7.2MB）。
  リサイズ+再圧縮（可能ならWebP併用）でページ速度・リポジトリサイズとも大幅改善余地。
- **GA4の有効化**（要オーナー: 測定ID取得 → `G-XXXXXXXXXX` を一括置換しコメント解除）。
- **Search Console への sitemap 登録**(要オーナー)。

### 中
- **OGP画像の改善**: トップの `og:image` が150×150。推奨1200×630の画像を用意し、
  `twitter:card` を `summary_large_image` へ（画像制作を伴うため今回見送り）。
- **img の alt 属性が空**: 記事画像の多くが `alt=""`。アクセシビリティ・画像SEOのため
  内容に応じた代替テキストを付与（1000枚超の内容判断が必要なため段階的に）。
- **独自ドメイン移行とURL正規化**: 全ページに無料ドメインが絶対URLで焼き込み済み（884ファイル）。
  移行時に一括置換+リダイレクト設計が必要。AdSense有効化もこれが前提（`_automation/README.md` 参照）。

### 低（現状維持の方針決定済みを含む）
- **slugの乱立**: 類似事案でslug命名が不統一（例: ガーゼ遺残系が6種）。既存URLは温存し、
  新規記事の命名規約を揃える運用で対応。
- **AMPページの二重保守**（225件）: 新規記事はAMP版を作っていない。既存AMPはURL温存のため残置。
- **日本語名ディレクトリ1件**（`青森県立中央病院...`）: URL温存のため残置。
- **page/11・12の欠番**: 元サイト由来。番号体系はURL温存のため触らない（既定方針）。
- **コメントフォーム除去後の残骸**: 過去コメント内の「返信」リンクが除去済みアンカー
  `#respond` を指す（実害は小さい）。
