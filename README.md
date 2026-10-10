# 容量予測・整備計画

蓄積する使用量から「容量不足の見込み日」と「整備に着手する期限」を計算する日本語Webアプリです。予測値を、対応事項と報告用サマリへつなげます。

**[公開デモ](https://capacity-forecast.vercel.app/) · [評価結果](docs/evaluation.md)**

![容量・着手期限を確認するPC画面](docs/screenshots/business-ui/desktop-1280.png)

## まず試す

1. サンプル「安定した増加」で「予測を実行」を押します。
2. 容量不足日と着手期限を確認します。**着手期限 = 到達日 − 整備期間 − 安全余裕**です。
3. 容量上限を1000GBへ変えて再計算し、サマリTXTを保存します。

公開デモは合成データで試してください。CSVはクラウドのサーバーへ送信されます。アプリはファイル・DBに保存しません。自分のPC内で使う場合は下のローカル手順を使います。

## 実装で工夫したこと

| 判断 | 実装・確認方法 |
|---|---|
| データの意味を守る | 連続日次CSVの欠損・重複・負値・減少を拒否。予測の基準日は最終観測日 |
| 単純な手法と比較する | 増分平均・線形トレンド・指数平滑化を同条件で比較。開発区間で選び、監査・最終採点を分離 |
| 評価を再現できるようにする | 未使用seed・凍結ハッシュ・全ケースの結果を公開。未来の実績を予測入力に渡さない |
| 古い結果を保存させない | 条件変更・入力エラー時に出力を停止。数値と日本語サマリは同じ計算結果から生成 |

**Python / Flask / NumPy / pandas / HTML / CSS / JavaScript / SVG**。実行時のLLM・APIキーは不要です。

## 評価と限界

合成データ6シナリオ・120ケースで評価しました。**実業務データでの有効性は未検証**です。

| 使用量MAE（GB） | 比較基準 | 選択手法 |
|---|---:|---:|
| 7日間 | 4.666 | 4.340 |
| 30日間 | 13.851 | 13.200 |
| 90日間 | 34.039 | 45.570 |

90日間は基準より**33.9%悪化**しました。到達日・着手期限のMAEは比較可能な34ケースで0.676日です。期間内未到達70ケース・既に満杯16ケースは日付誤差から除外しています。突発変化・削除・長期成長の変化は扱いきれません。[全結果](docs/evaluation.md)・[リーク監査](docs/leakage-audit.md)を公開しています。

## ローカルで動かす

Python 3.14.3での既存検証記録があります。PowerShellの例です。

```powershell
git clone https://github.com/mndyant/capacity-forecast.git
cd capacity-forecast
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python run.py
```

`http://127.0.0.1:5000` を開きます。初回の依存インストール後は外部サービスへ通信しません。公開デモは `feat/vercel-demo`、この手順は `main` の構成です。

入力はUTF-8の `date,used_gb`、連続90〜3650日、2MB以内です。[CSV例・操作・テスト・評価再現](docs/USAGE_GUIDE.md)を参照してください。

## 関連資料・利用条件

[UIとサマリの設計](docs/business-ui.md) · [仕様](capacity-forecast-codex-handoff.md) · [素材・依存の由来](docs/provenance.md) · [利用条件](RIGHTS.md)

[バッチ予測](https://github.com/mndyant/batch-runtime-forecast)は日次の件数・所要時間から締切超過を扱う別作品です。本作は減少のない蓄積量と、整備期間の逆算を扱います。採用選考・学習時の閲覧と動作確認を目的に公開し、再利用ライセンスの付与は保留しています。
