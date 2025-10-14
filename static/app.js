// static/app.js
const API = "";
const $ = (id)=>document.getElementById(id);
let trendChart, topChart;

async function call(path, opts={}) {
  const r = await fetch(`${API}${path}`, {
    headers: {'Content-Type':'application/json'},
    ...opts
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function refreshHealth() {
  try {
    const data = await call('/health');
    $('status').textContent = data.ok ? 'healthy' : 'error';
    $('out').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $('status').textContent = 'error';
    $('out').textContent = e.toString();
  }
}

async function seedDemo() {
  $('out').textContent = 'Seeding…';
  try {
    const res = await call('/api/seed', {method:'POST'});
    $('out').textContent = JSON.stringify(res, null, 2);
    await loadAll();
  } catch (e) {
    $('out').textContent = e.toString();
  }
}

function currency(n){ return '$' + (n||0).toLocaleString(undefined,{maximumFractionDigits:0}); }
function pct(n){ return (n||0).toFixed(2) + '%'; }

function renderKPIs(k){
  const html = [
    {label:'Total Spend', value: currency(k.total_spend)},
    {label:'Avg ROAS', value: (k.avg_roas||0).toFixed(2)},
    {label:'Avg CPA', value: currency(k.avg_cpa)},
    {label:'Conversions', value: (k.conversions||0).toLocaleString()}
  ].map(x=>`<div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>`).join('');
  $('kpis').innerHTML = html;
}

function ensureTrendChart(labels, spend, roas){
  if (trendChart) trendChart.destroy();
  const ctx = $('trendChart').getContext('2d');
  trendChart = new Chart(ctx, {
    type:'line',
    data:{
      labels,
      datasets:[
        {label:'Spend', data:spend, borderColor:'#4ea8ff', backgroundColor:'rgba(78,168,255,.15)', yAxisID:'y', tension:.35},
        {label:'ROAS', data:roas, borderColor:'#6ee7b7', backgroundColor:'rgba(110,231,183,.12)', yAxisID:'y1', tension:.35}
      ]
    },
    options:{
      plugins:{legend:{labels:{color:'#cfe3f0'}}},
      scales:{
        x:{ticks:{color:'#9fb3c8'}, grid:{color:'rgba(255,255,255,.06)'}},
        y:{position:'left', ticks:{color:'#9fb3c8'}, grid:{color:'rgba(255,255,255,.06)'}},
        y1:{position:'right', ticks:{color:'#9fb3c8'}, grid:{display:false}}
      }
    }
  });
}

function ensureTopChart(labels, clicks){
  if (topChart) topChart.destroy();
  const ctx = $('topChart').getContext('2d');
  topChart = new Chart(ctx, {
    type:'bar',
    data:{ labels, datasets:[{label:'Clicks', data:clicks, backgroundColor:'#7c3aed'}] },
    options:{ plugins:{legend:{labels:{color:'#cfe3f0'}}}, scales:{
      x:{ticks:{color:'#9fb3c8'}}, y:{ticks:{color:'#9fb3c8'}}
    }}
  });
}

function renderRecs(list){
  if (!list?.length){
    $('recs').innerHTML = '<div class="rec">No recommendations yet.</div>';
    return;
  }
  $('recs').innerHTML = list.map(r=>`
    <div class="rec">
      <div class="rec-title">${r.title}</div>
      <div>${r.description}</div>
      <div class="sub">Impact: ${(r.impact_score||0).toFixed(2)} • Account #${r.account_id}</div>
    </div>`).join('');
}

function renderTable(el, rows, cols){
  if(!rows?.length){ el.innerHTML='<div style="color:#9fb3c8">No data</div>'; return; }
  el.innerHTML = `<table><thead><tr>${cols.map(c=>`<th>${c.label}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${r[c.key] ?? ''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

async function loadRecs(){
  const d = await call('/api/recommendations');
  renderRecs(d.recommendations || []);
}

async function loadAccounts(){
  const d = await call('/api/accounts');
  renderTable($('accounts'), d.accounts || [], [
    {key:'id',label:'ID'},{key:'name',label:'Name'},{key:'platform',label:'Platform'},{key:'monthly_spend',label:'Monthly Spend'}
  ]);
}

async function loadCampaigns(){
  const d = await call('/api/campaigns');
  renderTable($('campaigns'), d.campaigns || [], [
    {key:'id',label:'ID'},{key:'account_id',label:'Account'},{key:'name',label:'Name'},{key:'status',label:'Status'},
    {key:'spend',label:'Spend'},{key:'cpa',label:'CPA'},{key:'roas',label:'ROAS'},{key:'ctr',label:'CTR'},
    {key:'impressions',label:'Impressions'},{key:'clicks',label:'Clicks'},{key:'conversions',label:'Conversions'}
  ]);
}

async function loadKPIs(){
  const k = await call('/api/kpis');
  renderKPIs(k);
}

async function loadTrends(){
  const t = await call('/api/trends');
  ensureTrendChart(t.labels, t.series.spend, t.series.roas);
  ensureTopChart(t.top.labels, t.top.clicks);
}

async function loadAll(){
  await refreshHealth();
  await Promise.all([loadKPIs(), loadTrends(), loadRecs(), loadAccounts(), loadCampaigns()]);
}

document.addEventListener('DOMContentLoaded', loadAll);
