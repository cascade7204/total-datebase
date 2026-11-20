# 全日本大学駅伝 2026 自動取得・DB登録テスト

`pip install -r requirements.txt`

手元のPDFを使うテスト: `python update.py --pdf data/58meki_result.pdf`

公式サイトから取得して登録: `python update.py`

`output/results.csv`、`output/ekiden.sqlite3`、`output/status.json` を生成します。再実行しても出走記録が重複登録されません。元データの選手名が変更された場合は安全のためエラーにします。

`.github/workflows/weekly.yml` はGitHub Actionsで月曜04:17（日本時間）に実行する設定です。実際に動かすにはGitHubリポジトリへの登録が必要です。GitHub上での実行と公式サイトからのダウンロードは未検証です。

**制限**: PDFのページ座標と2026年の版面に依存します。別の年・大会へそのまま適用できません。PDFの再配布や定期取得の前に利用条件・robots.txt・負荷の確認が必要です。GitHubのartifact保存は永続的な本番DBの代わりにはなりません。個人情報の同一人物判定は未実装です。
