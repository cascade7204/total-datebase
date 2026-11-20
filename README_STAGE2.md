# 開発版・検索画面（第2段階）

## 含まれるもの
- `index.html`: 2025・2026年の全日本大学駅伝の選手・チーム・大会記録検索（検索ボタン式、20件ずつ）
- `public_data/*.json`: ブラウザ向け公開データ（5ファイル）
- `export_public.py`: `ekiden_v2.sqlite3` からJSONを再生成するプログラム
- `ekiden_v2.sqlite3`: 第1段階の移行済みDB（動作確認用）

## GitHubへの配置
`develop` ブランチの**リポジトリ直下**に `index.html`、`export_public.py`、`ekiden_v2.sqlite3`、`README_STAGE2.md` を配置し、`public_data` の5つのJSONは `public_data/` 内に配置します。

**重要:** `index.html` を `develop` にアップロードするだけでは、`main` で公開中のサイトは変わりません。`main` へのPull Requestはまだ行わないでください。

## 仕様上の制限
- 選手は区間記録単位の仮IDです。同姓同名や同一人物の年度間統合は未実装です。
- 出身高校、所属履歴、個人7種目、正式な総合順位は未収録です。画面で捏造しません。
- 総合タイムは元CSVの最終区間通過タイムに基づく暫定値です。
- チームの都道府県は未収録のため `—` です。
- 詳細画面は初期版で、正式な3タブ構成などは今後の実装対象です。
- GitHub PagesはSQLiteを直接参照しません。JSONを公開します。

## JSON再生成
データベースを更新したら、Python 3で `python export_public.py` を実行します。現時点ではGitHub Actionsへの組み込みは未実施です。
