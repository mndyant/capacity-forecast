"""CSVの検証。補間や実績の書き換えはしない。"""
import io
import re
import numpy as np
import pandas as pd


def read_csv(content: bytes, minimum: int = 90) -> pd.DataFrame:
    try:
        text = content.decode('utf-8-sig')
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError('UTF-8のCSVを指定してください。列は date,used_gb です。') from exc
    if list(frame.columns) != ['date', 'used_gb']:
        raise ValueError('列は date,used_gb の順で指定してください。容量単位はGBです（MB・TB列は使えません）。')
    if not frame.date.map(lambda x: bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', x))).all():
        raise ValueError('日付は欠損のないYYYY-MM-DD形式にしてください。')
    try:
        frame['date'] = pd.to_datetime(frame.date, format='%Y-%m-%d', errors='raise')
    except ValueError as exc:
        raise ValueError('存在しない日付が含まれています。') from exc
    if frame.date.duplicated().any():
        raise ValueError('日付が重複しています。1日1行にしてください。')
    frame['used_gb'] = pd.to_numeric(frame.used_gb, errors='coerce')
    if not np.isfinite(frame.used_gb).all() or (frame.used_gb < 0).any():
        raise ValueError('used_gbは欠損・単位文字のない、0以上の有限の数値（GB）にしてください。')
    if (frame.used_gb > 1e12).any():
        raise ValueError('used_gbは1兆GB以下にしてください。単位を確認してください。')
    frame = frame.sort_values('date').reset_index(drop=True)
    if len(frame) < minimum:
        raise ValueError(f'日次データが{len(frame)}点です。最低{minimum}点、推奨180点が必要です。月次データは使えません。')
    if len(frame) > 3650:
        raise ValueError('初版は3650日以内のCSVに対応しています。')
    if not frame.date.diff().iloc[1:].eq(pd.Timedelta(days=1)).all():
        raise ValueError('欠損日があります。連続した日次データが必要です。自動補間は行いません。')
    if (frame.used_gb.diff().iloc[1:] < 0).any():
        raise ValueError('使用量が減少しています。初版は削除のない蓄積データ専用のため、予測を停止しました。')
    return frame


def records(frame):
    return [{'date': d.strftime('%Y-%m-%d'), 'used_gb': float(v)} for d, v in frame.itertuples(index=False, name=None)]
