const API = ""; const $ = (id)=>document.getElementById(id);
let trendChart, topChart;
let selectedForPlan = new Set();

function toast(msg){ const t=$('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2200); }
function setStatus(ok){ const s=$('status'); if(ok){s.textContent='healthy'; s.className='status ok';} else {s.textContent='error'; s.className='status err';} }
function showOut(obj){ $('out').textContent = typeof obj==='string'? obj : JSON.stringify(obj,null,2); }

async function call(path, opts={}){
  const r = await fetch(`${API}${path}`, {headers:{'Content-Type':'application/json'}, ...opts});
  const txt = await r.text();
  let data; try{ data = JSON.parse(txt);}catch{ data = {raw:txt}; }
  if(!r.ok) throw Object.assign(new Error(`HTTP ${r.status}`), {status:r.status, data});
  return data;
}

// Global error surfacing
window.addEventListener('error', e=>{ setStatus(false); showOut(String(e.error||e.message||e)); });
window.addEventListener('unhandledrejection', e=>{ setStatus(false); showOut(e.reason||'Promise rejected'); });

// ---------- KPIs ----------
function currency(n){return '$'+(Number(n)||0).toLocaleString(undefined,{maximumFractionDigits:0});}
function renderKPIs(k){
  const items = [
    {label:'Total Spend', value:currency(k.total_spend)},
    {label:'Avg ROAS',   value:(k.avg_roas??0).toFixed?.(2) ?? String(k.avg_roas||0)},
    {label:'Avg CPA',    value:currency(k.avg_cpa)},
    {label:'Conversions',value:(k.conversions||0).toLocaleString()},
  ];
  $('kpis').innerHTML = items.map(x=>`
    <div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>
  `).join('');
}

// ---------- Charts ----------
function ensureTrendChart(labels, spend, roas){
  const el = $('trendChart'); if(!el || !window.Chart) return;
  if(trendChart) trendChart.destroy();
  trendChart = new Chart(el, {
    type:'line',
    data:{labels, datasets:[
      {label:'Spend', data:spend, borderColor:'#4ea8ff', backgroundColor:'rgba(78,168,255,.12)', yAxisID:'y', tension:.35},
      {label:'ROAS', data:roas, borderColor:'#6ee7b7', backgroundColor:'rgba(110,231,183,.10)', yAxisID:'y1', tension:.35},
    ]},
    options:{
      maintainAspectRatio:false, plugins:{legend:{labels:{color:'#cfe3f0'}}},
      scales:{x:{ticks:{color:'#9fb3c8'}, grid:{color:'rgba(255,255,255,.06)'}},
              y:{ticks:{color:'#9fb3c8'}}, y1:{position:'right', ticks:{color:'#9fb3c8'}, grid:{display:false}}}
    }
  });
}
function ensureTopChart(labels, clicks){
  const el = $('topChart'); if(!el || !window.Chart) return;
  if(topChart) topChart.destroy();
  topChart = new Chart(el, {
    type:'bar',
    data:{labels, datasets:[{label:'Clicks', data:clicks, backgroundColor:'#7c3aed'}]},
    options:{maintainAspectRatio:false, plugins:{legend:{labels:{color:'#cfe3f0'}}},
      scales:{x:{ticks:{color:'#9fb3c8'}}, y:{ticks:{color:'#9fb3c8'}}}}
  });
}

// ---------- Insights ----------
function badge(txt, cls){
  const klass = cls==='high' ? 'badge high' : cls==='med' ? 'badge med' : cls==='low' ? 'badge low' : 'badge';
  return `<span class="${klass}">${txt}</span>`;
}
function insightCard(i){
  const selected = selectedForPlan.has(i.id);
  return `
    <div class="insight card" style="margin:10px 0; border:1px solid var(--line)">
      <div class="left">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
          <div>
            <div style="font-weight:800;font-size:16px">${i.title}</div>
            <div class="sub" style="margin-top:4px">Campaign: ${i.campaign_name}</div>
          </div>
          <div class="badges">
            ${badge(i.kpi,'kpi')}
            ${badge(i.severity, i.severity)}
            ${badge('Score '+(i.priority_score??'-'),'low')}
          </div>
        </div>
        <div style="margin-top:8px"><b>Why:</b>
          <pre>${JSON.stringify(i.evidence||{},null,2)}</pre>
        </div>
        <div class="actions"><b>Actions (next 48h):</b>
          <ul>${(i.actions||[]).map(a=>`<li>${a}</li>`).join('')}</ul>
        </div>
        <div class="sub" style="margin-top:6px">Expected impact: +${Math.round((i.expected_impact||0)*100)}%</div>
        <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap">
          <button class="btn ${selected?'danger':''}" onclick="toggleSelect(${i.id})">${selected?'Remove from':'Add to'} Plan</button>
        </div>
      </div>
    </div>
  `;
}
function renderInsights(list){
  if(!Array.isArray(list) || !list.length){
    $('recs').innerHTML = '<div class="sub">No insights yet.</div>'; return;
  }
  $('recs').innerHTML = list.map(insightCard).join('');
}
function toggleSelect(id){
  if(selectedForPlan.has(id)){ selectedForPlan.delete(id); toast('Removed from plan'); }
  else { selectedForPlan.add(id); toast('Added to plan'); }
  // re-render selection state quickly
  loadRecs();
}
function clearSelection(){ selectedForPlan.clear(); loadRecs(); toast('Selection cleared'); }

// ---------- Playbook Modal ----------
function showModal(){ $('modal').style.display='flex'; }
function hideModal(){ $('modal').style.display='none'; }
function renderPlan(plan){
  const rows = plan.map(p=>`
    <tr>
      <td>${p.day}</td>
      <td>${p.title}</td>
      <td>${p.kpi}</td>
      <td>${p.severity}</td>
      <td><ul>${p.what_to_ship.map(x=>`<li>${x}</li>`).join('')}</ul></td>
      <td><ul>${p.how_to_measure.map(x=>`<li>${x}</li>`).join('')}</ul></td>
    </tr>`).join('');
  $('planRows').innerHTML = rows || `<tr><td colspan="6" class="sub">No items</td></tr>`;
}

// ---------- API Loads ----------
async function refreshHealth(){
  try{ const d=await call('/health'); setStatus(!!d.ok); showOut(d); }
  catch(e){ setStatus(false); showOut(e.data||String(e)); }
}
async function seedDemo(){
  try{ showOut('Seeding…'); const d=await call('/api/seed',{method:'POST'}); showOut(d); await loadAll(); toast('Demo data seeded'); }
  catch(e){ setStatus(false); showOut(e.data||String(e)); }
}
async function loadKPIs(){ try{ const k=await call('/api/kpis'); renderKPIs(k); } catch(e){ showOut(e.data||String(e)); } }
async function loadTrends(){ 
  try{ const t=await call('/api/trends'); ensureTrendChart(t.labels,t.series?.spend||[],t.series?.roas||[]); ensureTopChart(t.top?.labels||[],t.top?.clicks||[]); }
  catch(e){ showOut(e.data||String(e)); }
}
async function loadRecs(){ try{ const d=await call('/api/insights'); renderInsights(d.insights||[]); } catch(e){ showOut(e.data||String(e)); } }

async function generatePlaybook(){
  try{
    const body = selectedForPlan.size ? {insight_ids:[...selectedForPlan]} : {};
    const d = await call('/api/playbook',{method:'POST',body:JSON.stringify(body)});
    showOut(d);
    renderPlan(d.plan||[]);
    showModal();
  }catch(e){ setStatus(false); showOut(e.data||String(e)); }
}
async function loadAll(){ await Promise.allSettled([refreshHealth(), loadKPIs(), loadTrends(), loadRecs()]); }

document.addEventListener('DOMContentLoaded', loadAll);
