"""検証済みの計算結果から、業務確認用サマリを作る。外部通信はしない。"""


def build_summary(result):
    settings, plan = result['settings'], result['plan']
    current = result['history'][-1]['used_gb']
    ending = result['forecast'][-1]
    remaining = settings['capacity'] - current
    if current >= settings['capacity']:
        headline = '容量上限に到達済み'
        action = '使用状況を確認し、容量確保または使用量の抑制を検討してください。'
    elif plan['days_to_deadline'] is not None and plan['days_to_deadline'] < 0:
        headline = '整備の着手期限を超過'
        action = '整備期間を確保できない見込みです。作業日程の前倒しと暫定対応を検討してください。'
    elif plan['deadline']:
        headline = '整備の着手日を設定'
        action = f"{plan['deadline']}までに着手できるよう、調達・承認・作業日程を確認してください。"
    elif plan['warning_date']:
        headline = '警戒水準への到達を確認'
        action = f"警戒水準への到達は{plan['warning_date']}です。使用量を継続監視し、整備の要否を確認してください。"
    else:
        headline = '予測期間内の容量上限到達なし'
        action = '今回の予測期間内では着手期限を算出できません。実績を追加して定期的に再計算してください。'
    audit = next(row for row in result['evaluation']['summary']
                 if row['model'] == result['selected_model'] and row['horizon'] == 30)
    comparison = ('比較基準の誤差が0のため改善率は算出不可。' if audit['improvement_pct'] is None
                  else f"比較基準に対する改善率 {audit['improvement_pct']:+.1f}%（負の値は悪化）。")
    audit_rows = result['evaluation']['audit']
    period = f"{min(r['test_start'] for r in audit_rows)}〜{max(r['test_end'] for r in audit_rows)}"
    items = [
        {'label': '現状', 'value': f"使用量 {current:,.1f} GB / 上限 {settings['capacity']:,.1f} GB（使用率 {plan['utilization_pct']:.1f}%）。" +
         (f"空き容量 {remaining:,.1f} GB。" if remaining >= 0 else f"上限超過量 {-remaining:,.1f} GB。")},
        {'label': '予測', 'value': f"{ending['date']}の予測使用量 {ending['used_gb']:,.1f} GB。容量上限到達日：{plan['hit_date'] or '予測期間内は未到達'}。"},
        {'label': '着手期限', 'value': f"{plan['deadline'] or '予測期間内では算出不可'}。整備期間 {settings['lead']}日＋安全余裕 {settings['buffer']}日で逆算。"},
        {'label': '対応事項', 'value': action},
        {'label': '評価', 'value': f"当該データの過去バックテスト（採点期間 {period}）。採用手法の30日間MAE {audit['mae']:.2f} GB。{comparison}"},
    ]
    assumptions = '削除・大幅な運用変更がない前提。期限は観測終了日を基準とする暦日計算。条件別の比較は確率付き予測区間ではありません。未来の精度や予測期間外の安全は保証しません。'
    lines = ['容量予測・整備計画 サマリ', f"判定：{headline}",
             f"データ：{result['source']}", f"観測期間：{result['history'][0]['date']}〜{result['as_of']}（{result['observations']}点）",
             f"予測期間：{result['forecast'][0]['date']}〜{ending['date']}（{settings['horizon']}日）",
             f"採用手法：{result['model_label']} / 1日あたりの増加量 {result['parameters']['rate']:.2f} GB",
             f"警戒水準：{settings['warning_pct']:g}% / 比較する増加率：{settings['pace']:g}%", '']
    lines += [f"{item['label']}：{item['value']}" for item in items]
    lines += ['', '増加率別の比較（基準予測の増加量を100%とする条件比較）']
    lines += [f"{s['multiplier']*100:g}%：容量上限到達 {s['plan']['hit_date'] or '期間内未到達'} / 着手期限 {s['plan']['deadline'] or '算出不可'}" for s in result['scenarios']]
    lines += ['', f'前提・制約：{assumptions}', result['limitations']]
    return {'headline': headline, 'items': items, 'assumptions': assumptions, 'text': '\n'.join(lines)+'\n'}
