// static/app.js
const API = ""; // same origin
const $ = (id)=>document.getElementById(id);
let trendChart, topChart;

async function call(path, opts={}) {
  const r = await fetch(`${API}${path}`, {headers:{'Content-Type':'application/json'}, ...opts});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function fmt(n, d=0){ if(n==null) return '–'; return Number(n).toLocaleString(undefined,{maximumFractionDigits:d}); }

async function refreshHealth(){
  try{
    const data = await call('/health');
    $('status').textContent = data.ok ? 'healthy' : 'error';
    $('status').className = data.ok ? 'ok' : '';
    $('out').textContent = JSON.stringify(data,null,2);
  }catch(e){
    $('status').textContent='error'; $('out').textContent = e.toString();
  }
}

async function seedDemo(){
  $('out').textContent = 'Seeding…';
  const data = await call('/api/seed',{method:'POST'});
  $('out').textContent = JSON.stringify(data,null,2);
  await loadEverything();
}

function renderTable(tbody, rows, cols){
  tbody.innerHTML = rows.map(r=>{
    return `<tr>${cols.map(c=>`<td>${r[c.key] ?? ''}</td>`).join('')}</tr>`;
  }).join('');
}

function recBadge(txt){ return `<span class="badge">${txt}</span>`; }

function renderRecs(rows){
  $('recs').innerHTML = rows.length ? rows.map(r=>`
    <div class="rec">
      <h4>${r.title}</h4>
      <div style="margin:6px 0 10px">${r.description}</div>
      <div class="muted" style="margin-bottom:6px"><strong>Why:</strong> ${r.why}</div>
      <div><strong>Action:</strong> ${r.action}</div>
      <div style="margin-top:8px">${recBadge('Priority: '+r.priority)} ${recBadge('Impact: '+r.impact_score)}</div>
    </div>
  `).join('') : `<div class="muted">No recommendations yet.</div>`;
}

function drawTrend(series){
  const labels = series.map(s=>s.day.slice(5));
  const spend = series.map(s=>s.spend);
  const roas  = series.map(s=>s.roas);
  const ctr   = series.map(s=>s.ctr);

  if(trendChart) trendChart.destroy();
  trendChart = new Chart($('trendChart'), {
    type:'line',
    data:{ labels, datasets:[
      {label:'Spend', data:spend, borderColor:'#60A5FA', backgroundColor:'rgba(96,165,250,0.2)', yAxisID:'y'},
      {label:'ROAS', data:roas, borderColor:'#34D399', backgroundColor:'rgba(52,211,153,0.2)', yAxisID:'y1'},
      {label:'CTR %', data:ctr, borderColor:'#F59E0B', backgroundColor:'rgba(245,158,11,0.2)', yAxisID:'y1'},
    ]},
    options:{ responsive:true, scales:{ y:{ beginAtZero:true }, y1:{ position:'right', beginAtZero:true } } }
  });
}

function drawTop(top){
  if(topChart) topChart.destroy();
  topChart = new Chart($('topChart'), {
    type:'bar',
    data:{ labels: top.map(t=>t.name),
      datasets:[{label:'Top Campaigns by ROAS', data: top.map(t=>t.roas), backgroundColor:'#A78BFA'}]
    },
    options:{ indexAxis:'y', responsive:true, scales:{ x:{ beginAtZero:true } } }
  });
}

async function loadOverview(){
  const {overview} = await call('/api/overview');
  $('kpi-spend').textContent = '$'+fmt(overview.spend, 0);
  $('kpi-conv').textContent  = fmt(overview.conversions);
  $('kpi-roas').textContent  = fmt(overview.roas, 2);
  $('kpi-cpa').textContent   = '$'+fmt(overview.cpa, 2);
  $('kpi-ctr').textContent   = fmt(overview.ctr, 2)+'%';
}

async function loadCharts(){
  const {series, top} = await call('/api/timeseries');
  drawTrend(series || []);
  drawTop(top || []);
}

async function loadRecs(){
  const data = await call('/api/recommendations');
  renderRecs(data.recommendations || []);
}

async function loadAccounts(){
  const data = await call('/api/accounts');
  renderTable($('accounts'), data.accounts || [], [
    {key:'id',label:'ID'}, {key:'name',label:'Name'}, {key:'platform',label:'Platform'},
    {key:'monthly_spend',label:'Monthly Spend'}
  ]);
}

async function loadCampaigns(){
  const data = await call('/api/campaigns');
  renderTable($('campaigns'), data.campaigns || [], [
    {key:'id'},{key:'account_id'},{key:'name'},{key:'status'},{key:'spend'},
    {key:'cpa'},{key:'roas'},{key:'ctr'},{key:'impressions'},{key:'clicks'},{key:'conversions'}
  ]);
}

async function loadEverything(){
  await refreshHealth();
  await Promise.all([loadOverview(), loadCharts(), loadRecs(), loadAccounts(), loadCampaigns()]);
}

document.addEventListener('DOMContentLoaded', loadEverything);
const API = ""; // same origin
const $out = id => document.getElementById(id);

async function call(path, opts={}) {
  const r = await fetch(`${API}${path}`, {
    headers: {'Content-Type':'application/json'},
    ...opts
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function init() {
  await refreshHealth();
  await loadRecs();
  await loadAccounts();
  await loadCampaigns();
}

async function refreshHealth() {
  try {
    const data = await call('/health');
    $out('status').textContent = data.ok ? 'healthy' : 'error';
    $out('out').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $out('status').textContent = 'error';
    $out('out').textContent = e.toString();
  }
}

async function seedDemo() {
  $out('out').textContent = 'Seeding…';
  try {
    const data = await call('/api/seed', {method:'POST'});
    $out('out').textContent = JSON.stringify(data, null, 2);
    await loadRecs();
    await loadAccounts();
    await loadCampaigns();
  } catch (e) {
    $out('out').textContent = e.toString();
  }
}

async function loadRecs() {
  const data = await call('/api/recommendations');
  const list = data.recommendations || [];
  const el = $out('recs');
  el.innerHTML = list.length ? '' : '<p>No recommendations yet.</p>';
  for (const r of list) {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `
      <div class="rec-title">${r.title}</div>
      <div class="rec-desc">${r.description || ''}</div>
      <div class="rec-meta">Impact: ${(+r.impact_score).toFixed(2)} • Account #${r.account_id}</div>
    `;
    el.appendChild(div);
  }
}

function renderTable(el, rows, cols) {
  el.innerHTML = '';
  const table = document.createElement('table');
  table.innerHTML = `
    <thead><tr>${cols.map(c=>`<th>${c.label}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${r[c.key] ?? ''}</td>`).join('')}</tr>`).join('')}</tbody>
  `;
  el.appendChild(table);
}

async function loadAccounts() {
  const data = await call('/api/accounts');
  renderTable($out('accounts'), data.accounts || [], [
    {key:'id',label:'ID'},
    {key:'name',label:'Name'},
    {key:'platform',label:'Platform'},
    {key:'monthly_spend',label:'Monthly Spend'},
  ]);
}

async function loadCampaigns() {
  const data = await call('/api/campaigns');
  renderTable($out('campaigns'), data.campaigns || [], [
    {key:'id',label:'ID'},
    {key:'account_id',label:'Account'},
    {key:'name',label:'Name'},
    {key:'status',label:'Status'},
    {key:'spend',label:'Spend'},
    {key:'cpa',label:'CPA'},
    {key:'roas',label:'ROAS'},
    {key:'ctr',label:'CTR'},
    {key:'impressions',label:'Impressions'},
    {key:'clicks',label:'Clicks'},
    {key:'conversions',label:'Conversions'},
  ]);
}

window.seedDemo = seedDemo;
window.refreshHealth = refreshHealth;
document.addEventListener('DOMContentLoaded', init);
