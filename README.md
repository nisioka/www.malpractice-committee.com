# www.malpractice-committee.com

医療ミス調査会 — 日本の医療事故・医療過誤ニュースをまとめるサイト。

公開URL: https://www.malpractice-committee.tech.server-on.net/

## 構成

WordPressを静的HTML化したサイトを GitHub Pages で配信している。ビルドは無く、
コミットされたHTMLがそのまま公開される（`master` への push で `.github/workflows/static.yml` が自動デプロイ）。

新規記事の追加・一覧/索引/サイトマップの再生成は `_automation/` のPython決定論スクリプトで行う。
週次でAIセッションがニュースを収集し、PRを作成 → オーナーがレビュー・Mergeして公開する運用。

## ドキュメント

- [`CLAUDE.md`](CLAUDE.md) — AI作業ガイド（構造・パイプライン・厳守ルール）。作業前に必読
- [`_automation/README.md`](_automation/README.md) — 生成ツールの設計とスクリプト一覧
- [`_automation/PLAYBOOK.md`](_automation/PLAYBOOK.md) — 週次自動更新の手順書
- [`docs/IMPROVEMENTS.md`](docs/IMPROVEMENTS.md) — 改善バックログ
