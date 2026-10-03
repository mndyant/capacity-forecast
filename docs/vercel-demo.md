# Vercel公開デモ

URL: https://capacity-forecast.vercel.app

`index.py` が Flask アプリをエクスポートし、Vercel の Python 3.12 Function が既存の予測・選択・期限計算を実行します。HTML/CSS/JavaScriptは既存画面をベースに、3つの条件プリセットとCSV送信の説明を追加しました。ローカルは `python run.py` で利用できます。

静的ファイルは `public/static/` に置き、VercelではCDN、ローカルではFlaskが配信します。予測計算に必要な `data/demo/observed/` は同梱します。truth/metadata、評価結果、テスト、開発用資料は `.vercelignore` でデプロイから除外します。CSVはメモリ上で計算し、ファイルやDBに保存しません。APIレスポンスは `Cache-Control: no-store` です。個人情報・機密情報を含まないCSVで試してください。

## 更新

Vercel CLIで対象アカウントにログインした後、リポジトリのルートで以下を実行します。

```powershell
vercel link --project capacity-forecast
vercel deploy
# プレビューで確認後に本番公開
vercel deploy --prod
```

## 2026-10-03の検証

- 既存回帰と公開用エントリーポイントのテスト: 52 passed。
- Vercel Python 3.12でビルド成功。公開URLにログインなしでアクセスできることを確認。
- 標準条件: 上限到達日2026-09-24、着手期限2026-08-18。ローカルと公開環境で一致。
- ローカル実ブラウザで3プリセットを操作。1000GBでは期限超過、9999GBでは期間内未到達。
- 公開環境でブラウザコンソールのエラーなし。390px幅で横はみ出しなし。

合成データによるデモです。公開対応は予測モデルの実業務精度を証明するものではありません。入力データの観測終了日を基準に期限を判定します。
