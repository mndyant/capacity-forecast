# リーク対策と監査テスト

合成データで評価／実データ未検証。対策とテストの範囲を示します。リークや過学習が無条件になくなるという主張ではありません。

|対策|対応する tests/test_audit.py のテスト|
|---|---|
|同じ起点より未来の正解を大幅に改変・追加しても予測・選択・fitパラメータが不変|test_future_mutation_and_append_do_not_change_forecast_or_selection|
|監査期間をモデル選択に使わない|test_audit_values_do_not_affect_selection|
|全foldで学習終了日より採点開始日が後、開発の採点範囲は監査前|test_all_fold_boundaries（9種類の観測長）|
|評価器がfitに渡すのは過去のdate,used_gbだけ、seedや正解列を落とす|test_evaluator_only_passes_past_and_no_metadata|
|平均・傾き・平滑化を各foldの過去だけで再計算|test_fit_only_uses_past_and_anchors（3手法）|
|比較基準が30増分であること|test_mean30_uses_30_increments|
|容量到達日と着手期限の手計算照合、期限超過、満杯、未到達|test_planning_matches_hand_calculation|
|増加0と比較基準誤差0のN/A処理|test_zero_growth|
|重複、欠損、減少、無限値、非数値、単位文字、月次などの拒否|test_csv_errors|
|seed再現性・観測と未来の分離・非減少性|test_reproducible_synthetic_data（6シナリオ）|
|見逃し・誤警報・両方未到達・既に満杯を区別し、日付誤差の0に混ぜない|test_hit_categories_exclude_non_comparable_cases|
|失敗を集計から黙って消さない|test_failures_are_counted|
|改行差によるハッシュ不一致を防ぐ|test_hash_normalizes_windows_line_endings|
|凍結後の変更・凍結記録の上書きを拒否|test_freeze_refuses_changes_and_overwrite|
|通常APIは未来の正解・メタデータのファイルを読まない|test_normal_app_never_reads_truth_or_metadata|
|取込CSVのAPI経路と設定値の検証|test_api_upload_flow_and_invalid_settings|

自動補間・標準化・外れ値除去・特徴量選択・中央移動平均は行いません。実績を非減少へ直すこともありません。非負制約は将来の増分だけです。最終予測は90日を一度に作り、将来の実績で途中更新しません。

最終採点器は全モデルの予測を先に作り、その後にだけ未来の正解ファイルを開きます。通常のWebサービスは `observed/` のみを読み、サンプル名以外のパス指定を受け付けません。説明テンプレートにも観測系列・生成メタデータを渡さず、計算済みの結果・評価・前提だけを渡します。

実行結果は [pytest.txt](verification/pytest.txt)、実ブラウザ確認は [ui.json](verification/ui.json) に保存。最終設定・ソース・データの照合は `python -m evaluation.final verify` で実行できます。

Claudeに独立した読み取り専用レビューを2回依頼しました。短いCSVの分割、同率選択、実行時境界検証、凍結対象、失敗途中のfold除去などを最終採点前に反映しています。[2回目のレビュー原文](claude-review.txt)は修正前の指摘を含む記録として残しています。

残る限界：テストは実装した入力・分割に対するものです。データの収集時刻や、CSVの各値が実際にその日に利用できたかは確認できません。入力に既に未来由来の集計が含まれている場合は利用者側の監査が必要です。生成器と予測器は有限の仮定に依存し、未知の分布や業務変更への過学習を排除できません。凍結記録はローカルの改変検知であり、第三者署名付きの改ざん防止ログではありません。
