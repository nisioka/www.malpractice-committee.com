# 改善バックログ

サイト全体の調査（2026-07）で見つかった改善点の記録。対応済み項目は ✅、未対応は優先度付きで残す。
新たに対応した際はこのファイルを更新すること。

## 対応済み（2026-10, ブランチ feat/static-site-search）

- ✅ **サイト内検索を、ブラウザ側だけで動く全文検索で戻した**: サイドバーの先頭に検索欄を戻した。
  入力した語は検索結果ページ `/search/` へ渡り、`search/search.js` が索引
  `search/search-index.json` を読んで、題名・病院名・本文から部分一致で探す。サーバー側の処理は無い。
  - 索引は `_automation/build_search.py` が `manifest.json` の記事から作る。266 記事で 561KB、
    gzip で 171KB。読み込むのは検索結果ページだけで、他のページに増えるのは検索欄の HTML だけ。
    記事を足したら同じスクリプトで作り直す（`_automation/PLAYBOOK.md` の手順5）。
  - 検索欄は `_automation/add_sidebar_search.py` が 672 ページと `_automation/templates/sidebar.html` に入れる。
    検索欄の id は `site-search`。WordPress が処理していた旧い検索欄 `search-2` とは別なので、
    `remove_sidebar_widgets.py` を掛け直しても消えない。
  - 語に区切らず文字列として探す。空白で区切った語はすべて含む記事だけを出し、全角と半角、
    大文字と小文字は区別しない。ひらがなとカタカナ、新旧の字体の違いは吸収しない。
  - 実体の無いサイト内参照は 3,234 件から 3,236 件になった。増えた2件は、新しい検索結果ページの
    サイドバー「閲覧ランキング」から下記の欠けた記事へのリンクで、他の全ページにあるものと同じ。
    検索欄の送信先・索引・スクリプト・CSS への参照はすべて実体がある。
  - 方式は次の候補から選んだ。保守の状況は 2026-10 に各公式リポジトリのリリースとコミットで確かめた。

    | 候補 | 保守の状況 | 日本語の扱い | 索引の作り方 | 判断 |
    |---|---|---|---|---|
    | 索引を Python で作り、素の JS で部分一致 | 自前 | 文字列として探すので、語の区切りに左右されない | `_automation/` にスクリプト1本。標準ライブラリだけ | 採用 |
    | Pagefind 1.5.2 | 2026-04 リリース、コミットは 2026-10 まで | 索引を作るときに語へ区切る | `pip install 'pagefind[extended]'` でバイナリを入れる | 退けた |
    | Lunr.js 2.3.9 | 最後のコミットが 2020-08 | 別リポジトリの lunr-languages と TinySegmenter が要る | Node | 退けた |
    | MiniSearch 7.2.0 | 最後のコミットが 2025-09 | 既定は空白と句読点で区切る。区切り方は自分で書く | Node、またはブラウザで毎回作る | 退けた |
    | FlexSearch 0.8.2 | 2025-05 リリース、コミットは 2026-05 まで | CJK 用の文字セットがある | Node、またはブラウザで毎回作る | 退けた |
    | Orama 3.1.18 | 2025-12 リリース、コミットは 2026-07 まで | 日本語用のトークナイザがある | Node | 退けた |
    | Fuse.js 7.5.0 | 2026-07 リリース | あいまい検索のライブラリ。索引は持たない | 不要 | 退けた |
    | tinysearch 0.11.1 | 2026-09 リリース | 完全一致と前方一致。語に区切られている前提 | Rust | 退けた |
    | Stork | 最後のコミットが 2023-07。2.0 は beta のまま | — | — | 退けた |

    候補のうち、HTML から索引を作るところまで受け持ち、日本語にも対応しているのは Pagefind だけ
    なので、同じ記事に実際に掛けて比べた
    （1.5.2、`--glob "*/index.html" --root-selector article`、他は既定）。出力は 292 ファイル・1.3MB で、
    索引の断片はファイル名が内容のハッシュになる。検索結果の件数は部分一致と次のように食い違った。

    | 語 | Pagefind | 部分一致 |
    |---|---|---|
    | 医療ミス | 17 | 117 |
    | 千葉県がんセンター | 4 | 9 |
    | がんセンター | 59 | 17 |
    | 誤投与 | 22 | 7 |
    | 胸腔ドレナージ | 5 | 1 |
    | 小林市立病院 | 1 | 1 |

    語への区切り方が索引と検索語で揃わないと、本文にある語が出ず、無い語が出る。病院名や
    手技の名前で探すサイトなので、書いてある文字列がそのまま当たるほうを取った。数百記事の
    うちは全件を走査しても一瞬で終わるので、語ごとの索引を持つ利点も無い。記事が数千に
    増えて索引が数 MB を超えたら、分割して読む Pagefind を見直す。
    残りの候補は、Node などこのリポジトリに無い実行環境が要るか、日本語の区切りを自分で
    用意する必要があり、部分一致に対する利点が無かった。
  - 出典:
    https://github.com/Pagefind/pagefind/releases
    https://github.com/Pagefind/pagefind/blob/main/docs/content/docs/multilingual.md
    https://github.com/olivernn/lunr.js/commits/master
    https://github.com/lucaong/minisearch
    https://github.com/nextapps-de/flexsearch/releases
    https://github.com/oramasearch/orama/releases
    https://github.com/krisk/Fuse/releases
    https://github.com/tinysearch/tinysearch/releases
    https://github.com/jameslittle230/stork/releases

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
  19,443件から3,230件になった。その後の週次更新を取り込んだ時点では3,234件で、増えた4件は
  新しい2ページのサイドバーから下記の欠けた記事へのリンク。残りは下記「未対応」に記載。
- ✅ **サイドバーの機能していない4部品を外した**: サイト内検索・twitter・関連書籍・アンドロイド アプリ。
  672ページと `_automation/templates/sidebar.html` から、見出しと外側のウィジェット要素ごと削除した
  （`_automation/remove_sidebar_widgets.py`）。サイドバーに残るのは「医療ミス調査会」と
  「閲覧ランキング」の2つ。外す前の状態は次のとおりで、2026-10 に公開サイトを実ブラウザで開いて確かめた。
  - サイト内検索: 何を入力してもトップページが表示される。検索は WordPress が処理していたので、
    静的配信では `?s=` が無視される。
  - twitter: タイムラインが出ず、「#医療ミス のツイート」というリンク文字だけが表示される。
  - 関連書籍: 壊れた枠のアイコンが 300×250 で表示される。
  - アンドロイド アプリ: バッジ画像は表示されるが、リンク先の Google Play のページが 404 になる。

  twitter の部品が読み込んでいた `widgets.js` は部品と一緒に消えた。記事の共有ボタンが読み込む
  `widgets.js` と、記事本文の商品枠が使う `amazonjs` は残している。実体の無いサイト内参照は
  3,234件のまま変わらない。検索フォームと関連書籍の `iframe` に付いていたアクセシビリティの指摘
  （PR #16）は、要素が無くなったので解消した。

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
- **記事ページそのものが無いリンク**: 一覧と AMP 版の関連記事から、リポジトリに存在しない
  記事41本へ計1,681件のリンクがある。静的化のときに記事ページが取り込まれなかったもの。
  うち `a-vegetative-state-in-medical-malpractice/` はサイドバー「人気記事」に載っており、
  全ページから計1,350件参照されている。Internet Archive に旧ドメインの写しが残っているが、
  復元は内容の確認を伴うためオーナー判断。対象の一覧は
  `python3 _automation/check_links.py --json out.json` で出力できる。
- **存在しないカテゴリページへのリンク**: `category/` 配下の9件。niigata-cc・gakuentoshi-mc・
  nagoya-cu・itoigawa-hp・tanushimaru・municipal-hospital-toyohashi・dongo・kcch-kanagawa・hiroo。
  ほとんどは上記の欠けた記事が属していたカテゴリ。
- **サイドバーから外した部品の代替**: 2026-10 に4部品を外し、サイト内検索は戻した（上記「対応済み」）。
  残りは関連書籍・twitter・アンドロイド アプリ。入れるときは `_automation/templates/sidebar.html` と
  全ページに同じコードを入れる。関連書籍と twitter は 2026-10-04 に代替手段を調べた。
  「試した結果」は実ブラウザで実際に表示させたもの。
  - **関連書籍**: 外したのは Amazon アソシエイトの `iframe` で、キーワード「医療事故」の和書を
    自動で並べる形式。Amazon は 2022-04-01 にウィジェットのサポートを終えた。プログラム自体は続いている。

    | 候補 | 必要なもの | 試した結果 |
    |---|---|---|
    | Amazon の検索結果へのテキストリンク1本 | 報酬を受けるなら有効なアソシエイトのアカウント | `s?k=医療事故&i=stripbooks&tag=mitsuwo-22` は 200 で開き、`tag` は URL に残る |
    | 書籍を選んで商品へのテキストリンクを並べる | 同上と、載せる本の選定 | `dp/<ASIN>?tag=mitsuwo-22` は 200 で開く |
    | 画像つきの商品枠を Amazon の API で作る | Creators API の登録と認証情報。鍵をブラウザに置けないので、事前に生成する仕組み | 試していない。Product Advertising API 5.0 は廃止され、呼び出すと 403 が返ると公式の移行案内にある |
    | 国立国会図書館サーチやカーリルの検索結果へのリンク | 不要。営利目的で API を使うなら国会図書館へ利用申請 | 国会図書館の検索 API は応答した。書影の URL は画像が表示されなかった |
    | openBD の書誌と書影 | 不要 | 応答はあるが、試した ISBN では書影が空。2023-07 に「openBD API（バージョン1）の提供終了」、2023-08 に「代替書誌情報の提供開始」の告知がある |
    | 楽天ブックスの API | アプリ ID とアクセスキー。報酬を受けるならアフィリエイト ID | 試していない |

    推奨は、Amazon の検索結果へのテキストリンク1本。外した部品と同じ「医療事故の本を探す入口」を、
    外部のスクリプトにも画像にも頼らずに置ける。リンクそのものはアカウントが無効でも開くが、
    `mitsuwo-22` が今も有効かはログインしないと分からない。無効なら `tag` を外すか、置かない。
    画像つきの枠は、API の登録と事前生成の仕組みに対して得るものが少ない。
    記事本文の Amazon の商品枠も、枠の中に ASIN と書名が残っているので、同じ形のテキストリンクへ
    機械的に置き換えられる。
  - **twitter**: 外したのはハッシュタグ `#医療ミス` の検索タイムラインで、X が 2018 年に描画をやめた
    旧形式。現行の埋め込みタイムラインはプロフィールとリストの2種類だけで、ハッシュタグは指定できない。

    | 候補 | 必要なもの | 試した結果 |
    |---|---|---|
    | `@MediMalpComm` のプロフィールタイムライン | なし | 表示されない。配信元が 429 `Rate limit exceeded` を返し、リンク文字だけが出る。前回と同じ |
    | 投稿1件の埋め込み | 載せる投稿の URL | 公開されている別の投稿で試すと表示された |
    | フォローボタン | なし | 表示された |
    | アカウントやハッシュタグ検索への通常のリンク | なし | リンクは置ける。x.com は自動操作のブラウザに 403 を返すので、未ログインで何が見えるかは確かめられなかった |
    | 新着記事の一覧を `_automation/` で生成して置く | なし。X に依存しない | 試していない |

    推奨は、twitter の枠を戻さないこと。タイムラインは出せず、アカウントの投稿は 2020-06 が最後で、
    ヘッダーに同じアカウントへのアイコンが既にある。投稿1件の埋め込みやフォローボタンは動くが、
    6年前の投稿を固定で見せるか、ヘッダーのアイコンと同じ行き先をもう1つ置くことになる。
    サイドバーに新しい話題への入口が欲しいなら、新着記事の一覧のほうが役割に合う。
  - **アンドロイド アプリ**: ストアにアプリのページが無い。再公開されるまで載せるものが無い。
  - 出典:
    https://affiliate.amazon.co.jp/help/node/topic/GJV3KJAYNY5BQYPH
    https://affiliate.amazon.co.jp/help/node/topic/G4WVNKFZTGPXW39F
    https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation
    https://ndlsearch.ndl.go.jp/help/api
    https://openbd.jp/
    https://webservice.rakuten.co.jp/documentation/books-book-search
    https://devcommunity.x.com/t/deprecating-widget-settings/102295
    https://docs.x.com/x-for-websites/timelines/overview
    https://docs.x.com/x-for-websites/embedded-posts/overview
- **記事本文の Amazon の商品枠が表示されない**: 412ファイルに637個あり、うち408ファイルでは
  読み込み中の表示のまま止まる。商品データが静的化のときに取り込まれておらず、代わりに
  使われる `rcm-jp.amazon.co.jp` の `iframe` も、ホスト名がアドレスを返さないので
  読み込めない。枠ごと外すか、商品ページへの通常のリンクに替えるかは
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
