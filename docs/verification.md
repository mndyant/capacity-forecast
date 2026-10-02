# 実行・画面確認の記録

検証環境：Windows / PowerShell、Python 3.14.3、Flask 3.1.3、NumPy 2.5.3、pandas 3.0.6、pytest 9.1.1。依存の全固定値は requirements.txt。ブラウザ検証のみPlaywright 1.63.0と既存のChromiumを使用しました。

## 実行したコマンド

|コマンド|結果|
|---|---|
|`python -m venv .venv`|初回ensurepipが失敗。仮想環境内でensurepipを再実行し解消|
|`.venv/Scripts/python -m pip install --index-url https://pypi.org/simple Flask numpy pandas pytest`|インストール成功。確認したバージョンを固定|
|`.venv/Scripts/python -m scripts.generate_demo`|6シナリオ×25 seed、観測150 CSV・正解150 CSV・メタデータ150 JSONを生成|
|`.venv/Scripts/python -m pytest -q`|通常権限では42 passed。初回は一時ディレクトリの制限で1 error。Windowsの例外トレースが多く出たため下記で記録|
|`.venv/Scripts/python -m pytest -q -p no:faulthandler`|最終コードで44 passed。faulthandlerのWindows例外トレースを無効化するだけで、テストや検証条件は無効化していない|
|`.venv/Scripts/python -m evaluation.final freeze --output evaluation/results/development-v1`|探索評価前の設定・ハッシュ保存|
|`.venv/Scripts/python -m evaluation.final run --output evaluation/results/development-v1 --stage development`|30ケース、失敗0。詳細と所要時間は保存レポート|
|`.venv/Scripts/python run.py`|127.0.0.1:5000で起動（debug無効）|
|`npx --yes agent-browser open http://127.0.0.1:5000`|Windowsのdaemon起動に失敗。既存Chromiumのパス指定でも同じ。installはダウンロード先への通信がタイムアウト|
|`.venv/Scripts/python -m tests.ui_check --browser-path <既存Chromiumのchrome.exe>`|Playwrightへ切替え、以下の実操作を確認|
|`.venv/Scripts/python -m evaluation.final freeze --output evaluation/results/final-v1`|最終コード・設定・データ・依存・seedのハッシュを採点前に保存|
|`.venv/Scripts/python -m evaluation.final run --output evaluation/results/final-v1 --stage final`|未使用120ケースを一度採点。11.09秒、失敗0。結果を見て設定を変更していない|
|`.venv/Scripts/python -m evaluation.final verify --output evaluation/results/final-v1`|採点後も凍結ハッシュ一致|

初回UI確認でfaviconの404を検出し、204を返すルートを追加してサーバーを再起動しました。成功した最終UI確認では、不正CSVに対する意図した400以外のconsole/page errorはありませんでした。アプリの外部リクエストは0件です。

## 確認した操作

- 画面表示、サンプル実行、容量不足日・着手期限・グラフ・GB単位。
- 精度詳細を開き、3手法×7/30日の6行と採点期間・予測起点を確認。
- JSON・CSVを実際にダウンロードし、90日分の行数と着手期限を確認。
- サンプルCSVのダウンロードと再取込。そのCSV自身の過去バックテストとして表示。
- 不正CSVの日本語エラー。古い結果には条件変更の表示。
- 既に満杯、整備期間の逆算で期限超過、期間内未到達。
- 1280pxと390pxでページ全体の横はみ出しなし。モバイルの精度表のみ横スクロールを許容。
- 7日・30日・90日の表示。短い予測期間では日付ラベルの間隔を確保。
- リクエスト中の入力・ボタン無効化、連続クリックが1リクエストだけになること。

自動確認に加え、PC・スマホの保存スクリーンショットを開き、カード・グラフ・シナリオ・評価表示を目視しました。

証跡：[UI操作記録](verification/ui.json)、[テスト出力](verification/pytest.txt)、[PC](screenshots/desktop-1280.png)、[スマホ](screenshots/mobile-390.png)、[計算結果JSON](verification/sample-result.json)、[予測CSV](verification/sample-forecast.csv)。

未実施：実機スマートフォン、Firefox・Safari、スクリーンリーダーの実機操作、負荷・公開環境の検証。幅の確認はChromiumのviewport変更です。アプリの起動・使用にPlaywrightやNode.jsは不要です。
