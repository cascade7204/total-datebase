# 駅伝データベース移行・第1段階

2025年・2026年の全日本大学駅伝CSVから、新しいSQLiteデータベースを生成する開発用セットです。**既存の `index.html`、`update.py`、GitHub Actionsは変更しません。**

## 実行

Python 3がある環境で、このフォルダ内から `python migrate.py` を実行します。追加ライブラリは不要です。

生成されるファイル：`ekiden_v2.sqlite3`、`migration_report.json`。

## 方針・注意

- 選手は1記録1仮IDとし、氏名が一致する選手を `review_cases` に候補として登録します。勝手に統合しません。
- チームは完全一致する名称だけ共通IDにします。別名・改称は今後確認します。
- 公式総合順位は元CSVにないため未登録です。総合タイムは最終区間の通過タイムから暫定取得し、公式結果と独立に照合する必要があります。
- 元CSVの行を `source_records` に保存します。通過タイムは出典保全用で、画面機能としては使いません。
- `ingestion_status` の `imported_unverified` は移行完了・公式検証未完了を意味します。
- 同一人物の判定・訂正履歴のテーブルはありますが、GitHub Issues連携や判定の自動反映は**まだ未実装**です。
- この移行用SQLiteはGitHub Pagesから直接参照できません。公開サイト向けJSON生成と画面の切り替えは次段階です。

## GitHubへの反映

`develop` ブランチに `migration/` フォルダとして、`migrate.py`、`README.md`、`results_2025.csv`、`results_2026.csv` を追加してください。生成済みSQLiteとレポートは動作確認用で、当面アップロードしなくても構いません。
