/* No identity simulation or browser-persisted tokens. Opaque HttpOnly sessions. */
const $ = s => document.querySelector(s);
const config = await (await fetch(`${location.pathname.replace(/\/$/, '')}/config`, {cache: 'no-store'})).json();
const base = config.api_base;
function message(s) { $('#status').textContent = s; }
async function api(path, params = {}, get = false) {
  const response = await fetch(base + path + (get ? '?' + new URLSearchParams({params: JSON.stringify(params)}) : ''), {
    method: get ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: {'Content-Type': 'application/json'}, ...(get ? {} : {body: JSON.stringify({params})})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(`Access denied (${response.status})`);
  return data;
}
async function task(fn) { try { await fn(); } catch (e) { message(e.message); } }
async function spaces() {
  const values = await api('/v1/kbs', {}, true); $('#spaces').replaceChildren();
  for (const item of values) { const li = document.createElement('li'); li.textContent = `${item.name} · ${item.kb_id}`; $('#spaces').append(li); }
  message('Authenticated. Only authorized data is displayed.');
}
async function login(value) {
  try {
    const response = await fetch(base + '/v1/auth/session', {method: 'POST', headers: {'Authorization': `Bearer ${value.trim()}`}, credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) throw new Error('OIDC authentication rejected');
    await spaces();
  } finally { value = ''; $('#bearer').value = ''; $('#token-file').value = ''; }
}
$('#session-form').addEventListener('submit', e => { e.preventDefault(); task(() => login($('#bearer').value)); });
$('#token-file').addEventListener('change', e => task(async () => { const file = e.target.files[0]; if (file) await login(await file.text()); }));
$('#refresh').addEventListener('click', () => task(spaces));
$('#logout').addEventListener('click', () => task(async () => { await fetch(base + '/v1/auth/logout', {method: 'POST', credentials: 'same-origin'}); for (const id of ['spaces','documents','search-results','citation-result','pack-result','alerts']) $('#' + id).replaceChildren(); message('Signed out'); }));
$('#documents-button').addEventListener('click', () => task(async () => { $('#documents').textContent = JSON.stringify(await api('/v1/documents', {}, true), null, 2); }));
$('#search-form').addEventListener('submit', e => { e.preventDefault(); task(async () => { $('#search-results').textContent = JSON.stringify(await api('/v1/search', {query: $('#query').value}), null, 2); }); });
$('#citation-form').addEventListener('submit', e => { e.preventDefault(); task(async () => { const response = await fetch(base + '/v1/mcp', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc:'2.0',id:1,method:'tools/call',params:{name:'verify_citation',arguments:{source_uri:$('#citation').value}}})}); if (!response.ok) throw new Error('Citation access denied'); $('#citation-result').textContent = JSON.stringify(await response.json(), null, 2); }); });
$('#pack-form').addEventListener('submit', e => { e.preventDefault(); task(async () => { $('#pack-result').textContent = JSON.stringify(await api('/v1/packs/get', {pack_id:$('#pack-id').value}), null, 2); }); });
$('#alerts-button').addEventListener('click', () => task(async () => { $('#alerts').textContent = JSON.stringify(await api('/v1/impact/alerts', {}), null, 2); }));
