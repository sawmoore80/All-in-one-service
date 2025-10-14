const API_BASE = "https://admindtech.onrender.com";
document.getElementById("yr").textContent = new Date().getFullYear();

async function j(u, o){ const r = await fetch(u, o||{}); return r.json(); }
function esc(s){ return (s||'').toString().replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function renderRecs(rs){
  const el = document.getElementById('recs');
  if(!rs || !rs.length){ el.innerHTML = '<i>No recommendations yet.</i>'; return; }
  el.innerHTML = rs.map(r => `
    <div class="panel" style="margin:8px 0">
      <b>${esc(r.action)}</b>
      <small>prio ${r.priority} · impact ${(+(r.impact_score||0)).toFixed(1)}</small>
      <div>${esc(r.rationale)}</div>
    </div>`).join('');
}

function renderAcc(a){
  document.getElementById('accounts').innerHTML = (a||[]).map(x =>
    `<div>${esc(x.name)} <small>(${esc(x.platform)})</small></div>`).join('');
}

function renderCamp(c){
  document.getElementById('campaigns').innerHTML = (c||[]).map(x =>
    `<div style="padding:6px 0;border-bottom:1px solid #1f2937">
      <b>${esc(x.name)}</b> — $${(+x.spend||0).toFixed(2)} | ROAS ${(+x.roas||0).toFixed(2)} | CTR ${(+x.ctr||0).toFixed(2)}%
     </div>`).join('');
}

async function load(){
  const a = await j('/api/accounts');      renderAcc(a.accounts||[]);
  const c = await j('/api/campaigns');     renderCamp(c.campaigns||[]);
  const r = await j('/api/recommendations'); renderRecs(r.recommendations||[]);
}

async function rebuild(){
  await j('/api/recommendations',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  load();
}

load();
