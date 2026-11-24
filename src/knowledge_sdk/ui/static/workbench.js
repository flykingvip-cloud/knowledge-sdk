import {t, getLanguage, setLanguage, localize, enumLabel, errorText} from './i18n.js';
/* Offline ES module. No secrets, telemetry, CDN, or auto-ask. */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const split = value => value.split(',').map(v => v.trim()).filter(Boolean);
const tagged = (type, value) => ({...value, __type__: type});
const spaceTypes = () => ({enterprise_public: t("企业公共库"), department: t("部门库"), personal: t("个人库")});
const viewMeta = () => ({
  spaces: [t("知识空间"), t("把知识放在正确的位置，让每一次访问都有边界。")],
  documents: [t("文档与权限"), t("从正文到版本，从部门到密级，始终由后端执行访问控制。")],
  search: [t("检索与问答"), t("先检索已授权证据，再回答。没有证据，明确拒答。")],
  receipts: [t("消费与回执"), t("连接业务范围，追溯版本引用，核验每一份证据。")]
});
const presets = {
  admin: {user_id: 'admin', org_roles: ['admin', 'analyst'], department_ids: ['engineering'], managed_department_ids: ['engineering'], clearance_level: 'restricted'},
  lead: {user_id: 'eng-lead', org_roles: ['analyst'], department_ids: ['engineering'], managed_department_ids: ['engineering'], clearance_level: 'confidential'},
  engineer: {user_id: 'engineer', org_roles: ['analyst'], department_ids: ['engineering/platform'], ancestor_department_ids: ['engineering'], clearance_level: 'internal'},
  marketing: {user_id: 'marketer', org_roles: ['analyst'], department_ids: ['marketing'], clearance_level: 'internal'},
  visitor: {user_id: 'visitor', org_roles: ['viewer'], clearance_level: 'public'}
};
let actor = {org_id: 'demo-org', ...presets.admin};
let config, spaces = [], docs = [], receipts = [], bindings = [], selectedDocument;
let epoch = 0;
let documentDetail, lastHits, lastAnswer;
let busy = 0;
localize();
$('#language').value = getLanguage();

function el(tag, className = '', text = '') {
  const node = document.createElement(tag); node.className = className; node.textContent = text; return node;
}
function empty(target, message) { target.replaceChildren(el('div', 'empty', message)); }
function badge(text, tone = '') { return el('span', `badge ${tone}`, text); }
function json(value) { return details(t('技术数据（保留原始字段和值）'), el('pre', '', JSON.stringify(value, null, 2))); }
function button(text, onClick, className = 'secondary') {
  const node = el('button', className, text); node.type = 'button';
  node.addEventListener('click', () => task(onClick)); return node;
}
function details(title, content) {
  const node = el('details'); node.append(el('summary', '', title), content); return node;
}
function feedback(text, error = false) {
  const node = $('#feedback'); node.hidden = !text; node.className = error ? 'error' : ''; node.textContent = text;
}
async function task(callback) {
  const start = epoch;
  try { busy++; feedback(t('loading')); await callback(); if (start === epoch && $('#feedback').textContent === t('loading')) feedback(''); }
  catch (error) { if (start === epoch && error.name !== 'AbortError') feedback(errorText(), true); }
  finally { busy--; }
}
async function api(operation, params = {}) {
  const start = epoch;
  const [method, path] = config.operations[operation];
  const operationTarget = method === 'GET' ? `${path}?${new URLSearchParams({params: JSON.stringify(params)})}` : path;
  const target = config.signature_base + operationTarget;
  const requestTarget = config.api_base + operationTarget;
  const body = method === 'GET' ? '' : JSON.stringify({params});
  let headers = {'Content-Type': 'application/json'};
  if (config.demo_enabled) {
    const response = await fetch(`${config.ui_base}/demo/sign`, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-KB-Demo': '1'}, body: JSON.stringify({actor, method, target, body})});
    const signed = await response.json(); if (!response.ok) throw new Error(errorText());
    headers = {...headers, ...signed.headers};
  } else if (typeof window.knowledgeWorkbenchAuth === 'function') {
    // A trusted same-origin host gateway signs the EXACT method + target + body.
    // This callback must never contain a shared HMAC key or trust UI actor claims.
    headers = {...headers, ...await window.knowledgeWorkbenchAuth({method, target, body})};
  }
  if (start !== epoch) throw new DOMException('Identity changed', 'AbortError');
  const response = await fetch(requestTarget, {method, headers, credentials: 'same-origin', ...(method === 'GET' ? {} : {body})});
  const data = await response.json();
  if (start !== epoch) throw new DOMException('Identity changed', 'AbortError');
  if (!response.ok) throw new Error(errorText());
  return data;
}
function scope(mode, ids) {
  const list = split(ids);
  if (mode === 'all_authorized' && list.length) throw new Error(t("全权限范围不能填写 IDs"));
  return tagged('KnowledgeScope', {mode, ...(mode === 'spaces' ? {kb_ids: list} : mode === 'documents' ? {doc_ids: list} : {})});
}
function aclFrom(form) {
  const data = new FormData(form), result = {access_level: data.get('access_level')};
  for (const key of ['allowed_department_ids', 'allowed_org_roles', 'allowed_user_ids', 'allowed_clearance_tags']) result[key] = split(data.get(key) || '');
  result.include_sub_departments = data.has('include_sub_departments'); result.required_clearance = data.get('required_clearance') || '';
  return tagged('DocumentACL', result);
}
function populateIdentity(updateInputs = true) {
  const form = $('#identity-form');
  if (updateInputs) $$('input,select', form).filter(n => n.name).forEach(n => {
    const value = actor[n.name];
    if (n.type === 'checkbox') n.checked = Boolean(value); else n.value = Array.isArray(value) ? value.join(', ') : value || '';
  });
  $('#identity-label').textContent = $('#preset').value === 'custom' ? t('自定义') : $('#preset').selectedOptions[0].textContent;
  $('#identity-label').append(el('code', '', ` · ${actor.user_id} / ${actor.org_id}`));
}
function resetIdentity() {
  epoch++; spaces = []; docs = []; receipts = []; bindings = []; selectedDocument = null; documentDetail = lastHits = lastAnswer = null;
  for (const selector of ['#space-list', '#space-stats', '#document-list', '#document-detail', '#search-results', '#answer-panel', '#binding-list', '#receipt-list', '#verify-result']) $(selector).replaceChildren();
  for (const selector of ['#upload-space', '#doc-space', '#consumer-binding']) $(selector).replaceChildren();
  $('#space-count').textContent = ''; $('#hit-count').textContent = '';
  $('#file-name').textContent = t('未选择文件');
  $('#upload-form').reset(); $('#binding-form').reset(); $('#verify-form').reset(); $('#query-form').reset();
  populateIdentity(); feedback(t("身份已切换；结果、引用、回执与选择范围已清空。"));
}
async function loadSpaces() {
  const bases = await api('list_kbs');
  const result = [];
  for (const kb of bases) {
    const manage = await api('can_manage_kb', {kb_id: kb.kb_id});
    const upload = await api('can_upload_to_kb', {kb_id: kb.kb_id});
    result.push({...kb, manage, upload});
  }
  spaces = result; renderSpaces();
  const current = $('#doc-space').value;
  $('#doc-space').replaceChildren(new Option(t("所有可访问空间"), ''));
  $('#upload-space').replaceChildren();
  spaces.forEach(kb => {
    $('#doc-space').add(new Option(kb.name, kb.kb_id));
    if (kb.upload && kb.manage) $('#upload-space').add(new Option(kb.name, kb.kb_id));
  });
  if (spaces.some(k => k.kb_id === current)) $('#doc-space').value = current;
  $('#upload-form button[type="submit"],#upload-form button.primary').disabled = !$('#upload-space').options.length;
}
function renderSpaces() {
  const stats = $('#space-stats'); stats.replaceChildren();
  for (const [type, name] of Object.entries(spaceTypes())) {
    const stat = el('div', 'stat'); stat.append(el('span', 'stat-icon', type === 'enterprise_public' ? '◈' : type === 'department' ? '▦' : '◉'), el('small', '', name), el('strong', '', spaces.filter(k => k.space_type === type).length), el('small', '', name)); stats.append(stat);
  }
  const filter = $('#space-filter').value, list = $('#space-list'); list.replaceChildren();
  const visible = spaces.filter(k => !filter || k.space_type === filter); $('#space-count').textContent = t('spaceCount', visible.length);
  visible.forEach(kb => {
    const card = el('article', 'space-card card');
    card.append(el('div', 'space-icon', kb.space_type === 'enterprise_public' ? '◈' : kb.space_type === 'department' ? '▦' : '◉'), el('h3', '', kb.name), el('div', 'space-meta', `${spaceTypes()[kb.space_type]} / ${kb.owner_department_id || kb.owner_user_id || kb.owner_id}`));
    const permissions = el('div', 'actions'); permissions.append(badge(kb.manage ? t("可管理 · 可上传") : t("只读"), kb.manage ? 'green' : ''), button(t("打开文档 →"), async () => { $('#doc-space').value = kb.kb_id; await showView('documents'); }));
    card.append(badge(enumLabel(kb.space_type)), el('code', '', kb.kb_id), permissions); list.append(card);
  });
  if (!visible.length) empty(list, t("当前身份没有匹配的知识空间。"));
}
async function loadDocuments() {
  docs = await api('list_documents', $('#doc-space').value ? {kb_id: $('#doc-space').value} : {});
  renderDocuments();
}
function renderDocuments() {
  const list = $('#document-list'); list.replaceChildren();
  docs.forEach(doc => {
    const node = button('', () => openDocument(doc.doc_id), `doc-button${selectedDocument === doc.doc_id ? ' selected' : ''}`);
    node.append(el('strong', '', doc.title), el('small', '', `v${doc.current_version} · ${spaces.find(k => k.kb_id === doc.kb_id)?.name || doc.kb_id}`)); list.append(node);
  });
  if (!docs.length) empty(list, t("没有可访问文档"));
  if (!docs.some(d => d.doc_id === selectedDocument)) { selectedDocument = null; documentDetail = null; empty($('#document-detail'), t("选择一份文档，查看正文、版本与权限。")); }
}
async function openDocument(docId, version) {
  const detail = await api('inspect_document', {doc_id: docId, ...(version ? {version} : {})});
  documentDetail = detail; renderDocument(detail);
}
function renderDocument(detail) {
  const docId = detail.document.doc_id, version = detail.selected.version;
  selectedDocument = docId; const panel = $('#document-detail'); panel.replaceChildren();
  const top = el('div', 'detail-top'); top.append(el('h3', '', detail.document.title), badge(`v${detail.selected.version}`, 'green')); panel.append(top, el('code', '', docId));
  const rail = el('div', 'version-rail'); detail.versions.forEach(v => rail.append(button(`v${v.version} · ${v.filename}`, () => openDocument(docId, v.version), v.version === detail.selected.version ? 'selected' : ''))); panel.append(rail);
  panel.append(el('pre', 'body-preview', detail.selected.text));
  panel.append(details(t('chunks', detail.chunks.length), json(detail.chunks)));
  panel.append(details(t("版本元数据 / hashes"), json(detail.versions)));
  const aclPanel = details(t('currentACL', enumLabel(detail.acl.access_level)), json(detail.acl));
  if (detail.can_manage) {
    const form = el('form'); form.id = 'edit-acl-form'; form.noValidate = true;
    form.append($('#upload-acl').cloneNode(true)); form.firstChild.removeAttribute('id');
    form.elements.access_level.add(new Option(t("兼容策略（v1.0）"), ''));
    for (const [key, value] of Object.entries(detail.acl)) {
      const field = form.elements.namedItem(key); if (!field) continue;
      if (field.type === 'checkbox') field.checked = value; else field.value = Array.isArray(value) ? value.join(', ') : value;
    }
    const submit = el('button', 'primary', t("保存 ACL")); form.append(submit);
    form.addEventListener('submit', event => { event.preventDefault(); task(async () => { await api('set_document_acl', {doc_id: docId, acl: aclFrom(form)}); await loadDocuments(); if (selectedDocument) await openDocument(docId, version); feedback(t("权限已保存，当前身份可能不再具有正文访问权。")); }); });
    aclPanel.append(form);
  }
  panel.append(aclPanel);
  if (detail.can_upload) {
    const actions = el('div', 'actions');
    actions.append(button(t("创建下一版本"), async () => {
      $('#upload-panel').open = true; const form = $('#upload-form'); form.elements.kb_id.value = detail.document.kb_id; form.elements.doc_id.value = docId; form.elements.title.value = detail.document.title;
      if (!detail.acl.access_level && ![...form.elements.access_level.options].some(o => o.value === '')) form.elements.access_level.add(new Option(t("兼容策略（v1.0）"), ''));
      // Preserve the current policy, never silently widen ACL on a version update.
      for (const [key, value] of Object.entries(detail.acl)) { const f = form.elements.namedItem(key); if (!f) continue; if (f.type === 'checkbox') f.checked = value; else f.value = Array.isArray(value) ? value.join(', ') : value; }
      form.scrollIntoView({behavior: 'smooth'});
    }), button(t("归档文档（所有版本）"), async () => { if (!confirm(t("归档会使整份文档及其历史版本从检索、预览与引用中不可见。继续？"))) return; await api('archive', {doc_id: docId}); await loadDocuments(); feedback(t("文档及全部版本已归档；历史记录保留，不是删除。")); }, 'danger'));
    panel.append(actions, el('small', '', t("归档粒度为文档；历史版本不可改写，不支持单独归档某个历史版本。")));
  }
  $$('.doc-button', $('#document-list')).forEach((node, i) => node.classList.toggle('selected', docs[i]?.doc_id === docId));
}
function highlight(text, ranges) {
  const node = el('p'), chars = Array.from(text); let offset = 0;
  for (const [start, end] of (ranges || []).slice().sort((a, b) => a[0] - b[0])) {
    if (start < offset || start < 0 || end > chars.length || end <= start) continue;
    node.append(document.createTextNode(chars.slice(offset, start).join('')), el('mark', '', chars.slice(start, end).join(''))); offset = end;
  }
  node.append(document.createTextNode(chars.slice(offset).join(''))); return node;
}
function renderHits(hits) {
  lastHits = hits;
  const root = $('#search-results'); root.replaceChildren(); $('#hit-count').textContent = t('hitCount', hits.length);
  hits.forEach(hit => {
    const card = el('article', 'card result-card'), head = el('div', 'hit-title');
    head.append(el('h3', '', hit.title), badge(t('score', hit.score.toFixed(5))));
    card.append(head, highlight(hit.excerpt, hit.highlights), badge(hit.truncated ? t('truncated', hit.remaining_chars) : t("完整片段 · 未截断"), hit.truncated ? 'warning' : 'green'), el('code', '', hit.source_uri), el('code', '', `excerpt_hash: ${hit.excerpt_hash}`));
    if (hit.partial_notice || hit.masking_summary) card.append(el('p', 'muted', t('摘录已按权限策略处理。')));
    const actions = el('div', 'actions'); actions.append(button(t("引用并挂载"), async () => {
      const ref = await api('create_ref', {doc_id: hit.doc_id, version: hit.version, chunk_ids: [hit.chunk_id], excerpt: hit.excerpt});
      const attachment = await api('attach', {ref, ...(currentBinding() ? {binding: currentBinding()} : {})}); receipts.push(attachment); renderReceipts(); feedback(t("已生成版本引用与 MaterialReceipt；可在消费与回执页核验。"));
    }), button(t("打开来源"), async () => { await showView('documents'); await openDocument(hit.doc_id, hit.version); })); card.append(actions); root.append(card);
  });
  if (!hits.length) empty(root, t("没有已授权的命中。可更换关键词、范围或演示身份。"));
}
function renderAnswer(answer, recordReceipts = true) {
  lastAnswer = answer;
  const card = el('article', `answer-card${answer.status === 'refused' ? ' refused' : ''}`), head = el('div', 'panel-top');
  head.append(el('h2', '', answer.status === 'refused' ? t("未找到可用证据 · 明确拒答") : t("基于授权证据的回答")), badge(t('answerStatus', enumLabel(answer.status), t(answer.model_called ? t("是") : t("否"))), answer.status === 'refused' ? 'warning' : 'green'));
  card.append(head, el('p', '', answer.status === 'refused' ? t('无可用证据，无法回答。') : answer.answer));
  answer.citations.forEach((ref, i) => {
    const content = json(ref); const citation = details(`[${i + 1}] ${ref.source_uri}`, content);
    citation.append(button(t("核验此引用"), async () => { const result = await api('verify_ref', {ref}); content.replaceChildren(json({reference: ref, verification: result})); feedback(t('verifyStatus', enumLabel(result.status))); })); card.append(citation);
    if (recordReceipts) receipts.push({reference: ref, receipt: answer.receipts[i]});
  });
  $('#answer-panel').replaceChildren(card); renderReceipts();
}
async function loadBindings() { bindings = await api('list_consumer_bindings'); renderBindings(); }
function currentBinding() { return bindings[Number($('#consumer-binding').value)] && $('#consumer-binding').value !== '' ? bindings[Number($('#consumer-binding').value)] : null; }
function renderBindings() {
  const select = $('#consumer-binding'), selected = select.value; select.replaceChildren(new Option(t("不绑定消费者"), ''));
  bindings.forEach((b, i) => select.add(new Option(`${enumLabel(b.consumer_type)} / ${b.consumer_id}`, String(i))));
  if (selected !== '' && Number(selected) < bindings.length) select.value = selected;
  const root = $('#binding-list'); root.replaceChildren();
  bindings.forEach(binding => {
    const card = el('article', 'card space-card'); card.append(badge(enumLabel(binding.consumer_type), 'green'), el('h3', '', binding.consumer_id), badge(enumLabel(binding.default_scope.mode)), el('small', '', t('stage', binding.stage || '—')), json(binding.default_scope)); root.append(card);
  });
  if (!bindings.length) empty(root, t("当前身份尚无消费范围绑定。"));
}
function renderReceipts() {
  const root = $('#receipt-list'); root.replaceChildren();
  receipts.forEach((item, index) => {
    const card = el('article', 'card receipt-card'); card.append(badge(enumLabel(item.receipt?.status || 'reference')), el('code', '', item.reference.source_uri), details(t("KnowledgeRef"), json(item.reference)), details(t("MaterialReceipt"), json(item.receipt)));
    const actions = el('div', 'actions');
    actions.append(button(t("verify_ref 防篡改核验"), async () => { const verified = await api('verify_ref', {ref: item.reference}); result.replaceChildren(json(verified)); }), button(t("载入手动核验"), async () => { $('#verify-form').elements.reference.value = JSON.stringify(item.reference, null, 2); $('#verify-form').parentElement.open = true; $('#verify-form').scrollIntoView({behavior: 'smooth'}); }));
    const result = el('div'); card.append(actions, result); root.append(card);
  });
  if (!receipts.length) empty(root, t("本次会话暂无引用与回执。"));
}
async function showView(view) {
  $$('.view').forEach(n => { n.hidden = n.id !== `view-${view}`; });
  $$('.nav').forEach(n => { n.classList.toggle('active', n.dataset.view === view); if (n.dataset.view === view) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current'); });
  $('#view-title').textContent = viewMeta()[view][0]; $('#view-description').textContent = viewMeta()[view][1];
  if (view === 'documents') await loadDocuments();
  if (view === 'search') await loadBindings();
  if (view === 'receipts') { await loadBindings(); renderReceipts(); }
}
function wireEvents() {
  $$('form').forEach(form => {
    form.noValidate = true;
    form.addEventListener('submit', event => {
      if ([...form.querySelectorAll('[required]')].some(n => !n.value.trim())) {
        event.preventDefault(); event.stopImmediatePropagation(); feedback(t('请填写必填字段。'), true);
      }
    });
  });
  $$('.nav').forEach(node => node.addEventListener('click', () => task(() => showView(node.dataset.view))));
  $('#preset').addEventListener('change', event => { if (event.target.value === 'custom') return; actor = {org_id: 'demo-org', ...presets[event.target.value]}; resetIdentity(); task(async () => { await loadSpaces(); await showView($('.nav.active').dataset.view); }); });
  $('#identity-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget, values = new FormData(form), next = {};
    for (const key of ['org_id', 'user_id', 'clearance_level']) next[key] = values.get(key).trim();
    for (const key of ['department_ids', 'ancestor_department_ids', 'org_roles', 'roles', 'managed_department_ids', 'clearance_tags']) next[key] = split(values.get(key));
    next.public_kb_admin = values.has('public_kb_admin'); actor = next; $('#preset').value = 'custom'; resetIdentity(); task(async () => { await loadSpaces(); await showView($('.nav.active').dataset.view); });
  });
  $('#space-filter').addEventListener('change', renderSpaces);
  $('#doc-space').addEventListener('change', () => task(loadDocuments));
  $('#space-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form);
    task(async () => { await api('create_kb', Object.fromEntries(data)); await loadSpaces(); form.reset(); feedback(t("知识空间已创建。")); });
  });
  $('#upload-form').addEventListener('submit', event => {
    event.preventDefault(); const form = event.currentTarget;
    task(async () => {
      const uploadEpoch = epoch;
      const data = new FormData(form), file = data.get('file'); const params = {kb_id: data.get('kb_id'), title: data.get('title'), acl: aclFrom(form)};
      if (data.get('doc_id').trim()) params.doc_id = data.get('doc_id').trim();
      if (file.size) {
        if (file.size > 16 * 1024 * 1024) throw new Error(t("文件超过 16 MiB"));
        params.filename = file.name; const bytes = new Uint8Array(await file.arrayBuffer());
        if (epoch !== uploadEpoch) throw new DOMException('Identity changed', 'AbortError');
        let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        params.content_b64 = btoa(binary);
      } else { params.filename = 'document.md'; params.content = data.get('content'); }
      const uploaded = await api('ingest', params); await loadDocuments();
      // A newly restrictive ACL may remove even the creator's content access.
      if (docs.some(d => d.doc_id === uploaded.doc_id)) await openDocument(uploaded.doc_id, uploaded.version);
      feedback(t('uploaded', uploaded.doc_id, uploaded.version));
    });
  });
  $('#query-form').addEventListener('submit', event => {
    event.preventDefault(); const action = event.submitter?.value || 'search';
    task(async () => {
      const selectedScope = scope($('#scope-mode').value, $('#scope-ids').value), mode = $('#search-mode').value, query = $('#query').value;
      $('#answer-panel').replaceChildren(); lastAnswer = null;
      if (action === 'ask') { const answer = await api('ask', {question: query, mode, scope: selectedScope, ...(currentBinding() ? {binding: currentBinding()} : {})}); renderAnswer(answer); renderHits(answer.evidence_hits); }
      else { const result = await api('search', {query, mode, scope: selectedScope}); renderHits(result.hits); }
    });
  });
  $('#binding-form').addEventListener('submit', event => {
    event.preventDefault(); const values = new FormData(event.currentTarget);
    task(async () => { const binding = tagged('ConsumerBinding', {consumer_type: values.get('consumer_type'), consumer_id: values.get('consumer_id'), stage: values.get('stage'), default_scope: scope(values.get('mode'), values.get('ids'))}); await api('bind_consumer', {binding}); await loadBindings(); feedback(t("消费范围绑定已保存。")); });
  });
  $('#refresh-bindings').addEventListener('click', () => task(loadBindings));
  $('#verify-form').addEventListener('submit', event => { event.preventDefault(); task(async () => { const ref = tagged('KnowledgeRef', JSON.parse(event.currentTarget.elements.reference.value)); $('#verify-result').textContent = '';
      try { const result = await api('verify_ref', {ref}); $('#verify-result').textContent = JSON.stringify(result, null, 2); }
      catch (error) { if (error.name !== 'AbortError') $('#verify-result').textContent = t('verifyFailed'); throw error; } }); });
}
async function start() {
  const response = await fetch(new URL('../config', import.meta.url), {credentials: 'same-origin'}); if (!response.ok) throw new Error(t('Workbench 配置不可用')); config = await response.json();
  if (config.demo_enabled) populateIdentity();
  renderConnection();
  wireEvents(); renderReceipts(); await loadSpaces();
}
function renderConnection() {
  if (!config) return;
  $('#auth-badge').textContent = config.demo_enabled ? t("LOCAL DEMO / 演示模式") : t("HMAC / 生产网关模式");
  if (config.demo_enabled) {
    $('#identity-warning').textContent = t("仅限本地隔离演示：可任意模拟身份。请勿在真实数据服务启用开发签名器。密钥仅保留在服务端。");
    populateIdentity(false);
  } else {
    $('#identity-label').textContent = t("宿主认证身份"); $('#identity-warning').textContent = t("生产模式关闭身份模拟；Actor 仅由受信网关签名。");
    $$('input,select,button', $('#identity-form')).forEach(n => { n.disabled = true; });
    feedback(t("生产模式：请接入同源 HMAC 网关。静态页面不具备签名密钥，也不信任浏览器角色。"));
  }
  if (!config.vector_available) {
    $$('#search-mode option').filter(n => n.value !== 'keyword').forEach(n => { n.disabled = true; n.textContent = `${enumLabel(n.value)}${t("（需配置向量后端）")}`; });
    $('#retrieval-note').textContent = t("当前未配置向量后端，使用关键词检索 + 本地抽取式回答；无模型调用。");
  }
}
// Locale changes only rerender cached data. They never search, ask, or sign a request.
function changeLanguage(value) {
  setLanguage(value); localize(); $('#language').value = getLanguage();
  const view = $('.nav.active').dataset.view;
  $('#view-title').textContent = viewMeta()[view][0];
  $('#view-description').textContent = viewMeta()[view][1];
  renderConnection();
  renderSpaces(); renderDocuments();
  if (documentDetail) {
    const oldForm = $('#edit-acl-form');
    const fields = oldForm ? [...oldForm.elements].filter(n => n.name).map(n => [n.name, n.type === 'checkbox' ? n.checked : n.value]) : [];
    renderDocument(documentDetail);
    for (const [name, value] of fields) {
      const field = $('#edit-acl-form')?.elements.namedItem(name);
      if (field) { if (field.type === 'checkbox') field.checked = value; else field.value = value; }
    }
  }
  if (lastHits) renderHits(lastHits);
  if (lastAnswer) renderAnswer(lastAnswer, false);
  renderBindings(); renderReceipts();
  // Select options are data, not text inputs: refresh only the localized empty caption.
  const allOption = $('#doc-space option[value=""]');
  if (allOption) allOption.textContent = t('所有可访问空间');
  if (!$('#upload-form').elements.file.files.length) $('#file-name').textContent = t('未选择文件');
  if ($('#verify-result').textContent && !$('#verify-result').textContent.trim().startsWith('{')) $('#verify-result').textContent = t('verifyFailed');
  feedback(busy ? t('loading') : t('语言已切换。'));
}
$('#language').addEventListener('change', event => changeLanguage(event.target.value));
$('#pick-file').addEventListener('click', () => $('#upload-form').elements.file.click());
$('#upload-form').elements.file.addEventListener('change', event => { $('#file-name').textContent = event.target.files[0]?.name || t('未选择文件'); });
task(start);
