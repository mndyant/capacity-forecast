"""容量予測Webアプリ。通常の予測経路はtruth/metadataを開かない。"""
import math
from pathlib import Path
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from forecasting.data import read_csv, records
from forecasting.models import predict, LABELS
from forecasting.planning import plan
from forecasting.explanation import TemplateExplainer
from evaluation.backtest import evaluate_history
from app.summary import build_summary

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {'stable': '安定した増加', 'accelerating': '徐々に加速', 'weekday': '曜日差',
           'regime': '途中でペースが変化', 'burst': '突発的な大量登録', 'stagnant': '停滞期間',
           'full': 'すでに満杯（動作確認）'}


def parse_settings(source):
    def number(key, default, low, high, integer=False):
        try:
            value = float(source.get(key, default))
        except (ValueError, TypeError):
            raise ValueError(f'{key}には数値を入力してください。') from None
        names = {'capacity': '上限容量', 'warning_pct': '警戒水準', 'horizon': '予測期間', 'lead': '整備期間', 'buffer': '安全余裕', 'pace': '増加ペース'}
        if not math.isfinite(value) or not low <= value <= high or (integer and value != int(value)):
            raise ValueError(f'{names[key]}は{low}〜{high}の'+('整数' if integer else '数値')+'にしてください。')
        return int(value) if integer else value
    settings = {'capacity': number('capacity',1200, .01,1e12), 'warning_pct': number('warning_pct',80,1,100),
        'horizon': number('horizon',90,7,90,True), 'lead': number('lead',30,0,3650,True),
        'buffer': number('buffer',7,0,3650,True), 'pace': number('pace',130,1,500)}
    if settings['horizon'] not in (7,30,90):
        raise ValueError('予測期間は7日・30日・90日から選んでください。')
    return settings


def compute(frame, settings, source):
    assessment = evaluate_history(frame)
    model = assessment['selected']
    prediction = predict(frame, settings['horizon'], model)
    current = float(frame.used_gb.iloc[-1])
    as_of = str(frame.date.iloc[-1].date())
    def planning(p):
        return plan(current, p, settings['capacity'], settings['warning_pct'], settings['lead'], settings['buffer'], as_of)
    scenarios = []
    for label, multiplier in [('緩やか（70%）',.7), ('中心予測（100%）',1.), (f"指定ペース（{settings['pace']:g}%）",settings['pace']/100)]:
        altered = {**prediction, 'values': current+(prediction['values']-current)*multiplier}
        scenarios.append({'label': label, 'multiplier': multiplier, 'plan': planning(altered),
            'values': altered['values'].tolist()})
    result = {'source': source, 'as_of': as_of, 'observations': len(frame), 'settings': settings,
        'selected_model': model, 'model_label': LABELS[model], 'parameters': prediction['parameters'],
        'plan': planning(prediction), 'history': records(frame),
        'forecast': [{'date': str(d.date()), 'used_gb': float(v)} for d,v in zip(prediction['dates'],prediction['values'])],
        'scenarios': scenarios, 'evaluation': assessment,
        'limitations': '合成データで評価／実データ未検証。90日先は不確実性が大きく、短期の誤差は長期の精度を保証しません。'}
    explanation_input = {key: result[key] for key in ('as_of','parameters','plan','settings','evaluation','limitations')}
    result['explanation'] = TemplateExplainer().explain(explanation_input)
    result['summary'] = build_summary(result)
    return result


def create_app():
    app = Flask(__name__, static_folder=str(ROOT/'public'/'static'), static_url_path='/static')
    app.config['MAX_CONTENT_LENGTH'] = 2*1024*1024
    app.json.ensure_ascii = False

    @app.get('/')
    def index():
        return render_template('index.html', samples=SAMPLES)

    @app.get('/favicon.ico')
    def favicon():
        return '',204

    @app.get('/api/sample/<name>')
    def sample(name):
        if name not in SAMPLES:
            return jsonify(error='サンプルが見つかりません。'),404
        key = 'stable' if name=='full' else name
        return send_file(ROOT/'data'/'demo'/'observed'/f'{key}-0.csv', as_attachment=True, download_name=f'synthetic-{name}.csv')

    @app.post('/api/forecast')
    def forecast():
        try:
            settings = parse_settings(request.form)
            if 'file' in request.files and request.files['file'].filename:
                content = request.files['file'].read()
                source = '取込CSV（データの由来は利用者指定。表示する精度はこのCSV内の過去バックテスト）'
            else:
                name = request.form.get('sample','stable')
                if name not in SAMPLES:
                    raise ValueError('一覧からサンプルを選択してください。')
                key = 'stable' if name=='full' else name
                content = (ROOT/'data'/'demo'/'observed'/f'{key}-0.csv').read_bytes()
                source = f'合成データ：{SAMPLES[name]} / 探索用seed 0'
            frame = read_csv(content)
            return jsonify(compute(frame, settings, source))
        except ValueError as exc:
            return jsonify(error=str(exc)),400

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error='CSVは2MB以下にしてください。'),413

    @app.errorhandler(500)
    def server_error(_):
        return jsonify(error='計算を完了できませんでした。時間をおいて再度お試しください。'),500

    @app.after_request
    def response_headers(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    return app
