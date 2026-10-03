# 改善バックログ

サイト全体の調査（2026-07）で見つかった改善点の記録。対応済み項目は ✅、未対応は優先度付きで残す。
新たに対応した際はこのファイルを更新すること。

## 対応済み（2026-10, ブランチ fix/broken-image-links）

- ✅ **サイドバー「人気記事」のサムネイルが高解像度の画面でリンク切れになる問題を解消**:
  `srcset` が指す `@1.5x`〜`@3x` の画像は、静的化のときに1枚も取り込まれていなかった。
  等倍の画面では `src` が使われて表示されるが、スマートフォンなど高解像度の画面では
  10枚中7枚が404になっていた。対象は670ページと `_automation/templates/sidebar.html`。
  実体の無い候補を `srcset` から落とし、残りが `src` と同じ1件だけなら属性ごと削除した。
  post 624・779 の8枚は Internet Archive に元画像が残っていたので取得して配置し、
  `srcset` をそのまま生かしている。
- ✅ **病院ページの「関連記事」リンクの404を解消**: `/<病院slug>/<記事slug>` を指していた109件を、
  実在する `/<記事slug>/` へ書き換えた。WordPress はこの形を自動で転送していたが、
  静的配信では404になる。
- ✅ **参照切れの集計ツール新設**: `_automation/check_links.py`。実体の無いサイト内参照は
  19,443件から3,230件になった。残りは下記「未対応」に記載。

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
- **WP時代の記事に本文全文転載・裁判判決文の長文引用が残存**（PR #16, CodeRabbit指摘で発覚）:
  週次更新の生成ルール（`_automation/PLAYBOOK.md`）は新規記事に「事実の短い要約+出典リンクのみ」
  を義務付けているが、2016年前後に作成された既存記事の一部（例: `patients-after-liver-biopsy/`
  ＝post-667、および post-664/631/628/601/604/793/760/821/819/219/209/1039/1031/1000/997/965/963/936/934/912/909/188 等）
  は報道の全文コピー＋裁判判決文の逐語引用（実名含む）をそのまま掲載している。
  週次のページ送り非破壊シフト（`rebuild_listings.py`）で該当記事が別の `page/N/` に
  移動するたびに大きな差分として現れるが、**内容自体は本PRで新規に書いたものではない**。
  法的・名誉毀損リスクと分量（数十記事×長文）を踏まえ、要約への一括リライトはオーナー確認の
  上で別PRとして対応する方針とする（1件ずつ事実確認しながらの書き換えが必要なため）。
- **サイドバー共通テンプレートのアクセシビリティ不備**（同PR, CodeRabbit指摘）: 検索フォーム
  `input#s` にアクセシブルな名前（`aria-label`等）が無い／Amazon「関連書籍」`iframe` に
  `title` 属性が無い。`_automation/sitelib.py`・`_automation/templates/*.html` の共通部分の
  ため、修正すると全ページ（800件超）が再生成対象になる。ニュース更新PRに混在させると
  差分が肥大化しレビューしづらくなるため、独立したアクセシビリティ改善PRで対応する。

- **記事ページそのものが無いリンク**: 一覧と AMP 版の関連記事から、リポジトリに存在しない
  記事41本へ計1,677件のリンクがある。静的化のときに記事ページが取り込まれなかったもの。
  うち `a-vegetative-state-in-medical-malpractice/` はサイドバー「人気記事」に載っており、
  全ページから計1,346件参照されている。Internet Archive に旧ドメインの写しが残っているが、
  復元は内容の確認を伴うためオーナー判断。対象の一覧は
  `python3 _automation/check_links.py --json out.json` で出力できる。
- **存在しないカテゴリページへのリンク**: `category/` 配下の9件。niigata-cc・gakuentoshi-mc・
  nagoya-cu・itoigawa-hp・tanushimaru・municipal-hospital-toyohashi・dongo・kcch-kanagawa・hiroo。
  ほとんどは上記の欠けた記事が属していたカテゴリ。
- **Amazon のウィジェットが表示されない**: サイドバー「関連書籍」の `rcm-fe.amazon-adsystem.com` は
  全ページ、記事本文の `rcm-jp.amazon.co.jp` は592ファイルにある。どちらのホスト名も
  アドレスを返さなくなっており、`iframe` は読み込めない。枠ごと外すか別の掲載方法へ替えるかは
  オーナー判断。
- **medwatch.jp の図版が表示されない**: 記事本文が直接参照している図が191件・35ファイル、
  画像CDN経由の一覧サムネイルが144件・12ファイル。2026-10 時点で接続がタイムアウトし、
  CDN も取得に失敗する。CDN経由の一部はファイル名が文字化けしたURLになっている。
  他サイトの図版なのでリポジトリへ複製していない。
- **実体の無い宣言タグ**: 画面には出ない。oEmbed discovery が960件、コメントフィードの
  `rel="alternate"` が492件、AMP版の無い30ページの `rel="amphtml"`。`wp-json/` 配下は
  クエリ付きのファイル名で保存されており、静的配信では oEmbed のURLに応答しない。
  生成テンプレートからは既に除いてあるので、既存ページからも除去するのが整合的。

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
