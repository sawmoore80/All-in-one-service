(function(){
  const $=id=>document.getElementById(id);
  let trendChart, topChart, selected=new Set();

  function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000);}
  function showOut(o){$('out').textContent=typeof o==='string'?o:JSON.stringify(o,null,2);}
  async function call(path,opts={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},credentials:'include',...opts});const txt=await r.text();let d;try{d=JSON.parse(txt);}catch{d={raw:txt}};if(!r.ok) throw d; return d;}

  function openAuth(){ $('authModal').style.display='flex'; }
  function closeAuth(){ $('authModal').style.display='none'; }
  async function refreshAuthBadge(){ try{const d=await call('/api/me'); $('authBadge').textContent=d.auth?(d.email||'User'):'Guest'; $('whoami').textContent=d.auth?(d.email||'user'):'guest'; }catch{ $('authBadge').textContent='Guest'; } }
  async function register(){ const email=$('email').value, password=$('password').value; const d=await call('/api/register',{method:'POST',body:JSON.stringify({email,password})}); toast('Account created'); await refreshAuthBadge(); closeAuth(); loadAll();}
  async function login(){ const email=$('email').value, password=$('password').value; const d=await call('/api/login',{method:'POST',body:JSON.stringify({email,password})}); toast('Signed in'); await refreshAuthBadge(); closeAuth(); loadAll();}
  async function logout(){ await call('/api/logout',{method:'POST'}); toast('Signed out'); await refreshAuthBadge(); }

  function currency(n){return '$'+(Number(n)||0).toLocaleString(undefined,{maximumFractionDigits:0});}
  function ensureTrendChart(labels,spend,roas){const el=$('trendChart'); if(!el||!window.Chart) return; if(trendChart) trendChart.destroy(); trendChart=new Chart(el,{type:'line',data:{labels,datasets:[{label:'Spend',data:spend,borderColor:'#4ea8ff',backgroundColor:'rgba(78,168,255,.12)',yAxisID:'y',tension:.35},{label:'ROAS',data:roas,borderColor:'#f472b6',backgroundColor:'rgba(244,114,182,.10)',yAxisID:'y1',tension:.35}]},options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'},grid:{color:'rgba(255,255,255,.06)'}},y:{ticks:{color:'#9fb3c8'}},y1:{position:'right',ticks:{color:'#9fb3c8'},grid:{display:false}}}});}
  function ensureTopChart(labels,clicks){const el=$('topChart'); if(!el||!window.Chart) return; if(topChart) topChart.destroy(); topChart=new Chart(el,{type:'bar',data:{labels,datasets:[{label:'Clicks',data:clicks,backgroundColor:'#7c3aed'}]},options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'}},y:{ticks:{color:'#9fb3c8'}}}});}

  function renderKPIs(k){$('kpis').innerHTML=[{label:'Total Spend',value:currency(k.total_spend)},{label:'Avg ROAS',value:(k.avg_roas??0).toFixed(2)},{label:'Avg CPA',value:currency(k.avg_cpa)},{label:'Conversions',value:(k.conversions||0).toLocaleString()}].map(x=>`<div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>`).join('');}
  function badge(txt,cls){const klass=cls==='high'?'badge high':cls==='med'?'badge med':cls==='low'?'badge low':'badge';return `<span class="${klass}">${txt}</span>`;}
  function pretty(obj){return Object.entries(obj||{}).map(([k,v])=>`<div><span class="badge">${k}</span> <b>${v}</b></div>`).join('')}
  function insightCard(i){const sel=selected.has(i.id);return `<div class="card" style="margin:10px 0"><div style="display:flex;justify-content:space-between;gap:8px"><div><div style="font-weight:800">${i.title}</div><div class="sub">Campaign: ${i.campaign_name}</div></div><div>${badge(i.kpi,'kpi')} ${badge(i.severity,i.severity)} ${badge('Score '+i.priority_score,'low')}</div></div><div class="evidence"><b>Why:</b>${pretty(i.evidence)}</div><div><b>Actions (48h):</b><ul>${(i.actions||[]).map(a=>`<li>${a}</li>`).join('')}</ul></div><div class="sub" style="margin-top:6px">Expected impact: +${Math.round((i.expected_impact||0)*100)}%</div><div style="margin-top:10px"><button class="btn ${sel?'danger':''}" onclick="toggleSelect(${i.id})">${sel?'Remove':'Add'} to Plan</button></div></div>`;}
  function renderInsights(list){$('recs').innerHTML=(list||[]).map(insightCard).join('')||'<div class="sub">No insights yet.</div>'; }
  function toggleSelect(id){ if(selected.has(id)){selected.delete(id);toast('Removed');} else {selected.add(id);toast('Added');} loadRecs(); }
  function renderPlan(plan){$('planRows').innerHTML=(plan||[]).map(p=>`<tr><td>${p.day}</td><td>${p.title}</td><td>${p.kpi}</td><td>${p.severity}</td><td><ul>${p.what_to_ship.map(x=>`<li>${x}</li>`).join('')}</ul></td><td><ul>${p.how_to_measure.map(x=>`<li>${x}</li>`).join('')}</ul></td></tr>`).join('')||`<tr><td colspan="6" class="sub">No items</td></tr>`;}
  function showModal(){const m=$('modal'); if(m) m.style.display='flex';}
  function hideModal(){const m=$('modal'); if(m) m.style.display='none';}

  async function refreshHealth(){ try{ showOut(await call('/health')); }catch(e){ showOut(e);} }
  async function seedDemo(){ try{ const d=await call('/api/seed',{method:'POST'}); showOut(d); await loadAll(); toast('Seeded'); }catch(e){ showOut(e);} }
  async function loadKPIs(){ try{ const k=await call('/api/kpis'); renderKPIs(k);}catch(e){ showOut(e);} }
  async function loadTrends(){ try{ const t=await call('/api/trends'); ensureTrendChart(t.labels,t.series?.spend||[],t.series?.roas||[]); ensureTopChart(t.top?.labels||[],t.top?.clicks||[]);}catch(e){ showOut(e);} }
  async function loadRecs(){ try{ const d=await call('/api/insights'); renderInsights(d.insights||[]);}catch(e){ showOut(e);} }
  async function loadPosts(){ try{ const d=await call('/api/posts'); $('posts').innerHTML=(d.posts||[]).map(p=>`<div class="badge">${p.platform}</div> ${p.title||''} <span class="sub">· ${p.caption||''}</span>`).join('<br>')||'<div class="sub">No posts yet.</div>'; }catch(e){ $('posts').innerHTML='<div class="sub">Sign in to load private posts.</div>'; } }
  async function pullPosts(){ try{ const d=await call('/api/social/mock_pull',{method:'POST'}); showOut(d); await loadPosts(); toast('Demo posts added'); }catch(e){ showOut(e);} }

  async function generatePlaybook(){ try{ const body=selected.size?{insight_ids:[...selected]}:{}; const d=await call('/api/playbook',{method:'POST',body:JSON.stringify(body)}); showOut(d); renderPlan(d.plan||[]); showModal(); }catch(e){ showOut(e);} }
  async function askAI(){ try{ const q=$('aiq').value||''; const d=await call('/api/ai/ask',{method:'POST',body:JSON.stringify({q})}); $('aiout').textContent=d.answer||JSON.stringify(d,null,2);}catch(e){ $('aiout').textContent='AI error'; } }
  async function connect(platform){ try{ const d=await call(`/api/oauth/${platform}`); if(d.auth_url){ window.location=d.auth_url; } else { toast('Provider not configured'); } }catch(e){ toast('Connect error'); } }

  function wire(){
    const w=[
      ['btnAccount',openAuth],['btnCloseAuth',closeAuth],
      ['btnDoRegister',register],['btnDoLogin',login],['btnLogout',logout],
      ['btnHealth',refreshHealth],['btnSeed',seedDemo],['btnPull',pullPosts],
      ['btnPlan',generatePlaybook],['btnPlan2',generatePlaybook],['btnClearSel',()=>{selected.clear();loadRecs();}],
      ['btnAskAI',askAI],
      ['btnIG',()=>connect('instagram')],['btnTT',()=>connect('tiktok')],['btnFB',()=>connect('facebook')],['btnYT',()=>connect('youtube')],['btnLI',()=>connect('linkedin')],
      ['btnClosePlan',hideModal]
    ];
    for(const [id,fn] of w){ const el=$(id); if(el) el.addEventListener('click',fn); }
  }

  async function loadAll(){ wire(); await Promise.allSettled([refreshAuthBadge(),refreshHealth(),loadKPIs(),loadTrends(),loadRecs(),loadPosts()]); }
  document.addEventListener('DOMContentLoaded', loadAll);
})();
