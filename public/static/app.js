'use strict';
const $ = id => document.getElementById(id);
let result = null;
const labels = {mean30:'直近30日平均（比較基準）',linear:'線形トレンド',ses:'増加量の指数平滑化'};
const num = (v,d=1) => Number(v).toLocaleString('ja-JP',{maximumFractionDigits:d,minimumFractionDigits:d});
const text = (id,value) => {$(id).textContent = value;};
const exportButtons = ['export-summary','export-csv','export-json'];
function invalidate(){
  if(!result)return;
  $('stale').hidden=false;
  exportButtons.forEach(id=>$(id).disabled=true);
}
function inputSource(){
  const file=$('file').files[0];
  text('input-source',file ? `使用データ：${file.name}` : `使用データ：サンプル「${$('sample').selectedOptions[0].textContent}」`);
  $('clear-file').hidden=!file;
}
$('sample').addEventListener('change', () => {
  $('file').value = '';
  $('sample-download').href = `/api/sample/${$('sample').value}`;
  $('capacity').value = $('sample').value === 'full' ? 800 : 1200;
  inputSource();
});
$('file').addEventListener('change',inputSource);
$('clear-file').addEventListener('click',()=>{$('file').value='';inputSource();invalidate();});
$('forecast-form').addEventListener('input', invalidate);
$('forecast-form').addEventListener('change', invalidate);
// 折りたたまれた項目に入力エラーがある場合は開いて修正できるようにする。
$('forecast-form').addEventListener('invalid',event=>{const details=event.target.closest('details');if(details)details.open=true;},true);
inputSource();
document.querySelectorAll('[data-demo-capacity]').forEach(button => {
  button.addEventListener('click', () => {
    $('forecast-form').reset();
    $('sample').value = 'stable';
    $('file').value = '';
    $('capacity').value = button.dataset.demoCapacity;
    $('sample-download').href = '/api/sample/stable';
    inputSource();
    invalidate();
    $('forecast-form').requestSubmit();
  });
});
$('forecast-form').addEventListener('submit', async event => {
  event.preventDefault();
  if ($('calculate').disabled) return;
  const data = new FormData(event.currentTarget);
  $('error').hidden=true;
  exportButtons.forEach(id=>$(id).disabled=true);
  const controls = [...event.currentTarget.elements];
  controls.forEach(control => control.disabled=true);
  text('progress','過去データで手法を比較し、予測と整備期限を計算しています…');
  try {
    const response = await fetch('/api/forecast',{method:'POST',body:data});
    const body = response.headers.get('content-type')?.includes('application/json')
      ? await response.json()
      : {error: 'サーバーに接続できませんでした。時間をおいて再度お試しください。'};
    if(!response.ok) throw new Error(body.error || '計算に失敗しました。');
    result=body; render();
    text('progress','計算完了。予測結果とサマリを更新しました。');
  } catch(error) {
    text('error',error.message || '接続できません。通信環境を確認し、再度お試しください。');
    $('error').hidden=false; text('progress','');
    invalidate();
  } finally {controls.forEach(control=>control.disabled=false);}
});
function render(){
  const r=result,p=r.plan;
  $('empty').hidden=true;$('results').hidden=false;$('stale').hidden=true;
  exportButtons.forEach(id=>$(id).disabled=false);
  $('results').className=p.status;
  text('context',`観測終了 ${r.as_of} ・ ${r.observations}日分 ・ 予測${r.settings.horizon}日`);
  text('source',r.source);
  text('usage',`${num(p.utilization_pct)}%`);
  text('used',`${num(r.history.at(-1).used_gb)} / ${num(r.settings.capacity,0)} GB`);
  $('meter').style.width=`${Math.min(100,p.utilization_pct)}%`;
  text('hit',p.hit_date || '期間内未到達');
  text('deadline',p.deadline || '期間内は算出なし');
  text('deadline-detail',p.days_to_deadline===null ? '先の安全を保証するものではありません' : `観測終了日から ${p.days_to_deadline} 日 ／ 整備＋余裕 ${r.settings.lead+r.settings.buffer} 日`);
  text('status',{normal:'✓ 期間内未到達',attention:'△ 注意',overdue:'！期限超過'}[p.status]);
  text('status-note',p.message);
  text('explanation',`${r.model_label}を採用。${r.explanation}`);
  text('summary-headline',r.summary.headline);
  $('summary-items').replaceChildren();
  r.summary.items.forEach(item=>{
    const row=document.createElement('div'),label=document.createElement('dt'),value=document.createElement('dd');
    label.textContent=item.label;value.textContent=item.value;row.append(label,value);$('summary-items').append(row);
  });
  $('scenarios').replaceChildren();
  r.scenarios.forEach((s,i)=>{
    const row=document.createElement('tr');if(i===1)row.className='chosen';
    [`${num(s.multiplier*100,0)}%${i===1?'（基準）':i===2?'（指定）':''}`,s.plan.hit_date||'期間内未到達',s.plan.deadline||'算出不可'].forEach(value=>{const td=document.createElement('td');td.textContent=value;row.append(td);});
    $('scenarios').append(row);
  });
  const e=r.evaluation, first=e.audit[0],last=e.audit.at(-1);
  text('evaluation-context',`${r.source}。監査の採点期間 ${first.test_start}〜${last.test_end}、予測起点 ${[...new Set(e.audit.map(x=>x.train_end))].join(' / ')}。各起点までの観測だけで再学習。`);
  const developmentCount = new Set(e.development.map(x=>x.origin)).size;
  text('selection',`${e.selection_rule} 選択：${r.model_label}。${e.fallback?'開発foldを確保できない短いCSVのため、比較基準を固定採用。':`開発${developmentCount}起点で選択。モデル選択には監査区間を使っていません。${developmentCount<5?'起点数が少なく、選択結果が不安定になる可能性があります。':''}`}`);
  $('metrics').replaceChildren();
  e.summary.forEach(row=>{const tr=document.createElement('tr');if(row.model===r.selected_model)tr.className='chosen';
    [labels[row.model]+(row.model===r.selected_model?' ［採用］':''),`${row.horizon}日`,num(row.mae),num(row.rmse),num(row.endpoint_abs_error),num(row.growth_abs_error),row.improvement_pct===null?'N/A':`${num(row.improvement_pct)}%`].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});$('metrics').append(tr);});
  drawChart();
}
function drawChart(){
  if(!result)return;
  const r=result, mobile=window.innerWidth<700, W=mobile?570:1060,H=mobile?340:340,L=64,R=20,T=30,B=48;
  const values=[...r.history.map(x=>x.used_gb),...r.forecast.map(x=>x.used_gb),...r.scenarios.at(-1).values,r.settings.capacity];
  const max=Math.max(...values)*1.12,min=0,n=r.history.length+r.forecast.length;
  const x=i=>L+i/(n-1)*(W-L-R), y=v=>T+(max-v)/(max-min)*(H-T-B);
  const path=(array,start)=>array.map((v,i)=>`${i?'L':'M'}${x(start+i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','使用量（GB）と日付。実績、中心予測、指定ペース、容量上限、警戒水準。');
  const add=(name,attrs,content)=>{const el=document.createElementNS(svg.namespaceURI,name);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));if(content!==undefined)el.textContent=content;svg.append(el);return el;};
  add('rect',{x:x(r.history.length-1),y:T,width:W-R-x(r.history.length-1),height:H-T-B,fill:'#f4f7fc'});
  for(let i=0;i<=4;i++){const v=max*i/4;add('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:'#e5eceb'});add('text',{x:L-9,y:y(v)+5,'text-anchor':'end',fill:'#718487','font-size':mobile?16:12},num(v,0));}
  add('text',{x:9,y:17,fill:'#627b7d','font-size':mobile?16:12},'GB');
  [[r.settings.capacity,'#b26b5d',''],[r.settings.capacity*r.settings.warning_pct/100,'#b58a32','5 5']].forEach(([v,c,d])=>add('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:c,'stroke-dasharray':d,'stroke-width':1.5}));
  const start=r.history.length-1,current=r.history.at(-1).used_gb;
  add('path',{d:path(r.history.map(v=>v.used_gb),0),fill:'none',stroke:'#16776c','stroke-width':2.5});
  add('path',{d:path([current,...r.scenarios.at(-1).values],start),fill:'none',stroke:'#9f86c1','stroke-dasharray':'3 5','stroke-width':2});
  add('path',{d:path([current,...r.forecast.map(v=>v.used_gb)],start),fill:'none',stroke:'#4c77b8','stroke-dasharray':'6 4','stroke-width':2.5});
  add('line',{x1:x(start),x2:x(start),y1:T,y2:H-B,stroke:'#8b9da3','stroke-dasharray':'4 4'});
  const shortFuture = W-R-x(start)<100;
  add('text',{x:shortFuture?W-R:x(start)+7,y:20,'text-anchor':shortFuture?'end':'start',fill:'#607d98','font-size':mobile?16:12},'予測 →');
  const middleIndex = shortFuture ? Math.floor(start/2) : start;
  [[0,r.history[0].date,'start'],[middleIndex,r.history[middleIndex].date,'middle'],[n-1,r.forecast.at(-1).date,'end']].forEach(([i,d,anchor])=>add('text',{x:x(i),y:H-19,'text-anchor':anchor,fill:'#718487','font-size':mobile?16:12},mobile?d.slice(5):d));
  $('chart').replaceChildren(svg);
}
window.addEventListener('resize',drawChart);
function download(content,type,name){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-json').addEventListener('click',()=>download(JSON.stringify(result,null,2),'application/json',`capacity-result-${result.as_of}.json`));
$('export-summary').addEventListener('click',()=>download('\uFEFF'+result.summary.text,'text/plain;charset=utf-8',`capacity-summary-${result.as_of}.txt`));
$('export-csv').addEventListener('click',()=>{const rows=['date,predicted_gb,capacity_gb,hit_date,deadline,model'];result.forecast.forEach(r=>rows.push([r.date,r.used_gb,result.settings.capacity,result.plan.hit_date||'',result.plan.deadline||'',result.selected_model].join(',')));download('\uFEFF'+rows.join('\r\n'),'text/csv;charset=utf-8',`capacity-forecast-${result.as_of}.csv`);});
