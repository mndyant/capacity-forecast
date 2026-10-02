"""時間順の分割、固定選択規則、公平な比較。"""
import numpy as np
from forecasting.models import MODELS, predict

SELECTION_RULE = '開発foldの30日間MAE。最小値×1.05＋0.01GB以内を同程度とし mean30,linear,ses の順を優先。'


def origins(n):
    # 180点では仕様通り。短いCSVは監査30日を確保し開発foldを減らす。
    end = max(60, n-60)
    development = list(range(60, end-29, 7))[-5:]
    audit = list(range(end, n-29, 7))[:5]
    return development, audit


def metrics(truth, values, current):
    error = np.asarray(values)-np.asarray(truth)
    return {'mae': float(np.mean(np.abs(error))), 'rmse': float(np.sqrt(np.mean(error**2))),
            'endpoint_error': float(error[-1]), 'endpoint_abs_error': float(abs(error[-1])),
            'growth_error': float((values[-1]-current)-(truth[-1]-current))}


def forecast_at(frame, origin, horizon, model):
    # 正解・追加列は境界の外。fitは各foldで独立にやり直す。
    history = frame.iloc[:origin][['date', 'used_gb']].copy()
    return predict(history, horizon, model)


def backtest(frame, points, stage):
    rows = []
    for origin in points:
        for model in MODELS:
            prediction = forecast_at(frame, origin, 30, model)
            for horizon in (7, 30):
                truth = frame.iloc[origin:origin+horizon]
                if len(truth) != horizon or frame.date.iloc[origin-1] >= truth.date.iloc[0]:
                    raise ValueError('学習と採点の時系列境界が不正です。')
                rows.append({'stage': stage, 'origin': origin, 'model': model, 'horizon': horizon,
                    'train_start': str(frame.date.iloc[0].date()), 'train_end': str(frame.date.iloc[origin-1].date()),
                    'test_start': str(truth.date.iloc[0].date()), 'test_end': str(truth.date.iloc[-1].date()),
                    **metrics(truth.used_gb.to_numpy(), prediction['values'][:horizon], frame.used_gb.iloc[origin-1]),
                    'fit_ms': prediction['fit_ms'], 'predict_ms': prediction['predict_ms']})
    return rows


def select_model(frame):
    development, _ = origins(len(frame))
    rows = backtest(frame, development, 'development')
    if not rows:
        return 'mean30', rows, {}
    scores = {m: float(np.mean([r['mae'] for r in rows if r['model']==m and r['horizon']==30])) for m in MODELS}
    best = min(scores.values())
    selected = next(m for m in MODELS if scores[m] <= best*1.05+.01)
    return selected, rows, scores


def evaluate_history(frame):
    model, development, scores = select_model(frame)
    _, audit = origins(len(frame))
    rows = backtest(frame, audit, 'audit')
    summary = []
    for horizon in (7, 30):
        baseline = np.mean([r['mae'] for r in rows if r['model']=='mean30' and r['horizon']==horizon])
        for candidate in MODELS:
            cases = [r for r in rows if r['model']==candidate and r['horizon']==horizon]
            mae = float(np.mean([r['mae'] for r in cases]))
            summary.append({'model': candidate, 'horizon': horizon, 'mae': mae,
                'rmse': float(np.sqrt(np.mean([r['rmse']**2 for r in cases]))),
                'endpoint_abs_error': float(np.mean([r['endpoint_abs_error'] for r in cases])),
                'growth_abs_error': float(np.mean([abs(r['growth_error']) for r in cases])),
                'improvement_pct': None if baseline < 1e-10 else float(100*(1-mae/baseline)), 'folds': len(cases)})
    return {'selected': model, 'selection_rule': SELECTION_RULE, 'selection_scores': scores,
            'development': development, 'audit': rows, 'summary': summary,
            'fallback': not bool(development)}
