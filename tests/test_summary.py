"""業務サマリの境界と、評価済み予測結果の不変性を確認する。"""
import json
from pathlib import Path
import pytest
from app import create_app, compute, parse_settings
from forecasting.data import read_csv

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('capacity,headline', [
    (800, '容量上限に到達済み'),
    (1000, '整備の着手期限を超過'),
    (1200, '整備の着手日を設定'),
    (1400, '警戒水準への到達を確認'),
    (9999, '予測期間内の容量上限到達なし'),
])
def test_summary_matches_planning_boundaries(capacity, headline):
    response = create_app().test_client().post('/api/forecast', data={'sample': 'stable', 'capacity': str(capacity)})
    assert response.status_code == 200
    result = response.get_json()
    summary = result['summary']
    assert summary['headline'] == headline
    assert len(summary['items']) == 5
    assert result['as_of'] in summary['text'] and '合成データ' in summary['text']
    assert '過去バックテスト' in summary['text'] and '未来の精度' in summary['text']
    assert 'LLM' not in summary['text']
    if result['plan']['deadline']:
        assert result['plan']['deadline'] in summary['text']
    else:
        assert '算出不可' in summary['text']


def assert_saved_result_matches(actual, expected):
    # NumPyの最終ビットはOSで異なる。日付・分類・手法・整数は厳密に比較する。
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-10)
    elif isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_saved_result_matches(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for value, saved in zip(actual, expected):
            assert_saved_result_matches(value, saved)
    else:
        assert actual == expected


def test_summary_keeps_evaluated_forecast_unchanged():
    previous = json.loads((ROOT/'docs/verification/sample-result.json').read_text(encoding='utf-8'))
    frame = read_csv((ROOT/'data/demo/observed/stable-0.csv').read_bytes())
    current = compute(frame, parse_settings({}), '合成データ')
    for key in ('forecast', 'plan', 'parameters', 'selected_model', 'history', 'scenarios'):
        assert_saved_result_matches(current[key], previous[key])
