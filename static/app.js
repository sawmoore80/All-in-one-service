const API = ""; const $ = id => document.getElementById(id);
let trendChart, topChart;

async function call(path, opts={}) {
  const r = await fetch(`${API}${path}`, { headers:{'Content-Type':'application/json'}, ...opts });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
function currency(n){ return '$'+(n||0).toLocaleString(undefined,{maximumFractionDigits:0}); }

async function refreshHealth(){
  try{ const d=await call('/health'); $('status').textContent=d.ok?'healthy':'error'; $('out').textContent=JSON.stringify(d,null,2);}
  catch(e){ $('status').textContent='error'; $('out').textContent=e.toString(); }
}
async function seedDemo(){ $('out').textContent='Seeding…'; const d=await call('/api/seed',{method:'POST'}); $('out').textContent=JSON.stringify(d,null,2); await loadAll(); }

function renderKPIs(k){
  $('kpis').innerHTML = [
    {label:'Total Spend',value:currency(k.total_spend)},
    {label:'Avg ROAS',value:(k.avg_roas||0).toFixed(2)},
    {label:'Avg CPA',value:currency(k.avg_cpa)},
    {label:'Conversions',value:(k.conversions||0).toLocaleString()}
  ].map(x=>`<div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>`).join('');
}
function ensureTrendChart(labels,spend,roas){
  if(trendChart) trendChart.destroy();
  trendChart=new Chart($('trendChart'),{type:'line',data:{labels,
    datasets:[
      {label:'Spend',data:spend,borderColor:'#4ea8ff',backgroundColor:'rgba(78,168,255,.15)',yAxisID:'y',tension:.35},
      {label:'ROAS',data:roas,borderColor:'#6ee7b7',backgroundColor:'rgba(110,231,183,.12)',yAxisID:'y1',tension:.35}
    ]},
    options:{plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'},grid:{color:'rgba(255,255,255,.06)'}},y:{ticks:{color:'#9fb3c8'}},y1:{position:'right',ticks:{color:'#9fb3c8'},grid:{display:false}}}}
  });
}
function ensureTopChart(labels,clicks){
  if(topChart) topChart.destroy();
  topChart=new Chart($('topChart'),{type:'bar',data:{labels,datasets:[{label:'Clicks',data:clicks,backgroundColor:'#7c3aed'}]},options:{plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'}},y:{ticks:{color:'#9fb3c8'}}}});
}

function badge(txt, cls){ const c = cls==='high'?'#ef4444':cls==='med'?'#f59e0b':'#10b981'; return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:${c}22;border:1px solid ${c}33;color:${c};font-size:12px;margin-right:6px">${txt}</span>`; }

function renderTable(el, rows, cols){
  if(!rows?.length){ el.innerHTML='<div style="color:#9fb3c8">No data</div>'; return; }
  el.innerHTML = `<table><thead><tr>${cols.map(c=>`<th>${c.label}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${r[c.key] ?? ''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function renderInsights(list){
  if(!list?.length){ $('recs').innerHTML='<div class="card">No insights yet</div>'; return; }
  $('recs').innerHTML = list.map(i=>`
    <div class="card" style="margin:8px 0">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div style="font-weight:700">${i.title}</div>
        <div>${badge(i.kpi,'low')}${badge(i.severity,i.severity)}${badge('Score '+i.priority_score,'low')}</div>
      </div>
      <div style="color:#9fb3c8;margin-top:6px">Campaign: ${i.campaign_name}</div>
      <div style="margin-top:8px">
        <div style="font-weight:600;color:#cfe3f0">Why:</div>
        <pre style="margin:6px 0 10px 0">${JSON.stringify(i.evidence,null,2)}</pre>
        <div style="font-weight:600;color:#cfe3f0">Actions (next 48h):</div>
        <ul>${i.actions.map(a=>`<li>${a}</li>`).join('')}</ul>
      </div>
      <div style="margin-top:6px;color:#9fb3c8">Expected impact: +${Math.round(i.expected_impact*100)}%</div>
      <div style="margin-top:10px">
        <button class="btn" onclick="addToPlan(${i.id})">Add to 7-Day Plan</button>
      </div>
    </div>`).join('');
}

let selectedForPlan = new Set();
function addToPlan(id){ selectedForPlan.add(id); $('out').textContent = JSON.stringify({selected:[...selectedForPlan]},null,2); }

async function generatePlaybook(){
  const body = selectedForPlan.size? {insight_ids:[...selectedForPlan]} : {};
  const d = await call('/api/playbook',{method:'POST',body:JSON.stringify(body)});
  $('out').textContent = JSON.stringify(d, null, 2);
}

async function loadRecs(){ const d=await call('/api/insights'); renderInsights(d.insights||[]); }
async function loadAccounts(){ const d=await call('/api/accounts'); renderTable($('accounts'), d.accounts||[], [{key:'id',label:'ID'},{key:'name',label:'Name'},{key:'platform',label:'Platform'},{key:'monthly_spend',label:'Monthly Spend'}]); }
async function loadCampaigns(){ const d=await call('/api/campaigns'); renderTable($('campaigns'), d.campaigns||[], [{key:'id',label:'ID'},{key:'account_id',label:'Account'},{key:'name',label:'Name'},{key:'status',label:'Status'},{key:'spend',label:'Spend'},{key:'cpa',label:'CPA'},{key:'roas',label:'ROAS'},{key:'ctr',label:'CTR'},{key:'impressions',label:'Impressions'},{key:'clicks',label:'Clicks'},{key:'conversions',label:'Conversions'}]); }

async function loadKPIs(){ const k=await call('/api/kpis'); $('kpis').innerHTML = [
  {label:'Total Spend',value:currency(k.total_spend)},
  {label:'Avg ROAS',value:(k.avg_roas||0).toFixed(2)},
  {label:'Avg CPA',value:currency(k.avg_cpa)},
  {label:'Conversions',value:(k.conversions||0).toLocaleString()}
].map(x=>`<div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>`).join(''); }

async function loadTrends(){ const t=await call('/api/trends'); 
  if (window.Chart){ 
    if($('trendChart')){ new Chart($('trendChart')).destroy?.(); }
    if($('topChart')){ new Chart($('topChart')).destroy?.(); }
  }
  ensureTrendChart(t.labels,t.series.spend,t.series.roas); 
  ensureTopChart(t.top.labels,t.top.clicks); 
}

async function loadAll(){ await refreshHealth(); await Promise.all([loadKPIs(),loadTrends(),loadRecs(),loadAccounts(),loadCampaigns()]); }
document.addEventListener('DOMContentLoaded', loadAll);

// expose
window.refreshHealth = refreshHealth;
window.seedDemo = seedDemo;
window.generatePlaybook = generatePlaybook;
