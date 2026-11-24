/* Deterministic, dependency-free DOM contract harness, not a browser. */
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../src/knowledge_sdk/ui/static');
let stored = process.env.TEST_LANGUAGE || null;
const storageWrites = [];
class Element {
  constructor(tag = 'div', text = '') {
    this.tagName = tag; this.children = []; this._text = text; this.value = ''; this.hidden = false;
    this.dataset = {}; this.attributes = {}; this.files = []; this.name = '';
    this.elements = {file: {files: []}};
    this.classList = {toggle() {}};
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent ?? String(n)).join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = [...nodes]; }
  add(node) { this.children.push(node); }
  get options() { return this.children; }
  get selectedOptions() { return [{textContent: stored === 'en' ? 'Enterprise administrator' : '企业管理员'}]; }
  setAttribute(k, v) { this.attributes[k] = v; }
  getAttribute(k) { return this.attributes[k]; }
  removeAttribute(k) { delete this.attributes[k]; }
  querySelectorAll() { return []; }
  addEventListener() {}
  reset() {}
}
const nodes = new Map();
const get = selector => {
  if (!nodes.has(selector)) nodes.set(selector, new Element());
  return nodes.get(selector);
};
get('.nav.active').dataset.view = 'spaces';
get('#preset').value = 'admin';
get('#doc-space option[value=""]').value = '';
let localizedNodes = [], attributeNodes = [];
const document = {
  documentElement: {lang: 'zh-CN'},
  querySelector: get,
  querySelectorAll(selector) {
    if (selector === '[data-i18n]') return localizedNodes;
    if (selector.startsWith('[data-i18n-')) return attributeNodes;
    return [];
  },
  createElement: tag => new Element(tag),
  createTextNode: text => new Element('text', text),
};
const context = vm.createContext({console, document, window: {
  localStorage: {
    getItem() { if (process.env.BLOCK_STORAGE) throw Error('blocked'); return stored; },
    setItem(k,v) { if (process.env.BLOCK_STORAGE) throw Error('blocked'); stored=v; storageWrites.push([k,v]); },
  },
}, Option: class extends Element { constructor(text, value) { super('option', text); this.value=value; } },
DOMException, URLSearchParams, fetch() { throw Error('Unexpected network/model request'); }});
const locale = fs.readFileSync(path.join(root, 'i18n.js'), 'utf8').replaceAll('export ', '');
let script = fs.readFileSync(path.join(root, 'workbench.js'), 'utf8').replace(/^import .*;\n/, '');
// vm.Script is not an ES module: substitute only its module URL syntax.
script = script.replaceAll('import.meta.url', JSON.stringify('http://localhost/ui/assets/workbench.js'));
script = script.slice(0, script.indexOf("$('#language').addEventListener('change'"));
vm.runInContext(locale + '\n' + script, context);
function run(source) { return vm.runInContext(source, context); }
const cases = {
  default() { assert.equal(run('getLanguage()'), 'zh-CN'); assert.equal(run("t('知识空间')"), '知识空间'); },
  english() { run("setLanguage('en')"); assert.equal(run("t('知识空间')"), 'Knowledge spaces'); assert.equal(run("t('hitCount', 7)"), '7 hits'); },
  persistence() { run("setLanguage('en')"); assert.deepEqual(storageWrites, [['knowledge-workbench-language','en']]); },
  reload() { assert.equal(run('getLanguage()'), 'en'); },
  fallback() { run("setLanguage('invalid')"); assert.equal(run('getLanguage()'), 'zh-CN'); assert.match(run("t('missing-key')"), /操作失败/); run("setLanguage('en')"); assert.match(run("t('missing-key')"), /Operation failed/); },
  storageBlocked() { run("setLanguage('en')"); assert.equal(run("t('知识空间')"), 'Knowledge spaces'); },
  staticDOM() {
    const n = new Element(); n.setAttribute('data-i18n', '知识空间'); localizedNodes = [n];
    const a = new Element(); a.setAttribute('data-i18n-placeholder', '文档标题'); attributeNodes = [a];
    run("setLanguage('en'); localize()"); assert.equal(n.textContent, 'Knowledge spaces'); assert.equal(a.getAttribute('placeholder'), 'Document title'); assert.equal(document.documentElement.lang, 'en');
    run("setLanguage('zh-CN'); localize()"); assert.equal(n.textContent, '知识空间'); assert.equal(document.documentElement.lang, 'zh-CN');
  },
  dynamic() {
    run("spaces = [{space_type:'enterprise_public', kb_id:'kb-1', name:'原始文档空间', manage:true}]; setLanguage('en'); renderSpaces(); renderReceipts(); renderBindings()");
    assert.match(get('#space-list').textContent, /Manage & upload/); assert.match(get('#space-list').textContent, /原始文档空间/); assert.doesNotMatch(get('#space-list').textContent, /可管理|enterprise_public/);
    assert.match(get('#space-count').textContent, /1 spaces/); assert.match(get('#receipt-list').textContent, /No references/);
    run("setLanguage('zh-CN'); renderSpaces(); renderReceipts()"); assert.match(get('#space-list').textContent, /可管理/); assert.doesNotMatch(get('#space-list').textContent, /Manage|enterprise_public/);
  },
  evidence() {
    run("setLanguage('en'); renderHits([{title:'文档原题', excerpt:'原始正文', highlights:[], score:0.5, truncated:true, remaining_chars:5, source_uri:'kb://doc-1', excerpt_hash:'a', partial_notice:'UNTRANSLATED SERVER NOTICE'}])");
    assert.match(get('#search-results').textContent, /Truncated/); assert.match(get('#search-results').textContent, /原始正文/); assert.doesNotMatch(get('#search-results').textContent, /UNTRANSLATED|已截断/);
    run("setLanguage('zh-CN'); renderHits(lastHits)"); assert.match(get('#search-results').textContent, /已截断/); assert.doesNotMatch(get('#search-results').textContent, /Score|Truncated/);
  },
  refusal() {
    run("setLanguage('zh-CN'); renderAnswer({status:'refused', model_called:false, answer:'No authorized evidence.', citations:[], receipts:[]})");
    assert.match(get('#answer-panel').textContent, /拒答/); assert.doesNotMatch(get('#answer-panel').textContent, /No authorized|refused|model_called/);
    run("setLanguage('en'); renderAnswer(lastAnswer, false)"); assert.match(get('#answer-panel').textContent, /Refused/); assert.doesNotMatch(get('#answer-panel').textContent, /拒答/);
  },
  errors() { run("setLanguage('zh-CN')"); assert.doesNotMatch(run("errorText(new Error('secret server diagnostic'))"), /secret|diagnostic/); run("setLanguage('en')"); assert.match(run('errorText()'), /Operation failed/); },
  enums() { for(const code of ['admin','viewer','public','enterprise_public','org_public','all_authorized','keyword','consumed']) { const value=run(`enumLabel('${code}')`); assert.notEqual(value, code); } run("setLanguage('en')"); assert.equal(run("enumLabel('enterprise_public')"), 'Enterprise public library'); },
  switchCached() {
    run("config={demo_enabled:true,vector_available:false}; changeLanguage('en'); changeLanguage('zh-CN'); changeLanguage('en')");
    assert.equal(get('#view-title').textContent, 'Knowledge spaces'); assert.equal(get('#auth-badge').textContent, 'Local demo mode'); assert.equal(run('getLanguage()'), 'en'); assert.match(get('#identity-label').textContent, /Enterprise administrator/);
  },
  documents() {
    run("setLanguage('en'); renderDocument({document:{doc_id:'doc-1',title:'原始标题'}, selected:{version:1,text:'原始正文'},versions:[{version:1,filename:'original.md'}],chunks:[],acl:{access_level:'role_clearance'},can_manage:false,can_upload:false})");
    assert.match(get('#document-detail').textContent, /Current access policy \/ Roles & clearance/);
    assert.match(get('#document-detail').textContent, /原始正文/);
    run("setLanguage('zh-CN'); renderDocument(documentDetail || {document:{doc_id:'doc-1',title:'原始标题'},selected:{version:1,text:'原始正文'},versions:[],chunks:[],acl:{access_level:'role_clearance'},can_manage:false,can_upload:false})");
    assert.match(get('#document-detail').textContent, /当前权限策略/);
    assert.doesNotMatch(get('#document-detail').textContent, /Current access policy/);
  },
  receipts() {
    run("receipts=[]; setLanguage('en'); renderAnswer({status:'answered',model_called:false,answer:'原始回答',citations:[{source_uri:'kb://doc-1'}],receipts:[{status:'partial'}]}); renderAnswer(lastAnswer,false)");
    assert.equal(run('receipts.length'), 1);
    assert.match(get('#receipt-list').textContent, /Partially consumed/);
    run("setLanguage('zh-CN'); renderReceipts()");
    assert.match(get('#receipt-list').textContent, /部分消费/);
  },
  chromeIdentity() {
    const before = run('JSON.stringify(actor)');
    run("setLanguage('en'); populateIdentity(false)");
    assert.match(get('#identity-label').textContent, /Enterprise administrator/);
    assert.match(get('#identity-label').textContent, /admin \/ demo-org/);
    assert.doesNotMatch(get('#identity-label').textContent, /engineering|Restricted|Analyst/);
    run("setLanguage('zh-CN'); populateIdentity(false)");
    assert.match(get('#identity-label').textContent, /企业管理员/);
    assert.equal(run('JSON.stringify(actor)'), before);
    run("config={demo_enabled:false,vector_available:true}; renderConnection()");
    assert.match(get('#identity-label').textContent, /宿主认证身份/);
    assert.match(get('#identity-warning').textContent, /生产模式关闭身份模拟/);
    run("setLanguage('en'); renderConnection()");
    assert.doesNotMatch(get('#identity-warning').textContent, /[\u4e00-\u9fff]/);
  },
  chromeNavigation() {
    const keys = ['知识空间', '文档与权限', '检索与问答', '消费与回执'];
    localizedNodes = keys.map(key => { const n = new Element(); n.setAttribute('data-i18n', key); return n; });
    run("setLanguage('en'); localize()");
    assert.deepEqual(localizedNodes.map(n => n.textContent), ['Knowledge spaces', 'Documents & permissions', 'Search & answers', 'Consumers & receipts']);
    run("setLanguage('zh-CN'); localize()");
    assert.deepEqual(localizedNodes.map(n => n.textContent), keys);
  },
  identity() { run("setLanguage('en'); resetIdentity()"); assert.equal(run('getLanguage()'), 'en'); assert.match(get('#feedback').textContent, /Identity changed/); },
};
cases[process.argv[2]]();
