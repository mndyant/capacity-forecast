"""合成データ生成。未来の正解はobservedとは別のディレクトリへ保存。"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

SCENARIOS = {'stable': '安定した増加', 'accelerating': '徐々に加速', 'weekday': '曜日差',
             'regime': '途中でペースが変化', 'burst': '突発的な大量登録', 'stagnant': '停滞期間'}
DEFAULTS = {'initial_gb': 400., 'daily_gb': 3., 'noise': .35}


def generate(scenario, seed, start='2026-01-01', days=180, future=90, settings=None):
    settings = {**DEFAULTS, **(settings or {})}
    if scenario not in SCENARIOS or days < 90 or future < 1:
        raise ValueError('シナリオ、観測90日以上、未来1日以上を指定してください。')
    rng = np.random.default_rng(np.random.SeedSequence([seed, list(SCENARIOS).index(scenario)]))
    count = days+future
    t = np.arange(count)
    dates = pd.date_range(start, periods=count)
    base = settings['daily_gb']
    # ガンマ乱数、緩い波、構造変化、イベントを組み合わせ、単一直線だけにしない。
    noise = rng.gamma(2., settings['noise']/2, count)-settings['noise']
    rate = base+noise+.2*np.sin(t/11)
    events = []
    if scenario == 'accelerating':
        rate += .00008*t**2
    elif scenario == 'weekday':
        rate *= np.where(dates.dayofweek < 5, 1.4, .25)
    elif scenario == 'regime':
        change = int(rng.integers(95, 150))
        rate[t >= change] *= 2.2
        events = [change]
    elif scenario == 'burst':
        events = sorted(rng.choice(np.arange(20, count), size=max(2, count//65), replace=False).tolist())
        rate[events] += rng.uniform(60, 140, len(events))
    elif scenario == 'stagnant':
        rate[(t//35)%3 == 1] = 0
        rate[t > int(count*.7)] *= .15
    rate = np.maximum(0., rate)
    values = np.round(settings['initial_gb']+np.cumsum(rate), 6)
    frame = pd.DataFrame({'date': dates, 'used_gb': values})
    return frame.iloc[:days].copy(), frame.iloc[days:].copy(), {
        'kind': '合成データ', 'scenario': scenario, 'seed': seed, 'start': start,
        'days': days, 'future_days': future, 'settings': settings, 'events_index': events,
        'generator_version': 1}


def write_case(root, scenario, seed, **kwargs):
    observed, future, metadata = generate(scenario, seed, **kwargs)
    case = f'{scenario}-{seed}'
    for folder, frame in [('observed', observed), ('truth', future)]:
        (root/folder).mkdir(parents=True, exist_ok=True)
        frame.to_csv(root/folder/f'{case}.csv', index=False, date_format='%Y-%m-%d', lineterminator='\n')
    (root/'metadata').mkdir(parents=True, exist_ok=True)
    (root/'metadata'/f'{case}.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='再現可能な合成データを生成')
    parser.add_argument('--output', default='data/demo')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--scenario', choices=SCENARIOS)
    parser.add_argument('--start', default='2026-01-01')
    parser.add_argument('--days', type=int, default=180)
    parser.add_argument('--future', type=int, default=90)
    parser.add_argument('--initial-gb', type=float, default=400.)
    parser.add_argument('--daily-gb', type=float, default=3.)
    parser.add_argument('--noise', type=float, default=.35)
    args = parser.parse_args()
    if args.initial_gb < 0 or args.daily_gb < 0 or args.noise < 0:
        parser.error('生成設定は0以上にしてください。')
    for scenario in ([args.scenario] if args.scenario else SCENARIOS):
        for seed in ([args.seed] if args.seed is not None else list(range(5))+list(range(100,120))):
            write_case(Path(args.output), scenario, seed, start=args.start, days=args.days, future=args.future,
                       settings={'initial_gb': args.initial_gb, 'daily_gb': args.daily_gb, 'noise': args.noise})
    print('合成データを保存しました（観測と未来の正解は別ファイル）。')


if __name__ == '__main__':
    main()
