# 週次自動更新プレイブック（クラウド定期実行用）

このファイルは、週に一度クラウドで起動する Claude Code セッションが従う手順書です。
**サブスク枠内で動作し、API課金は発生しません。** 公開はレビュー方式（AIはPRを作るだけ、
オーナーがMergeして初めて公開）。

## 役割分担
- **判断（AIが担当）**: ニュース選別・重複排除・短い事実要約・病院/カテゴリの判定。
- **HTML生成（決定論スクリプトが担当）**: `_automation/*.py` が既存とバイト整合するHTMLを生成。

## 手順

1. **準備**
   - 作業ブランチ `claude/medical-news-auto-update-e1kwkq` で作業（無ければ master から作成）。
   - `pip install pykakasi`（病院索引の五十音分類に使用。失敗しても索引は「その他」に集約され動作継続）。
   - `python3 _automation/build_manifest.py` で最新の manifest を作る。

2. **ニュース収集**
   - `_automation/sources.json` の各RSSを WebFetch で取得し、候補記事（見出し・リンク・日付・媒体）を集める。
   - 必要に応じ WebSearch も併用。

3. **重複排除**（重要）
   - `_automation/manifest.json` の既存記事（タイトル・病院名・カテゴリ）と突き合わせ、**既に取り上げた事案は除外**。
   - 判定はAIの類似判断に加え、出典URLの一致など機械的チェックも併用。

4. **記事化**（新規事案のみ）— 1件ごとに次のJSONを作る（配列で複数可）:
   ```json
   {
     "slug": "english-slug",            // 英小文字/ハイフンのユニークなURL
     "title": "記事タイトル（日本語・事実ベース）",
     "date": "YYYY-MM-DDTHH:MM:00+09:00",
     "hospital_name": "○○病院",
     "category_slug": "hospital-slug",  // 既存病院は manifest.categories の既存slugを流用
     "description": "meta用の1〜2文要約",
     "body_html": "<p>事実を短く要約した本文（複数段落可）。本文の丸写しはしない。</p>",
     "source_name": "媒体名",
     "source_url": "https://元記事URL"
   }
   ```
   **ガードレール（YMYL・医療分野のため厳守）**:
   - 元記事の**本文を転載しない**。事実を短く要約し、必ず `source_url` で出典へリンク。
   - 事実が確認できない・断定できない事案は**スキップ**。実在の病院・個人の名誉毀損になり得る推測を書かない。
   - 病院名/カテゴリは既存に合わせる。新病院なら妥当な英語slugを付ける。

5. **生成パイプライン実行**（順番厳守）:
   ```
   python3 _automation/generate_article.py articles.json   # 記事ページ生成＋採番、_generated.json 出力
   python3 _automation/build_manifest.py                    # manifest 更新
   python3 _automation/build_category.py                    # 新規/更新カテゴリページ
   python3 _automation/rebuild_listings.py                  # トップ＋page/N を非破壊シフト
   python3 _automation/build_hospital_index.py              # 病院索引 再生成
   python3 _automation/build_sitemap.py                      # sitemap.xml 再生成
   ```

6. **検証**
   - `git status` で変更範囲を確認（新記事ディレクトリ、category/、index.html、page/N、hospital-info）。
   - 生成した記事ページをブラウザ（chromium）で開き、体裁崩れが無いか確認。

7. **PR作成**（**master へ直接 push しない**）
   - 作業ブランチに commit → push → PR を作成。タイトル/本文に「今週追加した記事一覧」を記載。
   - オーナーがレビューして Merge → `.github/workflows/static.yml` が GitHub Pages へ公開。

8. **該当なしの週**
   - 新規事案が無ければ**何も変更せず終了**。「今週は候補なし」と報告するだけ。

## 補足
- 生成方式の詳細・パーツ抽出は `_automation/README.md` を参照。
- ページ送りの page/11・page/12 欠番は既存サイトのバグ。番号体系は触らない方針（URL温存のため）。
