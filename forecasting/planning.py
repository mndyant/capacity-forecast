"""予測期間内の到達日と暦日による整備期限。"""
import pandas as pd


def first_hit(current, values, dates, threshold, as_of):
    if current >= threshold:
        return pd.Timestamp(as_of)
    return next((pd.Timestamp(d) for v, d in zip(values, dates) if v >= threshold), None)


def plan(current, prediction, capacity, warning_pct, lead, buffer, as_of):
    hit = first_hit(current, prediction['values'], prediction['dates'], capacity, as_of)
    warning = first_hit(current, prediction['values'], prediction['dates'], capacity*warning_pct/100, as_of)
    deadline = hit-pd.Timedelta(days=lead+buffer) if hit is not None else None
    as_of = pd.Timestamp(as_of)
    if current >= capacity:
        status, message = 'overdue', '！すでに容量上限に到達しています'
    elif deadline is not None and deadline < as_of:
        status, message = 'overdue', '！整備期間を考慮すると着手期限を過ぎています'
    elif deadline is not None or warning is not None:
        status, message = 'attention', '△ 注意：整備計画を確認してください'
    else:
        status, message = 'normal', '✓ 予測期間内に到達見込みなし'
    fmt = lambda d: d.strftime('%Y-%m-%d') if d is not None else None
    return {'hit_date': fmt(hit), 'warning_date': fmt(warning), 'deadline': fmt(deadline),
            'status': status, 'message': message, 'utilization_pct': current/capacity*100,
            'days_to_deadline': (deadline-as_of).days if deadline is not None else None}
