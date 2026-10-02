"""実ブラウザの操作記録。python -m tests.ui_check --browser-path ..."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def run(browser_path=None):
    out=ROOT/'docs/verification/business-ui';out.mkdir(parents=True,exist_ok=True)
    shots=ROOT/'docs/screenshots/business-ui';shots.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];external=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path)
        page=browser.new_page(viewport={'width':1280,'height':1000},accept_downloads=True)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' else None)
        page.on('request',lambda req:external.append(req.url) if not req.url.startswith(('http://127.0.0.1:5000','blob:','data:')) else None)
        page.goto('http://127.0.0.1:5000',wait_until='networkidle')
        assert page.locator('h1').is_visible()
        checks.append('初期画面・入力欄の表示')
        page.locator('#calculate').click()
        page.locator('#results').wait_for(state='visible')
        page.wait_for_function("!document.getElementById('calculate').disabled")
        assert page.locator('#chart svg').count()==1
        assert 'GB' in page.locator('#chart').inner_text()
        assert len(page.locator('#hit').inner_text())>0
        assert page.locator('#summary-items > div').count()==5
        assert page.locator('#summary-headline').inner_text()=='整備の着手日を設定'
        assert page.locator('#scenarios tr').count()==3
        checks.append('サンプル→予測→容量不足日→着手期限→グラフ')
        page.locator('#accuracy summary').click()
        assert page.locator('#metrics tr').count()==6
        checks.append('精度を確認：3手法×7/30日、監査期間・起点の表示')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(shots/'desktop-1280.png'),full_page=True)
        checks.append('1280px：ページの横はみ出しなし・スクリーンショット保存')
        for selector,filename in [('#export-json','sample-result.json'),('#export-csv','sample-forecast.csv'),('#export-summary','sample-summary.txt')]:
            with page.expect_download() as info:
                page.locator(selector).click()
            info.value.save_as(str(out/filename))
        exported=json.loads((out/'sample-result.json').read_text(encoding='utf-8'))
        assert len(exported['forecast'])==90 and exported['plan']['deadline']
        assert len((out/'sample-forecast.csv').read_text(encoding='utf-8-sig').splitlines())==91
        assert (out/'sample-summary.txt').read_text(encoding='utf-8-sig')==exported['summary']['text']
        checks.append('業務サマリの現状・予測・期限・対応・評価を表示し、TXTとJSONの内容一致')
        checks.append('JSON/CSVダウンロードと予測90行・期限の照合')
        with page.expect_download() as info:
            page.locator('#sample-download').click()
        info.value.save_as(str(out/'downloaded-sample.csv'))
        page.locator('#file').set_input_files(str(out/'downloaded-sample.csv'))
        assert page.locator('#clear-file').is_visible()
        assert page.locator('#export-summary').is_disabled()
        page.locator('#calculate').click()
        page.wait_for_function("document.getElementById('source').textContent.includes('取込CSV') && !document.getElementById('calculate').disabled")
        checks.append('サンプルCSVダウンロード→再取込→CSV自身の過去評価を表示')
        page.locator('#file').set_input_files({'name':'invalid.csv','mimeType':'text/csv','buffer':b'date,used_gb\n2026-01-01,-2\n'})
        page.locator('#calculate').click();page.locator('#error').wait_for(state='visible')
        assert '0以上' in page.locator('#error').inner_text()
        assert page.locator('#export-summary').is_disabled()
        page.locator('#clear-file').click()
        assert page.locator('#clear-file').is_hidden()
        assert 'サンプル' in page.locator('#input-source').inner_text()
        checks.append('入力元・ファイル解除を確認、変更後とエラー時は古いサマリの出力を停止')
        checks.append('不正CSVの日本語エラーと古い結果の表示識別')
        page.locator('#sample').select_option('full')
        assert page.locator('#capacity').input_value()=='800'
        page.locator('#calculate').click()
        page.wait_for_function("document.getElementById('status-note').textContent.includes('すでに容量上限') && !document.getElementById('calculate').disabled")
        checks.append('すでに満杯：容量上限と期限超過を文字で表示')
        page.locator('#sample').select_option('stable')
        page.locator('#capacity').fill('1000')
        page.locator('#calculate').click()
        page.wait_for_function("document.getElementById('status-note').textContent.includes('着手期限を過ぎています') && !document.getElementById('calculate').disabled")
        checks.append('整備期間を逆算した着手期限超過')
        page.locator('#capacity').fill('9999');page.locator('#calculate').click()
        page.wait_for_function("document.getElementById('hit').textContent==='期間内未到達' && !document.getElementById('calculate').disabled")
        assert page.locator('#deadline').inner_text()=='期間内は算出なし'
        checks.append('予測期間内未到達：無制限な外挿をしない')
        page.locator('#capacity').fill('1200')
        page.locator('#calculate').click();page.wait_for_function("!document.getElementById('calculate').disabled")
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('#chart svg').is_visible()
        page.screenshot(path=str(shots/'mobile-390.png'),full_page=True)
        page.locator('.summary-panel').screenshot(path=str(shots/'mobile-summary.png'))
        checks.append('390px：ページの横はみ出しなし・単位と結果・スクリーンショット保存')
        for horizon in ('7','30'):
            page.locator('select[name=horizon]').select_option(horizon)
            page.locator('#calculate').click()
            page.wait_for_function("!document.getElementById('calculate').disabled")
            assert f'予測{horizon}日' in page.locator('#context').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.evaluate("""() => {
                const labels=[...document.querySelectorAll('#chart svg text')].slice(-3).map(x=>x.getBoundingClientRect());
                return labels[0].right<labels[1].left && labels[1].right<labels[2].left;
            }""")
        checks.append('7日・30日の短い予測期間でも軸ラベルが重ならない配置と表示を確認')
        # リクエスト中はフォーム全体を無効化し、連打でも1回だけ送る。
        count=[]
        page.on('request',lambda req:count.append(req.url) if req.url.endswith('/api/forecast') else None)
        page.route('**/api/forecast',lambda route:route.fulfill(response=route.fetch()))
        page.evaluate("document.getElementById('calculate').click(); document.getElementById('calculate').click();")
        assert page.locator('#calculate').is_disabled()
        page.wait_for_function("!document.getElementById('calculate').disabled")
        assert len(count)==1
        checks.append('処理中のボタン無効化と二重送信防止（1リクエスト）')
        # 不正CSVへの400は想定内。その他のブラウザエラーは残して判定する。
        unexpected=[e for e in errors if '400 (BAD REQUEST)' not in e]
        assert not unexpected,unexpected
        assert not external,external
        browser.close()
    report={'checks':checks,'console_messages':errors,'unexpected_errors':unexpected,'external_requests':external}
    (out/'ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser-path');args=parser.parse_args();run(args.browser_path)
