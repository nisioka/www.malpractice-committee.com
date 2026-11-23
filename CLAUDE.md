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
| `<slug>/amp/` | 旧AMP版のURL。正規ページ `<slug>/` へ転送するだけのページ（`retire_amp.py` が生成。AMPは廃止済み） |
| `<slug>/Pnoamp=mobile.html` 等 | WP時代のモバイル/返信バリアント（保守対象外・URL温存のため残置） |
| `index.html`, `page/N/` | 記事一覧（トップ + ページ送り。**page/11・12は元サイト由来の欠番**） |
| `category/<slug>/` | 病院別カテゴリページ |
| `hospital-info/` | 病院索引（全網羅再生成対象） |
| `search/` | サイト内検索。結果ページ `index.html` と索引 `search-index.json` は `build_search.py` が再生成する。`search.js`・`search.css` は手書き |
| `sitemap.xml`, `robots.txt` | クロール基盤（sitemapは `build_sitemap.py` で再生成。noindex と canonical が他を指すページは載らない） |
| `wp-content/`, `wp-includes/`, `wp-json/` | WordPress遺産のアセット類（原則触らない） |
| `_automation/` | Python製の決定論生成ツール一式 + `manifest.json`（全記事メタの単一情報源） |
| `docs/IMPROVEMENTS.md` | 改善バックログ（対応済み/未対応の記録） |
| `.claude/site-ops.yml`, `.claude/skills/site-ops/` | 週次のサイト診断（GA4 / Search Console）の設定とスキル |
| `scripts/site-ops/`, `package.json` | 診断の収集 CLI（[site-ops-ai](https://github.com/nisioka/site-ops-ai) から取り込み）。`pnpm site-ops collect` で実行。サイトのビルドには使わない |

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
python3 _automation/build_category.py                    # 病院カテゴリページへ新記事を反映
python3 _automation/rebuild_listings.py                  # トップ＋page/N を非破壊シフト（公開日時順）
python3 _automation/build_hospital_index.py              # 病院索引 再生成
python3 _automation/build_sitemap.py                     # sitemap.xml 再生成
python3 _automation/build_search.py                      # サイト内検索の索引 再生成
```

## 検証方法

- **回帰テスト**: `python3 _automation/rebuild_listings.py --check`
  （新規0件で全一覧ページがバイト一致すれば合格。横断修正後は必ず実行）
- **検索の索引**: `python3 _automation/build_search.py --check`
  （索引と検索結果ページが、記事とテンプレートから作り直したものと一致すれば合格）
- **定型ブロック**: `python3 _automation/fix_shared_markup.py --dry-run`
  （書き換え対象 0 件なら、全ページの構造化データ・一覧カードの画像の alt 等が生成側と揃っている）
- **AMP の名残**: `python3 _automation/retire_amp.py --dry-run`
  （書き換え対象 0 件なら、`rel="amphtml"` も AMP 文書も残っていない）
- **人気記事**: `python3 _automation/build_popular.py --dry-run`
  （書き換え対象 0 件なら、全ページのサイドバーの人気記事が `popular.json` と記事ページに揃っている）
- **フィードの名残**: `python3 _automation/remove_dead_feeds.py --dry-run`
  （書き換え対象 0 件なら、実体の無いフィードを指す `rel="alternate"` が残っていない）
- **SNS の名残**: `python3 _automation/remove_sns.py --dry-run`
  （書き換え対象 0 件なら、Facebook・X・Google+ のボタン・リンク・埋め込みが残っていない）
- **著者欄の名残**: `python3 _automation/remove_post_author.py --dry-run`
  （書き換え対象 0 件なら、記事の末尾の著者欄（「管理者」）が残っていない）
- **構造化データの著者**: `python3 _automation/set_jsonld_organization.py --dry-run`
  （書き換え対象 0 件なら、JSON-LD の著者・発行者に「管理者」の Person が残っていない）
- **参照切れの確認**: `python3 _automation/check_links.py`
  全HTML/CSSの画像・CSS・JS・サイト内リンクをリポジトリ内の実体と突き合わせて集計する。
  外部URLは叩かない。横断修正の前後で件数を比べる。
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
- **サイドバーの部品は「サイト内検索」「医療ミス調査会」「人気記事」の3つ**。twitter・
  関連書籍・アンドロイド アプリと、WordPress が処理していた旧い検索欄は機能していなかったので、
  全ページとテンプレートから枠ごと外した（`_automation/remove_sidebar_widgets.py`）。外した部品を
  含むHTMLを取り込み直したときは、同じスクリプトを掛け直し、続けて `add_sidebar_search.py` で
  今の検索欄を入れる。関連書籍の代替は調査済みで未対応（`docs/IMPROVEMENTS.md`）。twitter は
  SNS を運用していないので戻さない。
- **サイト内検索はブラウザ側だけで動く**。検索欄は語を `/search/` へ渡すだけで、`search/search.js` が
  索引 `search/search-index.json` を読んで部分一致で探す。**記事を足したり本文を直したりしたら
  `build_search.py` で索引を作り直す**。検索欄の HTML を変えるときは `add_sidebar_search.py` の
  `WIDGET` を書き換えて実行する（全ページとテンプレートが同じ中身に揃う）。`search.js` に
  ホスト名を書かない（プレビュー配信は別ホストなので動かなくなる）。
- **サイドバーの「人気記事」は閲覧数を数えていない**。静的配信では実行時に数えられないので、載せる
  記事の slug を `_automation/popular.json` に表示順で書き、`build_popular.py` が全ページと
  テンプレートへ同じ中身で埋め込む。リストに書けるのは記事ページがある slug だけ（無ければ止まる）。
  見出しと日付は記事ページから取るので、**載っている記事のタイトルを直したら `build_popular.py` を
  掛け直す**。リストを変えると約680ページが書き換わるので、週次更新では変えない。リストは
  WordPress のときの最後の集計の上位 10 本を当時の順位のまま載せている（記事ページの無い1本だけ次点で
  埋めた）。内容で選り好みしない（2026-11 のオーナー方針）。
- **記事ページが無い記事は作り直さない**。ニュースの出典は消えるもので、記事ページが無い記事も当時の
  スナップショットとして、一覧・カテゴリのカードとリンクをそのまま残す（2026-11 のオーナー方針）。
  `check_links.py` が数える「記事・固定ページ」の参照切れの多くはこれで、直す対象ではない。
- **記事本文の Amazon 商品枠**（`mitsuwo-22`）は残っているが表示されない。扱いはオーナー判断待ちで、
  決まるまで枠のコードは変えない（`docs/IMPROVEMENTS.md` の「未対応」）。
- **カテゴリページは3つの形がある**。病院ページ（`hp-wrap`、基本情報・地図・関連記事カード）と
  WordPress 由来の一覧は、`build_category.py` が作り直さずに新記事のカードを差し込む。作り直すのは
  このスクリプトが作った簡易一覧と新病院だけ。週次更新でカテゴリページを手で直す必要は無い。
  取り込み直したページに記事を足すときは `build_category.py <slug> --posts=<post_id>`。
- **SNS の部品と共有バーは無い**。サイトの Facebook ページと X のアカウントは運用していないので（2026-11 に
  オーナーが全部外すと決めた）、フォロー・共有のボタン、アカウントへのリンク、埋め込みとその読み込み、
  記事下の「SNSでもご購読できます。」欄、`twitter:site` を全ページとテンプレートから外した
  （`_automation/remove_sns.py`、冪等）。記事と一覧のカードの下にあった共有バー（「共有:」）も、メールで
  送るボタンを含めて要らない（同じくオーナー判断）ので、バーごと外し、それだけのための
  `sharing.min.js`・共有数の設定・ボタンのアイコンの字体（`social-logos.min.css`）も外した。
  OGP（`og:*`）と `twitter:card` は、他人がリンクを貼ったときのプレビュー用なので残す。生成側
  （`sitelib.py`・`build_category.py`）からも外してあるので、新しいページにも入らない。WordPress 時代の
  HTML を取り込み直したときは `remove_sns.py` を掛け直す。
- **記事の末尾の著者欄（「管理者」）は無い**。テーマが記事の末尾に出していた著者欄
  （`<aside class="post-author">`。仮の人型アイコンと「管理者」という名前だけ）は WordPress の名残で
  意味が無いので（2026-11 のオーナー判断）、全ページから外した（`_automation/remove_post_author.py`、
  冪等）。生成側（`sitelib.py`）からも外し、テンプレート `post_author.html` は削除したので、新しい
  ページにも入らない。WordPress 時代の HTML を取り込み直したときは `remove_post_author.py` を掛け直す。
- **構造化データの著者・発行者はサイトの組織「医療ミス調査会」**。`<head>` の JSON-LD の `author`・
  `publisher`（と WordPress 時代のページの `creator`、一覧の `about`）は、名前「管理者」の Person を
  指していたので、サイト名「医療ミス調査会」の組織（`Organization`、`@id` は `<トップ>/#organization`、
  `url` はトップ）にした（2026-11 のオーナー判断）。実体の無い著者ページ `/author/fushigibana/` を指す
  著者の URL も無くなった。既存ページは `_automation/set_jsonld_organization.py`（冪等。JSON の書き方は
  ページごとに元のまま）で書き換え、生成側は `sitelib.ORGANIZATION` から同じノードを出す。WordPress 時代の
  HTML を取り込み直したときは、このスクリプトを掛け直す。
- 定型ブロックの不具合を直した `_automation/fix_shared_markup.py` は冪等なので、WordPress 時代の
  HTML を取り込み直したときは掛け直す。
- **AMP は廃止済み**。どのページにも `rel="amphtml"` を付けず、AMP 版も作らない。旧 AMP の URL
  （`<slug>/amp/` と `Pamp.html`）は、正規ページへ `rel="canonical"` と即時の `meta refresh` で送る
  転送ページになっている（GitHub Pages では 301 が使えないため）。WordPress 時代の HTML を取り込み
  直したときは `_automation/retire_amp.py` を掛け直す（冪等）。
- **ページ送り（`page/N`）は noindex,follow**。検索結果には出さず（2026-11 にオーナーが不要と確認）、リンクはたどらせる。
  noindex のページは `build_sitemap.py` がサイトマップから落とす。
- コメント投稿フォームは静的化に伴い除去済み（過去コメントの表示は残存）。
- **フィード（RSS）は無い**。WordPress が `<head>` に出していたコメントフィード・カテゴリのフィードの
  `rel="alternate"` と、サイトのフィードを Feedly で購読させるリンク（ヘッダーの RSS アイコン、記事下の
  「Feedly でフォローする」）は、実体が無いので外した。テンプレートからも外してあるので、新しいページにも
  入らない。WordPress 時代の HTML を取り込み直したときは
  `_automation/remove_dead_feeds.py` を掛け直す（冪等）。
- `wp-json/` は oEmbed discovery が参照するため残置（robots.txt でクロール除外済み）。
- `pykakasi` 無しでも動作する（病院索引が「その他」に集約されるだけ）。
