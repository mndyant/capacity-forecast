"""境界を実際に改変するリーク監査と、手計算・入力・APIの確認。"""
import io
import numpy as np
import pandas as pd
import pytest
import evaluation.backtest as backtest
from app import create_app, compute, parse_settings
from forecasting.data import read_csv
from forecasting.models import MODELS, predict
from forecasting.planning import plan
from evaluation.final import hit_metrics, aggregate, digest
import evaluation.final as final_evaluation
from scripts.generate_demo import generate, SCENARIOS


@pytest.fixture
def history():
    return generate('regime',0)[0]


def csv(frame):
    return frame.to_csv(index=False,date_format='%Y-%m-%d').encode()


def signature(frame, origin=180):
    past=frame.iloc[:origin][['date','used_gb']]
    model, _, scores=backtest.select_model(past)
    p=backtest.forecast_at(frame,origin,90,model)
    return model,scores,p['values'],p['parameters']


def test_future_mutation_and_append_do_not_change_forecast_or_selection(history):
    _,future,_=generate('regime',0)
    full=pd.concat([history,future],ignore_index=True)
    before=signature(full)
    full.loc[180:,'used_gb']+=1e8
    after=signature(full)
    appended=signature(pd.concat([full,future.assign(date=future.date+pd.Timedelta(days=90))],ignore_index=True))
    alone=signature(history)
    for other in (after,appended,alone):
        assert before[:2]==other[:2]
        np.testing.assert_array_equal(before[2],other[2])
        assert before[3]==other[3]


def test_audit_values_do_not_affect_selection(history):
    before=backtest.select_model(history)
    altered=history.copy();altered.loc[120:,'used_gb']+=1e7
    after=backtest.select_model(altered)
    assert before[0]==after[0] and before[2]==after[2]


@pytest.mark.parametrize('n',[90,119,120,149,150,157,178,180,365])
def test_all_fold_boundaries(n):
    history=generate('stable',0,days=n)[0]
    dev,audit=backtest.origins(n)
    assert all(o>=60 and o+30<=n for o in dev+audit)
    assert not dev or max(dev)+30<=min(audit)
    rows=backtest.backtest(history,dev+audit,'test')
    assert all(r['train_end']<r['test_start'] for r in rows)
    if n==180:
        assert dev==[60,67,74,81,88] and audit==[120,127,134,141,148]


def test_evaluator_only_passes_past_and_no_metadata(monkeypatch,history):
    original=backtest.predict; observed=[]
    def spy(frame,horizon,model):
        assert list(frame.columns)==['date','used_gb']
        expected=history.iloc[:len(frame)]
        pd.testing.assert_frame_equal(frame,expected)
        prediction=original(frame,horizon,model)
        assert prediction['parameters']['fit_end']==str(expected.date.iloc[-1].date())
        observed.append(len(frame))
        return prediction
    monkeypatch.setattr(backtest,'predict',spy)
    rich=history.assign(seed=3,scenario='secret',future_value=99999)
    backtest.backtest(rich,[60,67,74,81,88,120,127,134,141,148],'audit')
    assert len(observed)==30


@pytest.mark.parametrize('model',MODELS)
def test_fit_only_uses_past_and_anchors(history,model):
    original=backtest.forecast_at(history,60,30,model)
    altered=history.copy();altered.loc[60:,'used_gb']*=100
    changed=backtest.forecast_at(altered,60,30,model)
    assert original['parameters']==changed['parameters']
    np.testing.assert_array_equal(original['values'],changed['values'])
    assert original['values'][0]==pytest.approx(history.used_gb.iloc[59]+original['parameters']['rate'])


def test_mean30_uses_30_increments():
    frame=pd.DataFrame({'date':pd.date_range('2026-01-01',periods=60),'used_gb':np.r_[np.arange(29),100+np.arange(31)*2.]})
    assert predict(frame,7)['parameters']['rate']==2.


def test_planning_matches_hand_calculation():
    p={'dates':pd.date_range('2026-07-01',periods=30),'values':np.arange(101,131)}
    result=plan(100,p,110,80,3,2,'2026-06-30')
    assert result['hit_date']=='2026-07-10'
    assert result['deadline']=='2026-07-05'
    assert result['days_to_deadline']==5
    assert plan(100,p,110,80,20,2,'2026-06-30')['status']=='overdue'
    assert plan(100,p,100,80,3,2,'2026-06-30')['hit_date']=='2026-06-30'
    assert plan(100,p,999,80,3,2,'2026-06-30')['hit_date'] is None


@pytest.mark.parametrize('model',MODELS)
def test_zero_growth(model):
    frame=pd.DataFrame({'date':pd.date_range('2026-01-01',periods=180),'used_gb':100.})
    p=predict(frame,90,model)
    assert all(p['values']==100)
    assert plan(100,p,110,80,30,7,frame.date.iloc[-1])['deadline'] is None
    assert all(r['improvement_pct'] is None for r in backtest.evaluate_history(frame)['summary'])


@pytest.mark.parametrize('kind',['duplicate','gap','negative','nan','inf','unit','decrease','short','bad_date','monthly','missing','columns'])
def test_csv_errors(history,kind):
    f=history.copy()
    if kind=='duplicate':f.loc[1,'date']=f.loc[0,'date']
    if kind=='gap':f=f.drop(3)
    if kind=='negative':f.loc[3,'used_gb']=-1
    if kind=='nan':f.loc[3,'used_gb']=np.nan
    if kind=='inf':f.loc[3,'used_gb']=np.inf
    if kind=='decrease':f.loc[3,'used_gb']=1
    if kind=='short':f=f.iloc[:89]
    if kind=='columns':f=f.rename(columns={'used_gb':'used_tb'})
    content=csv(f)
    if kind=='unit':content=content.replace(b'400.',b'400GB.',1) if b'400.' in content else content.replace(b'\n',b'\n2026-01-01,3TB\n',1)
    if kind=='bad_date':content=content.replace(b'2026-01-01',b'2026-02-30')
    if kind=='monthly':content=b'date,used_gb\n2026-01-01,1\n2026-02-01,2\n'
    if kind=='missing':content=content.replace(b'2026-01-01',b'')
    with pytest.raises(ValueError): read_csv(content)


@pytest.mark.parametrize('scenario',SCENARIOS)
def test_reproducible_synthetic_data(scenario):
    a,b,meta=generate(scenario,3);c,d,other=generate(scenario,3)
    assert len(a)==180 and len(b)==90
    pd.testing.assert_frame_equal(a,c);pd.testing.assert_frame_equal(b,d)
    assert meta==other
    assert (pd.concat([a,b]).used_gb.diff().dropna()>=0).all()


def test_hit_categories_exclude_non_comparable_cases():
    dates=pd.date_range('2026-07-01',periods=7)
    truth=pd.DataFrame({'date':dates,'used_gb':np.arange(101,108)})
    p={'dates':dates,'values':np.arange(102,116,2)}
    assert hit_metrics(100,p,truth,106,'2026-06-30')['hit_error_days']==-3
    assert hit_metrics(100,p,truth,110,'2026-06-30')['hit_category']=='false_alarm'
    assert hit_metrics(100,{'dates':dates,'values':[100]*7},truth,106,'2026-06-30')['hit_category']=='miss'
    neither=hit_metrics(100,p,truth,999,'2026-06-30')
    assert neither['hit_category']=='neither_hit' and neither['hit_error_days'] is None
    assert hit_metrics(100,p,truth,99,'2026-06-30')['hit_category']=='already_full'


def test_failures_are_counted():
    rows=[{'model':'mean30','horizon':90,'failure':'失敗'}]
    summary=aggregate(rows)
    row=next(r for r in summary if r['model']=='mean30' and r['horizon']==90)
    assert row['cases']==1 and row['failures']==1 and row['mae_mean'] is None


def test_hash_normalizes_windows_line_endings(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.write_bytes(b'a\nb\n');b.write_bytes(b'a\r\nb\r\n')
    assert digest(a)==digest(b)


def test_freeze_refuses_changes_and_overwrite(tmp_path,monkeypatch):
    monkeypatch.setattr(final_evaluation,'snapshot',lambda:{'config_hash':'before'})
    final_evaluation.freeze(tmp_path)
    final_evaluation.verify_freeze(tmp_path)
    with pytest.raises(ValueError,match='上書き'):
        final_evaluation.freeze(tmp_path)
    monkeypatch.setattr(final_evaluation,'snapshot',lambda:{'config_hash':'after'})
    with pytest.raises(ValueError,match='凍結後'):
        final_evaluation.verify_freeze(tmp_path)


def test_normal_app_never_reads_truth_or_metadata(monkeypatch):
    from pathlib import Path
    original=Path.read_bytes
    opened=[]
    def checked(path):
        assert 'truth' not in path.parts and 'metadata' not in path.parts
        opened.append(path)
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',checked)
    client=create_app().test_client()
    assert client.post('/api/forecast',data={'sample':'stable'}).status_code==200
    assert any('observed' in p.parts for p in opened)


def test_api_upload_flow_and_invalid_settings(history):
    client=create_app().test_client()
    assert client.get('/').status_code==200
    response=client.post('/api/forecast',data={'file':(io.BytesIO(csv(history)),'test.csv'),'capacity':'1200'})
    assert response.status_code==200
    body=response.get_json()
    assert len(body['history'])==180 and len(body['forecast'])==90
    assert '取込CSV' in body['source'] and body['evaluation']['audit']
    assert body['plan']['deadline'] is not None
    for field,value in [('capacity','nan'),('horizon','8'),('lead','1.5'),('buffer','-1'),('pace','inf')]:
        response=client.post('/api/forecast',data={field:value})
        assert response.status_code==400 and response.get_json()['error']
    assert client.get('/api/sample/unknown').status_code==404
