(function(){
  const $=id=>document.getElementById(id);
  function toast(m){const t=$('toast'); if(!t) return; t.textContent=m; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1800);}
  async function call(path, opts={}){const r=await fetch(path,{credentials:'include',headers:{'Content-Type':'application/json'},...opts});const t=await r.text();let d;try{d=JSON.parse(t);}catch{d={raw:t}};if(!r.ok) throw d; return d;}
  function showOut(o){const el=$('out'); if(el) el.textContent=typeof o==='string'?o:JSON.stringify(o,null,2);}

  // ----- auth modal -----
  function openAuth(){const m=$('authModal'); if(m) m.style.display='flex';}
  function closeAuth(){const m=$('authModal'); if(m) m.style.display='none';}
  async function refreshAuthBadge(){ try{ const d=await call('/api/me'); ($('authBadge')||{}).textContent = d.auth ? (d.email||'User'): 'Guest'; ($('whoami')||{}).textContent=d.auth?(d.email||'user'):'guest'; }catch{} }
  async function register(){ const email=$('email').value, password=$('password').value; await call('/api/register',{method:'POST',body:JSON.stringify({email,password})}); toast('Account created'); await refreshAuthBadge(); closeAuth(); }
  async function login(){ const email=$('email').value, password=$('password').value; await call('/api/login',{method:'POST',body:JSON.stringify({email,password})}); toast('Signed in'); await refreshAuthBadge(); closeAuth(); }
  async function logout(){ try{ await call('/api/logout',{method:'POST'}); toast('Signed out'); await refreshAuthBadge(); }catch(e){ toast('Logout error'); } }

  // ----- widgets -----
  function currency(n){return '$'+(Number(n)||0).toLocaleString(undefined,{maximumFractionDigits:0});}
  let trendChart, topChart;
  function ensureTrendChart(labels,spend,roas){ if(!window.Chart) return; const el=$('trendChart'); if(!el) return; if(trendChart) trendChart.destroy(); trendChart=new Chart(el,{type:'line',data:{labels,datasets:[{label:'Spend',data:spend},{label:'ROAS',data:roas,yAxisID:'y1'}]},options:{responsive:true,maintainAspectRatio:false,scales:{y1:{position:'right'}}}});}
  function ensureTopChart(labels,clicks){ if(!window.Chart) return; const el=$('topChart'); if(!el) return; if(topChart) topChart.destroy(); topChart=new Chart(el,{type:'bar',data:{labels,datasets:[{label:'Clicks',data:clicks}]} ,options:{responsive:true,maintainAspectRatio:false}});}

  function renderKPIs(k){ if(!$('kpis')) return; $('kpis').innerHTML=[{label:'Total Spend',value:currency(k.total_spend)},{label:'Avg ROAS',value:(k.avg_roas||0).toFixed(2)},{label:'Avg CPA',value:currency(k.avg_cpa)},{label:'Conversions',value:(k.conversions||0).toLocaleString()}].map(x=>`<div class="kpi"><div class="label">${x.label}</div><div class="value">${x.value}</div></div>`).join(''); }
  function badge(txt,cls){return `<span class="badge ${cls||''}">${txt}</span>`;}
  let selected=new Set();
  function insightCard(i){const sel=selected.has(i.id); return `<div class="card" style="margin:10px 0"><div class="row between"><div><b>${i.title}</b><div class="sub">Campaign: ${i.campaign_name||'-'}</div></div><div>${badge(i.kpi,'low')} ${badge(i.severity,i.severity)} ${badge('Score '+i.priority_score,'')}</div></div><div><b>Why:</b><pre>${JSON.stringify(i.evidence||{},null,2)}</pre></div><div><b>Actions:</b><ul>${(i.actions||[]).map(a=>`<li>${a}</li>`).join('')}</ul></div><div class="sub">Expected impact: +${Math.round((i.expected_impact||0)*100)}%</div><div style="margin-top:8px"><button class="btn ${sel?'danger':''}" onclick="toggleSelect(${i.id})">${sel?'Remove':'Add'} to Plan</button></div></div>`;}
  function renderInsights(list){ if(!$('recs')) return; $('recs').innerHTML=(list||[]).map(insightCard).join('')||'<div class="sub">No insights</div>'; }
  window.toggleSelect=function(id){ if(selected.has(id)) selected.delete(id); else selected.add(id); loadRecs(); }
  window.clearSelection=function(){ selected.clear(); loadRecs(); }

  function renderPlan(plan){ $('planRows').innerHTML = (plan||[]).map(p=>`<tr><td>${p.day}</td><td>${p.title}</td><td>${p.kpi}</td><td>${p.severity}</td><td><ul>${p.what_to_ship.map(x=>`<li>${x}</li>`).join('')}</ul></td><td><ul>${p.how_to_measure.map(x=>`<li>${x}</li>`).join('')}</ul></td></tr>`).join('')||`<tr><td colspan="6" class="sub">No items</td></tr>`; }
  function showModal(){ const m=$('modal'); if(m) m.style.display='flex'; }
  window.hideModal=function(){ const m=$('modal'); if(m) m.style.display='none'; }

  // ----- API loaders -----
  async function refreshHealth(){ try{ const d=await call('/health'); showOut(d);}catch(e){ showOut(e);} }
  async function seedDemo(){ try{ const d=await call('/api/seed',{method:'POST'}); showOut(d); await loadAll(); toast('Seeded'); }catch(e){ showOut(e);} }
  async function loadKPIs(){ try{ const k=await call('/api/kpis'); renderKPIs(k);}catch(e){ showOut(e);} }
  async function loadTrends(){ try{ const t=await call('/api/trends'); ensureTrendChart(t.labels,t.series?.spend||[],t.series?.roas||[]); ensureTopChart(t.top?.labels||[],t.top?.clicks||[]);}catch(e){ showOut(e);} }
  async function loadRecs(){ try{ const d=await call('/api/insights'); renderInsights(d.insights||[]);}catch(e){ showOut(e);} }
  async function loadPosts(){ try{ const d=await call('/api/posts'); $('posts').innerHTML=(d.posts||[]).map(p=>`<div class="badge">${p.platform}</div> ${p.title||''} <span class="sub">· ${p.caption||''}</span>`).join('<br>')||'<div class="sub">No posts</div>'; }catch(e){ $('posts').innerHTML='<div class="sub">No posts</div>'; } }
  async function pullPosts(){ try{ const d=await call('/api/social/mock_pull',{method:'POST'}); showOut(d); await loadPosts(); toast('Demo posts added'); }catch(e){ showOut(e);} }

  // ----- feature actions -----
  async function generatePlaybook(){ try{ const body=selected.size?{insight_ids:[...selected]}:{}; const d=await call('/api/playbook',{method:'POST',body:JSON.stringify(body)}); showOut(d); renderPlan(d.plan||[]); showModal(); }catch(e){ showOut(e);} }
  async function askAI(){ try{ const q=$('aiq').value||''; const d=await call('/api/ai/ask',{method:'POST',body:JSON.stringify({q})}); $('aiout').textContent=d.answer||JSON.stringify(d,null,2); }catch(e){ $('aiout').textContent='AI error'; showOut(e);} }
  async function connect(platform){ try{ const d=await call(`/api/oauth/${platform}`); if(d.auth_url) { window.open(d.auth_url,'_blank'); toast('Opening provider'); } else { toast('Missing client ID'); } }catch(e){ toast('Connect error'); } }

  // expose on window so onclick works from HTML
  window.openAuth=openAuth; window.closeAuth=closeAuth;
  window.register=register; window.login=login; window.logout=logout;
  window.refreshHealth=refreshHealth; window.seedDemo=seedDemo; window.pullPosts=pullPosts;
  window.generatePlaybook=generatePlaybook; window.askAI=askAI; window.connect=connect;

  // boot
  async function loadAll(){ await Promise.allSettled([refreshAuthBadge(),refreshHealth(),loadKPIs(),loadTrends(),loadRecs(),loadPosts()]); }
  document.addEventListener('DOMContentLoaded', loadAll);
})();
