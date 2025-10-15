const $=(id)=>document.getElementById(id);
let trendChart, topChart, selectedForPlan=new Set();

function toast(m){const t=$('toast'); if(!t) return; t.textContent=m; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2200);}
function showOut(o){const el=$('out'); if(!el) return; try{el.textContent=typeof o==='string'?o:JSON.stringify(o,null,2);}catch(e){el.textContent=String(o);}}
async function call(path, opts={}){
  const r=await fetch(path,{headers:{'Content-Type':'application/json'},credentials:'include',...opts});
  const text=await r.text(); let d; try{d=JSON.parse(text);}catch{d={raw:text}}
  if(!r.ok){ throw d; } return d;
}

// Account modal
function openAuth(){ const m=$('authModal'); if(m) m.style.display='flex'; }
function closeAuth(){ const m=$('authModal'); if(m) m.style.display='none'; }

async function refreshAuthBadge(){
  try{ const d=await call('/api/me');
    if(d.auth){ $('authBadge').textContent=d.email||'User'; const w=$('whoami'); if(w) w.textContent=d.email||'user'; }
    else { $('authBadge').textContent='Guest'; const w=$('whoami'); if(w) w.textContent='guest'; }
  }catch(e){ $('authBadge').textContent='Guest'; }
}

// Auth
async function register(){
  try{
    const email=$('email').value, password=$('password').value;
    await call('/api/register',{method:'POST',body:JSON.stringify({email,password})});
    toast('Account created'); await refreshAuthBadge(); closeAuth(); loadAll();
  }catch(e){ toast((e&&e.error)||'Register error'); showOut(e); }
}
async function login(){
  try{
    const email=$('email').value, password=$('password').value;
    await call('/api/login',{method:'POST',body:JSON.stringify({email,password})});
    toast('Signed in'); await refreshAuthBadge(); closeAuth(); loadAll();
  }catch(e){ toast((e&&e.error)||'Login error'); showOut(e); }
}
async function logout(){ try{ await call('/api/logout'); toast('Signed out'); await refreshAuthBadge(); }catch(e){ toast('Logout error'); } }

// Charts
function currency(n){return '$'+(Number(n)||0).toLocaleString(undefined,{maximumFractionDigits:0});}
function ensureTrendChart(labels,spend,roas){
  const el=$('trendChart'); if(!el||!window.Chart) return;
  if(trendChart) trendChart.destroy();
  trendChart=new Chart(el,{type:'line',data:{labels,datasets:[
    {label:'Spend',data:spend,borderColor:'#4ea8ff',backgroundColor:'rgba(78,168,255,.12)',yAxisID:'y',tension:.35},
    {label:'ROAS',data:roas,borderColor:'#6ee7b7',backgroundColor:'rgba(110,231,183,.10)',yAxisID:'y1',tension:.35}
  ]},options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'},grid:{color:'rgba(255,255,255,.06)'}},y:{ticks:{color:'#9fb3c8'}},y1:{position:'right',ticks:{color:'#9fb3c8'},grid:{display:false}}}});}
function ensureTopChart(labels,clicks){
  const el=$('topChart'); if(!el||!window.Chart) return;
  if(topChart) topChart.destroy();
  topChart=new Chart(el,{type:'bar',data:{labels,datasets:[{label:'Clicks',data:clicks,backgroundColor:'#7c3aed'}]},options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'}},y:{ticks:{color:'#9fb3c8'}}}});}
function renderKPIs(k){
  const items=[
    {label:'Total Spend',value:currency(k.total_spend)},
    {label:'Avg ROAS',value:(Number(k.avg_roas)||0).toFixed(2)},
    {label:'Avg CPA',value:currency(k.avg_cpa)},
    {label:'Conversions',value:(Number(k.conversions)||0).toLocaleString()}
  ];
  $('kpis').innerHTML=items.map(x=>`<div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>`).join('');
}
function badge(txt,cls){const klass=cls==='high'?'badge high':cls==='med'?'badge med':cls==='low'?'badge low':'badge';return `<span class="${klass}">${txt}</span>`;}
function insightCard(i){
  const sel=selectedForPlan.has(i.id);
  return `<div class="card" style="margin:10px 0">
    <div style="display:flex;justify-content:space-between;gap:8px">
      <div><div style="font-weight:800">${i.title}</div><div class="sub">Campaign: ${i.campaign_name}</div></div>
      <div>${badge(i.kpi,'kpi')} ${badge(i.severity,i.severity)} ${badge('Score '+i.priority_score,'low')}</div>
    </div>
    <div style="margin-top:8px"><b>Why:</b><pre>${JSON.stringify(i.evidence||{},null,2)}</pre></div>
    <div><b>Actions (48h):</b><ul>${(i.actions||[]).map(a=>`<li>${a}</li>`).join('')}</ul></div>
    <div class="sub" style="margin-top:6px">Expected impact: +${Math.round((i.expected_impact||0)*100)}%</div>
    <div style="margin-top:10px"><button class="btn ${sel?'danger':''}" onclick="toggleSelect(${i.id})">${sel?'Remove':'Add'} to Plan</button></div>
  </div>`;
}
function renderInsights(list){$('recs').innerHTML=(list||[]).map(insightCard).join('')||'<div class="sub">No insights yet.</div>'; }
function toggleSelect(id){ if(selectedForPlan.has(id)){selectedForPlan.delete(id);toast('Removed');} else {selectedForPlan.add(id);toast('Added');} loadRecs(); }
function clearSelection(){selectedForPlan.clear(); loadRecs(); toast('Cleared');}
function renderPlan(plan){$('planRows').innerHTML=(plan||[]).map(p=>`<tr><td>${p.day}</td><td>${p.title}</td><td>${p.kpi}</td><td>${p.severity}</td><td><ul>${p.what_to_ship.map(x=>`<li>${x}</li>`).join('')}</ul></td><td><ul>${p.how_to_measure.map(x=>`<li>${x}</li>`).join('')}</ul></td></tr>`).join('')||`<tr><td colspan="6" class="sub">No items</td></tr>`;}
function showModal(){const m=$('modal'); if(m) m.style.display='flex';}
function hideModal(){const m=$('modal'); if(m) m.style.display='none';}

// Loads
async function refreshHealth(){ try{ showOut(await call('/health')); }catch(e){ showOut(e);} }
async function seedDemo(){ try{ const d=await call('/api/seed',{method:'POST'}); showOut(d); await loadAll(); toast('Seeded'); }catch(e){ showOut(e);} }
async function loadKPIs(){ try{ const k=await call('/api/kpis'); renderKPIs(k); }catch(e){ showOut(e);} }
async function loadTrends(){ try{ const t=await call('/api/trends'); ensureTrendChart(t.labels,(t.series&&t.series.spend)||[],(t.series&&t.series.roas)||[]); ensureTopChart((t.top&&t.top.labels)||[],(t.top&&t.top.clicks)||[]);}catch(e){ showOut(e);} }
async function loadRecs(){ try{ const d=await call('/api/insights'); renderInsights(d.insights||[]);}catch(e){ showOut(e);} }
async function loadPosts(){ try{ const d=await call('/api/posts'); $('posts').innerHTML=(d.posts||[]).map(p=>`<div class="badge">${p.platform}</div> ${p.title||''} <span class="sub">· ${p.caption||''}</span>`).join('<br>')||'<div class="sub">No posts yet.</div>'; }catch(e){ $('posts').innerHTML='<div class="sub">Sign in to load private posts.</div>'; } }
async function pullPosts(){ try{ const d=await call('/api/social/mock_pull',{method:'POST'}); showOut(d); await loadPosts(); toast('Demo posts added'); }catch(e){ showOut(e);} }

// Features
async function generatePlaybook(){ try{ const body=selectedForPlan.size?{insight_ids:[...selectedForPlan]}:{}; const d=await call('/api/playbook',{method:'POST',body:JSON.stringify(body)}); showOut(d); renderPlan(d.plan||[]); showModal(); }catch(e){ showOut(e);} }
async function askAI(){ try{ const q=$('aiq').value||''; const d=await call('/api/ai/ask',{method:'POST',body:JSON.stringify({q})}); $('aiout').textContent=d.answer||JSON.stringify(d,null,2);}catch(e){ $('aiout').textContent='Sign in to use the AI on your posts.'; } }
async function connect(platform){ try{ const d=await call(`/api/oauth/${platform}`); if(d.auth_url){ window.open(d.auth_url,'_blank'); toast('Opened auth (demo URL)'); }else{ toast('OAuth error'); } }catch(e){ toast('Sign in to connect'); } }
async function loadConnections(){ try{ const d=await call('/api/social/connections'); $('connections').innerHTML=(d.connections||[]).map(c=>`<span class="badge ${c.connected?'low':''}">${c.platform}${c.connected?' · connected':''}</span>`).join(' ')||'<span class="sub">No connections</span>'; }catch(e){ $('connections').innerHTML='<span class="sub">Sign in to view connections.</span>'; } }

// Contact
async function submitContact(){
  const payload={ name:($('c_name')||{}).value||'', email:($('c_email')||{}).value||'', company:($('c_company')||{}).value||'', phone:($('c_phone')||{}).value||'', message:($('c_msg')||{}).value||'' };
  try{ const r=await fetch('/api/contact',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(payload)}); const d=await r.json(); toast(d.ok?(d.emailed?'Message sent!':'Saved. Email not configured'):('Failed')); }catch(e){ toast('Submit error'); }
}

// Boot
async function loadAll(){ await Promise.allSettled([refreshAuthBadge(),refreshHealth(),loadKPIs(),loadTrends(),loadRecs(),loadConnections(),loadPosts()]); }
document.addEventListener('DOMContentLoaded', loadAll);

// expose for buttons in HTML
window.openAuth=openAuth; window.closeAuth=closeAuth;
window.register=register; window.login=login; window.logout=logout;
window.refreshHealth=refreshHealth; window.seedDemo=seedDemo;
window.pullPosts=pullPosts; window.generatePlaybook=generatePlaybook;
window.askAI=askAI; window.connect=connect; window.clearSelection=clearSelection;
window.submitContact=submitContact; window.hideModal=hideModal;
