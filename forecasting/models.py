"""少数の固定候補。fitに渡すのは切り出した過去2列だけ。"""
from time import perf_counter
import numpy as np
import pandas as pd

MODELS = ('mean30', 'linear', 'ses')
LABELS = {'mean30': '直近30日平均（比較基準）', 'linear': '線形トレンド', 'ses': '増加量の指数平滑化'}
ALPHA = 0.2


def predict(history, horizon, model='mean30'):
    if list(history.columns) != ['date', 'used_gb'] or len(history) < 2:
        raise ValueError('モデル入力は観測済みのdate,used_gbだけにしてください。')
    if model not in MODELS or horizon not in range(1, 91):
        raise ValueError('予測手法または期間が不正です。')
    start = perf_counter()
    y = history.used_gb.to_numpy(dtype=float)
    increments = np.diff(y)
    if model == 'mean30':
        raw_rate = float(increments[-30:].mean())
    elif model == 'linear':
        x = np.arange(len(y), dtype=float)
        raw_rate = float(np.dot(x-x.mean(), y-y.mean()) / np.dot(x-x.mean(), x-x.mean()))
    else:
        raw_rate = float(increments[0])
        for value in increments[1:]:
            raw_rate = ALPHA * float(value) + (1-ALPHA) * raw_rate
    rate = max(0., raw_rate)
    fit_ms = (perf_counter()-start)*1000
    start = perf_counter()
    # 全候補で最終観測値を起点とし、不連続を避ける。実績は変更しない。
    values = y[-1] + rate * np.arange(1, horizon+1)
    dates = pd.date_range(history.date.iloc[-1]+pd.Timedelta(days=1), periods=horizon)
    return {'values': values, 'dates': dates, 'parameters': {'raw_rate': raw_rate, 'rate': rate,
            'alpha': ALPHA if model == 'ses' else None, 'fit_count': len(y),
            'fit_end': history.date.iloc[-1].strftime('%Y-%m-%d')},
            'fit_ms': fit_ms, 'predict_ms': (perf_counter()-start)*1000}
