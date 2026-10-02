"""計算済み結果を日本語にする境界。数値の再予測・上書きはしない。"""
from typing import Protocol


class Explainer(Protocol):
    def explain(self, result: dict) -> str: ...


class TemplateExplainer:
    def explain(self, result):
        rate = result['parameters']['rate']
        p = result['plan']
        hit = p['hit_date'] or '予測期間内に到達見込みなし'
        deadline = p['deadline'] or '予測期間内では算出できません'
        return (f"観測終了日 {result['as_of']} を基準に、1日あたり {rate:.2f} GBの増加を積み上げました。"
                f"容量不足の見込み：{hit}。着手期限：{deadline}。"
                f"上限到達日から整備期間 {result['settings']['lead']} 日と安全余裕 {result['settings']['buffer']} 日を引いています。"
                '削除や大幅な運用変更がない前提です。条件別シナリオは確率付きの予測区間ではありません。')
