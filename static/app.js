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
