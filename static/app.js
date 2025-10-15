(function(){
  function $(id){return document.getElementById(id);}
  var trendChart, topChart, selectedForPlan=new Set();

  function toast(m){var t=$('toast'); if(!t) return; t.textContent=m; t.classList.add('show'); setTimeout(function(){t.classList.remove('show');},2200);}
  function showOut(o){var el=$('out'); if(!el) return; try{el.textContent=typeof o==='string'?o:JSON.stringify(o,null,2);}catch(e){el.textContent=String(o);}}
  function call(path, opts){
    if(!opts) opts={};
    var base = { headers:{'Content-Type':'application/json'}, credentials:'include' };
    for(var k in opts){ base[k]=opts[k]; }
    return fetch(path, base).then(function(r){
      return r.text().then(function(txt){
        var d; try{ d=JSON.parse(txt); }catch(_){ d={raw:txt}; }
        if(!r.ok) throw d;
        return d;
      });
    });
  }

  // ----- auth -----
  function openAuth(){ var m=$('authModal'); if(m) m.style.display='flex'; }
  function closeAuth(){ var m=$('authModal'); if(m) m.style.display='none'; }
  function refreshAuthBadge(){
    return call('/api/me').then(function(d){
      if(d.auth){ $('authBadge').textContent=d.email||'User'; var w=$('whoami'); if(w) w.textContent=d.email||'user'; }
      else { $('authBadge').textContent='Guest'; var w2=$('whoami'); if(w2) w2.textContent='guest'; }
    }).catch(function(){ $('authBadge').textContent='Guest'; });
  }
  function register(){
    var email=$('email').value, password=$('password').value;
    call('/api/register',{method:'POST',body:JSON.stringify({email:email,password:password})})
      .then(function(){ toast('Account created'); return refreshAuthBadge(); })
      .then(function(){ closeAuth(); loadAll(); })
      .catch(function(e){ toast((e&&e.error)||'Register error'); showOut(e); });
  }
  function login(){
    var email=$('email').value, password=$('password').value;
    call('/api/login',{method:'POST',body:JSON.stringify({email:email,password:password})})
      .then(function(){ toast('Signed in'); return refreshAuthBadge(); })
      .then(function(){ closeAuth(); loadAll(); })
      .catch(function(e){ toast((e&&e.error)||'Login error'); showOut(e); });
  }
  function logout(){
    call('/api/logout').then(function(){ toast('Signed out'); return refreshAuthBadge(); })
      .catch(function(){ toast('Logout error'); });
  }

  // ----- charts & render -----
  function currency(n){ return '$'+(Number(n)||0).toLocaleString(undefined,{maximumFractionDigits:0}); }
  function ensureTrendChart(labels,spend,roas){
    var el=$('trendChart'); if(!el || !window.Chart) return;
    if(trendChart) trendChart.destroy();
    trendChart=new Chart(el,{type:'line',data:{labels:labels,datasets:[
      {label:'Spend',data:spend,borderColor:'#4ea8ff',backgroundColor:'rgba(78,168,255,.12)',yAxisID:'y',tension:.35},
      {label:'ROAS',data:roas,borderColor:'#6ee7b7',backgroundColor:'rgba(110,231,183,.10)',yAxisID:'y1',tension:.35}
    ]},options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'},grid:{color:'rgba(255,255,255,.06)'}},y:{ticks:{color:'#9fb3c8'}},y1:{position:'right',ticks:{color:'#9fb3c8'},grid:{display:false}}}});}
  function ensureTopChart(labels,clicks){
    var el=$('topChart'); if(!el || !window.Chart) return;
    if(topChart) topChart.destroy();
    topChart=new Chart(el,{type:'bar',data:{labels:labels,datasets:[{label:'Clicks',data:clicks,backgroundColor:'#7c3aed'}]},options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#cfe3f0'}}},scales:{x:{ticks:{color:'#9fb3c8'}},y:{ticks:{color:'#9fb3c8'}}}});}
  function renderKPIs(k){
    var items=[
      {label:'Total Spend',value:currency(k.total_spend)},
      {label:'Avg ROAS',value:(Number(k.avg_roas)||0).toFixed(2)},
      {label:'Avg CPA',value:currency(k.avg_cpa)},
      {label:'Conversions',value:(Number(k.conversions)||0).toLocaleString()}
    ];
    $('kpis').innerHTML=items.map(function(x){return '<div class="kpi"><div class="label">'+x.label+'</div><div class="value">'+x.value+'</div></div>';}).join('');
  }
  function badge(txt,cls){ var klass=cls==='high'?'badge high':cls==='med'?'badge med':cls==='low'?'badge low':'badge'; return '<span class="'+klass+'">'+txt+'</span>'; }
  function insightCard(i){
    var sel=selectedForPlan.has(i.id);
    return '<div class="card" style="margin:10px 0">'+
      '<div style="display:flex;justify-content:space-between;gap:8px">'+
        '<div><div style="font-weight:800">'+i.title+'</div><div class="sub">Campaign: '+i.campaign_name+'</div></div>'+
        '<div>'+badge(i.kpi,'kpi')+' '+badge(i.severity,i.severity)+' '+badge('Score '+i.priority_score,'low')+'</div>'+
      '</div>'+
      '<div style="margin-top:8px"><b>Why:</b><pre>'+JSON.stringify(i.evidence||{},null,2)+'</pre></div>'+
      '<div><b>Actions (48h):</b><ul>'+((i.actions||[]).map(function(a){return '<li>'+a+'</li>';}).join(''))+'</ul></div>'+
      '<div class="sub" style="margin-top:6px">Expected impact: +'+Math.round((i.expected_impact||0)*100)+'%</div>'+
      '<div style="margin-top:10px"><button class="btn '+(sel?'danger':'')+'" data-insight="'+i.id+'">'+(sel?'Remove':'Add')+' to Plan</button></div>'+
    '</div>';
  }
  function renderInsights(list){
    $('recs').innerHTML=(list||[]).map(insightCard).join('')||'<div class="sub">No insights yet.</div>';
    // wire Add/Remove buttons inside cards
    var buttons = $('recs').querySelectorAll('button[data-insight]');
    for(var i=0;i<buttons.length;i++){
      buttons[i].addEventListener('click', function(ev){
        var id = Number(ev.currentTarget.getAttribute('data-insight'));
        if(selectedForPlan.has(id)){ selectedForPlan.delete(id); toast('Removed'); }
        else { selectedForPlan.add(id); toast('Added'); }
        loadRecs();
      });
    }
  }
  function clearSelection(){ selectedForPlan.clear(); loadRecs(); toast('Cleared'); }
  function renderPlan(plan){
    $('planRows').innerHTML=(plan||[]).map(function(p){
      return '<tr><td>'+p.day+'</td><td>'+p.title+'</td><td>'+p.kpi+'</td><td>'+p.severity+'</td><td><ul>'+p.what_to_ship.map(function(x){return '<li>'+x+'</li>';}).join('')+'</ul></td><td><ul>'+p.how_to_measure.map(function(x){return '<li>'+x+'</li>';}).join('')+'</ul></td></tr>';
    }).join('')||'<tr><td colspan="6" class="sub">No items</td></tr>';
  }
  function showModal(){ var m=$('modal'); if(m) m.style.display='flex'; }
  function hideModal(){ var m=$('modal'); if(m) m.style.display='none'; }

  // ----- data loads -----
  function refreshHealth(){ return call('/api/test').then(showOut).catch(showOut); }
  function seedDemo(){ return call('/api/seed',{method:'POST'}).then(function(d){showOut(d);toast('Seeded');return loadAll();}).catch(showOut); }
  function loadKPIs(){ return call('/api/kpis').then(renderKPIs).catch(showOut); }
  function loadTrends(){ return call('/api/trends').then(function(t){ ensureTrendChart(t.labels,(t.series&&t.series.spend)||[],(t.series&&t.series.roas)||[]); ensureTopChart((t.top&&t.top.labels)||[],(t.top&&t.top.clicks)||[]); }).catch(showOut); }
  function loadRecs(){ return call('/api/insights').then(function(d){ renderInsights(d.insights||[]); }).catch(showOut); }
  function loadPosts(){
    return call('/api/posts').then(function(d){
      $('posts').innerHTML=(d.posts||[]).map(function(p){ return '<div class="badge">'+p.platform+'</div> '+(p.title||'')+' <span class="sub">· '+(p.caption||'')+'</span>'; }).join('<br>')||'<div class="sub">No posts yet.</div>';
    }).catch(function(){
      // not signed in — show demo posts
      call('/api/posts_demo').then(function(d){
        $('posts').innerHTML=(d.posts||[]).map(function(p){ return '<div class="badge">'+p.platform+'</div> '+(p.title||'')+' <span class="sub">· '+(p.caption||'')+'</span>'; }).join('<br>');
      });
    });
  }
  function pullPosts(){ return call('/api/social/mock_pull',{method:'POST'}).then(function(d){showOut(d);toast('Demo posts added');return loadPosts();}).catch(showOut); }

  // ----- features -----
  function generatePlaybook(){
    var body = selectedForPlan.size ? {insight_ids:Array.from(selectedForPlan)} : {};
    return call('/api/playbook',{method:'POST',body:JSON.stringify(body)}).then(function(d){ showOut(d); renderPlan(d.plan||[]); showModal(); }).catch(showOut);
  }
  function askAI(){
    var q=$('aiq').value||'';
    return call('/api/ai/ask',{method:'POST',body:JSON.stringify({q:q})}).then(function(d){ $('aiout').textContent=d.answer||JSON.stringify(d,null,2); }).catch(function(e){ $('aiout').textContent='AI error'; showOut(e); });
  }
  function connect(platform){
    return call('/api/oauth/'+platform).then(function(d){
      if(d.auth_url){ window.open(d.auth_url,'_blank'); toast('Opened auth (demo URL)'); }
      else toast('OAuth error');
    }).catch(function(){ toast('Sign in to connect'); });
  }
  function loadConnections(){
    return call('/api/social/connections').then(function(d){
      $('connections').innerHTML=(d.connections||[]).map(function(c){ return '<span class="badge '+(c.connected?'low':'')+'">'+c.platform+(c.connected?' · connected':'')+'</span>'; }).join(' ') || '<span class="sub">No connections</span>';
    }).catch(function(){ $('connections').innerHTML='<span class="sub">Sign in to view connections.</span>'; });
  }

  // ----- contact -----
  function submitContact(){
    var payload={
      name:($('c_name')||{}).value||'',
      email:($('c_email')||{}).value||'',
      company:($('c_company')||{}).value||'',
      phone:($('c_phone')||{}).value||'',
      message:($('c_msg')||{}).value||''
    };
    return fetch('/api/contact',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(d){ toast(d.ok ? (d.emailed?'Message sent!':'Saved (email not configured)') : 'Failed'); })
      .catch(function(){ toast('Submit error'); });
  }

  // ----- wire buttons by ID -----
  function wire(){
    var w = [
      ['btnAccount', openAuth],
      ['btnHealth', refreshHealth],
      ['btnSeed', seedDemo],
      ['btnPull', pullPosts],
      ['btnPlan', generatePlaybook],
      ['btnLogout', logout],
      ['btnAskAI', askAI],
      ['btnIG', function(){connect('instagram');}],
      ['btnTT', function(){connect('tiktok');}],
      ['btnFB', function(){connect('facebook');}],
      ['btnYT', function(){connect('youtube');}],
      ['btnClearSel', clearSelection],
      ['btnContact', submitContact],
      ['btnClosePlan', hideModal]
    ];
    for(var i=0;i<w.length;i++){ var b=$(w[i][0]); if(b) b.addEventListener('click', w[i][1]); }
  }

  function loadAll(){
    wire();
    Promise.allSettled([refreshAuthBadge(),refreshHealth(),loadKPIs(),loadTrends(),loadRecs(),loadConnections(),loadPosts()])
      .then(function(){ /* loaded */ })
      .catch(function(e){ showOut(e); });
  }

  document.addEventListener('DOMContentLoaded', loadAll);

  // expose minimal for modal actions inside the auth form
  window.register=register; window.login=login; window.closeAuth=closeAuth;
})();
