"""凍結記録を先に作り、全ケースを採点する。結果の上書きを禁止。"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import numpy as np
import pandas as pd
from forecasting.data import read_csv
from forecasting.models import MODELS, predict
from forecasting.planning import first_hit
from evaluation.backtest import evaluate_history, metrics

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def snapshot():
    config = json.loads((ROOT/'evaluation/protocol.json').read_text(encoding='utf-8'))
    sources = [p for folder in ('forecasting','evaluation','scripts','app','tests') for p in (ROOT/folder).rglob('*.py')]
    sources += [p for p in (ROOT/'app').rglob('*') if p.suffix in ('.html','.css','.js')]
    sources += [ROOT/'run.py', ROOT/'requirements.txt', ROOT/'requirements-dev.txt', ROOT/'pytest.ini', ROOT/'docs/explanation-input.schema.json']
    data = sorted((ROOT/'data/demo').rglob('*.csv'))+sorted((ROOT/'data/demo').rglob('*.json'))
    return {'config': config, 'config_hash': hashlib.sha256(json.dumps(config,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'source_hashes': {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(sources)},
        'data_hashes': {p.relative_to(ROOT).as_posix(): digest(p) for p in data},
        'versions': {p: importlib.metadata.version(p) for p in ['flask','numpy','pandas','pytest']},
        'python': platform.python_version()}


def freeze(output):
    output.mkdir(parents=True, exist_ok=True)
    target = output/'frozen.json'
    if target.exists():
        raise ValueError('凍結記録は上書きしません。別の出力先を使ってください。')
    record = snapshot()
    record['frozen_at'] = datetime.now(timezone.utc).isoformat()
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return record


def verify_freeze(output):
    recorded = json.loads((output/'frozen.json').read_text(encoding='utf-8'))
    current = snapshot()
    for key in current:
        if current[key] != recorded.get(key):
            raise ValueError(f'凍結後に{key}が変わっています。採点を停止しました。')
    return recorded


def hit_metrics(current, prediction, truth, capacity, as_of, lead=30, buffer=7):
    pred = first_hit(current,prediction['values'],prediction['dates'],capacity,as_of)
    actual = first_hit(current,truth.used_gb,truth.date,capacity,as_of)
    pred_deadline = pred-pd.Timedelta(days=lead+buffer) if pred is not None else None
    true_deadline = actual-pd.Timedelta(days=lead+buffer) if actual is not None else None
    fmt = lambda d: str(d.date()) if d is not None else None
    if current >= capacity:
        category, error = 'already_full', None
    elif pred is not None and actual is not None:
        category, error = 'both_hit', (pred-actual).days
    elif actual is not None:
        category, error = 'miss', None
    elif pred is not None:
        category, error = 'false_alarm', None
    else:
        category, error = 'neither_hit', None
    return {'hit_category': category, 'hit_error_days': error, 'deadline_error_days': error,
        'predicted_hit': fmt(pred), 'actual_hit': fmt(actual), 'predicted_deadline': fmt(pred_deadline),
        'actual_deadline': fmt(true_deadline)}


def aggregate(rows):
    out=[]
    for model in (*MODELS,'selected'):
        for horizon in (7,30,90):
            subset=[r for r in rows if r['model']==model and r['horizon']==horizon]
            valid=[r for r in subset if r['failure'] is None]
            errors=[r['mae'] for r in valid]
            categories={k:sum(r['hit_category']==k for r in valid) for k in ('both_hit','miss','false_alarm','neither_hit','already_full')}
            hits=[r['hit_error_days'] for r in valid if r['hit_error_days'] is not None]
            out.append({'model':model,'horizon':horizon,'cases':len(subset),'failures':len(subset)-len(valid),
                'mae_mean':float(np.mean(errors)) if errors else None,'mae_median':float(np.median(errors)) if errors else None,
                'mae_worst':max(errors) if errors else None,
                'rmse_pooled':float(np.sqrt(np.mean([r['rmse']**2 for r in valid]))) if valid else None,
                'endpoint_abs_error_mean':float(np.mean([r['endpoint_abs_error'] for r in valid])) if valid else None,
                'growth_abs_error_mean':float(np.mean([abs(r['growth_error']) for r in valid])) if valid else None,
                'improvement_mean_pct':float(np.mean([r['improvement_pct'] for r in valid if r['improvement_pct'] is not None])) if any(r['improvement_pct'] is not None for r in valid) else None,
                'hit_categories':categories,'hit_comparable':len(hits),
                'hit_mae_days':float(np.mean(np.abs(hits))) if hits else None,
                'hit_bias_days':float(np.mean(hits)) if hits else None,
                'deadline_mae_days':float(np.mean(np.abs(hits))) if hits else None})
    return out


def run(output, stage='final'):
    frozen=verify_freeze(output)
    if (output/'started.json').exists():
        raise ValueError('この記録では採点を開始済みです。既存の結果は上書きしません。')
    config=frozen['config']
    (output/'started.json').write_text(json.dumps({'stage':stage,'started_at':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    start=perf_counter(); rows=[]; folds=[]; selections=[]
    seeds=config['final_seeds'] if stage=='final' else config['development_seeds']
    for scenario in config['scenarios']:
        for seed in seeds:
            case=f'{scenario}-{seed}'
            capacity=1100. if seed%2==0 else 2200.
            try:
                history=read_csv((ROOT/f'data/demo/observed/{case}.csv').read_bytes())
                if len(history)!=180:
                    raise ValueError('評価は観測180点に固定しています。')
                assessment=evaluate_history(history)
                selected=assessment['selected']
                selections.append({'case':case,'selected':selected,'scores':assessment['selection_scores']})
                folds.extend({**r,'case':case,'scenario':scenario,'seed':seed} for r in assessment['development']+assessment['audit'])
                predictions={m:predict(history,90,m) for m in MODELS}
                # モデルへの全呼び出しが終了した後に、評価器だけが正解を読む。
                truth=read_csv((ROOT/f'data/demo/truth/{case}.csv').read_bytes(),minimum=90)
                if len(truth)!=90 or truth.date.iloc[0]!=history.date.iloc[-1]+pd.Timedelta(days=1):
                    raise ValueError('未来90日の採点ファイルの日付が不正です。')
                for horizon in (7,30,90):
                    baseline=metrics(truth.used_gb.to_numpy()[:horizon],predictions['mean30']['values'][:horizon],history.used_gb.iloc[-1])['mae']
                    for model in (*MODELS,'selected'):
                        prediction=predictions[selected if model=='selected' else model]
                        p={**prediction,'values':prediction['values'][:horizon],'dates':prediction['dates'][:horizon]}
                        score=metrics(truth.used_gb.to_numpy()[:horizon],p['values'],history.used_gb.iloc[-1])
                        rows.append({'case':case,'scenario':scenario,'seed':seed,'capacity':capacity,'model':model,'selected':selected,
                            'horizon':horizon,'failure':None,**score,
                            'improvement_pct':None if baseline<1e-10 else 100*(1-score['mae']/baseline),
                            **hit_metrics(history.used_gb.iloc[-1],p,truth.iloc[:horizon],capacity,history.date.iloc[-1],config['lead_days'],config['buffer_days']),
                            'fit_ms':prediction['fit_ms'],'predict_ms':prediction['predict_ms']})
            except Exception as exc:
                # 失敗を残す。同ケースの途中結果は成功として混ぜない。
                rows=[r for r in rows if r['case']!=case]
                folds=[r for r in folds if r['case']!=case]
                selections=[r for r in selections if r['case']!=case]
                rows.extend({'case':case,'scenario':scenario,'seed':seed,'model':m,'horizon':h,'failure':str(exc)} for m in (*MODELS,'selected') for h in (7,30,90))
    summary={'notice':config['notice'],'stage':stage,'elapsed_seconds':perf_counter()-start,'seed_count':len(seeds),
        'case_count':len(seeds)*len(config['scenarios']), 'overall':aggregate(rows),
        'by_scenario':{s:aggregate([r for r in rows if r['scenario']==s]) for s in config['scenarios']},
        'selections':selections, 'worst_selected_90':sorted([r for r in rows if r['model']=='selected' and r['horizon']==90 and r['failure'] is None],key=lambda r:r['mae'],reverse=True)[:10]}
    for name,data in [('summary',summary),('cases',rows),('folds',folds)]:
        (output/f'{name}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame(rows).to_csv(output/'cases.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(folds).to_csv(output/'folds.csv',index=False,encoding='utf-8-sig')
    lines=['# 合成データの評価結果','',config['notice'],'',f"{summary['case_count']}ケース（6シナリオ × {len(seeds)} seed）。所要{summary['elapsed_seconds']:.2f}秒。",'',
        '|手法|日数|MAE平均 GB|MAE中央値|最悪MAE|RMSE|終点誤差|失敗|','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in summary['overall']:
        def f(key): return 'N/A' if r[key] is None else f"{r[key]:.3f}"
        lines.append(f"|{r['model']}|{r['horizon']}|{f('mae_mean')}|{f('mae_median')}|{f('mae_worst')}|{f('rmse_pooled')}|{f('endpoint_abs_error_mean')}|{r['failures']}|")
    lines+=['','到達日・期限誤差は両方が到達する場合のみ。正の符号は予測の遅れ。既に満杯、見逃し、誤警報、両方未到達を0日誤差として混ぜません。','',
        '|手法（90日）|比較可能数|到達/期限MAE 日|見逃し|誤警報|両方未到達|既に満杯|','|---|---:|---:|---:|---:|---:|---:|']
    for r in summary['overall']:
        if r['horizon']==90:
            c=r['hit_categories']; lines.append(f"|{r['model']}|{r['hit_comparable']}|{r['hit_mae_days']}|{c['miss']}|{c['false_alarm']}|{c['neither_hit']}|{c['already_full']}|")
    lines+=['','全ケースは cases.csv / cases.json、開発・監査全foldは folds.csv / folds.json、シナリオ別と悪いケースは summary.json。',
        '学習・予測時間は各行のfit_ms/predict_ms。selected行は採用手法の再掲であり時間を加算しない。',
        '同じケース内の誤差や重複foldは独立標本ではない。6種の生成仮定を20 seedで繰り返しても、120種類の実務環境を検証したことにはならない。']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f"{stage}: {summary['case_count']} cases, {summary['elapsed_seconds']:.2f}s → {output}")


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['freeze','run','verify'])
    parser.add_argument('--output',type=Path,default=ROOT/'evaluation/results/final-v1')
    parser.add_argument('--stage',choices=['development','final'],default='final')
    args=parser.parse_args()
    if args.command=='freeze': freeze(args.output)
    elif args.command=='verify': verify_freeze(args.output); print('凍結ハッシュ一致')
    else: run(args.output,args.stage)
