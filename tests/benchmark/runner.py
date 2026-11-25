"""Exactly 75 executable scenarios (original 60 unchanged). SQLite offline or real optional PostgreSQL; no LLM, skips or random rank claims."""
from __future__ import annotations
import argparse
import concurrent.futures
from contextlib import closing
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib,json,secrets,tempfile,os,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.contracts.uri import build_uri
from knowledge_sdk.mcp import GatewayContext,GatewayAuthenticator,EvidenceTools,tool_definitions,MCPProtocol
from knowledge_sdk.server.auth import signed_headers,SQLiteReplayStore
from knowledge_sdk.retrieval.base import VectorHit
from knowledge_sdk.permissions.engine import DefaultPolicyEngine
from knowledge_sdk.retrieval.hybrid import search as hybrid_search

SCENARIOS={}
def scenario(name):
    def register(fn):
        if name in SCENARIOS:raise ValueError('Duplicate scenario')
        SCENARIOS[name]=fn;return fn
    return register


class Observation:
    def __init__(self,expected=None):self._expected=expected or {};self.safety_failures=0;self.positive_failures=0;self.model_calls=0;self.injection_attempts=0;self.injection_blocked=0;self.recall=None;self.audit_checks=0;self.audit_detected=0;self.impact_expected=0;self.impact_found=0;self.impact_unexpected=0
    def check(self,value,kind='correctness'):
        if not value:
            if kind=='safety':self.safety_failures+=1
            if kind=='positive':self.positive_failures+=1
            raise AssertionError(kind+' assertion failed')
    def denied(self,fn,reason=None):
        reason=reason if reason is not None else self._expected.get('reason_code')
        try:fn()
        except PermissionDeniedError as exc:
            self.check(reason is None or str(exc)==reason);return
        self.check(False,'safety')
    def invalid(self,fn,injection=False):
        if injection:self.injection_attempts+=1
        try:fn()
        except ValidationError:
            if injection:self.injection_blocked+=1
            return
        self.check(False,'safety')


class Fixture:
    def __init__(self,case,engine='sqlite'):
        self.engine=engine;self.sandbox=None;self.replays=[]
        if engine=='postgres':
            from tests.pg_helpers import PgSandbox,golden_client
            self.sandbox=PgSandbox();client=golden_client(self.sandbox.dsn)
        else:client=LocalKnowledgeClient()
        self.case=case;self.params=case['expected'].get('fixture_parameters',{});self.c=client;self.secret=secrets.token_hex(32);self.old_secret=secrets.token_hex(32)
        self.a=Actor('admin','org',org_roles=('admin',),managed_department_ids=('dep',));self.u=Actor('reader','org')
        self.c.create_kb(self.a,'baseline','enterprise',kb_id='kb')
        self.agent=AgentIdentity('gateway-agent','org');self.ctx=GatewayContext(self.u,self.agent,Purpose.GROUND_INTERNAL_LLM);self.tools=EvidenceTools(self.c)
    def doc(self,text='alpha evidence',id='doc',**kwargs):
        acl=kwargs.pop('acl',None)
        value=self.c.ingest(self.a,'kb',text,doc_id=id,**kwargs)
        if acl is not None:self.c.set_document_acl(self.a,id,acl)
        return value
    def uri(self,id='doc',version=1,anchor=None):return build_uri('org',id,version,anchor_id=anchor)
    def call(self,name,**kwargs):
        if 'task_id' in kwargs:
            from tests.runtime_helpers import provision_task
            provision_task(self.c,self.a,self.u,self.agent.agent_id,kwargs['task_id'],self.ctx.purpose)
        return self.tools.call(name,kwargs,self.ctx)
    def replay_store(self,path):
        if self.engine=='sqlite':return SQLiteReplayStore(path)
        from knowledge_sdk.server.replay_pg import PostgresReplayStore
        store=PostgresReplayStore(self.sandbox.dsn);self.replays.append(store);return store
    def close(self):
        for store in self.replays:store.close()
        try:self.c.store.close()
        finally:
            if self.sandbox:self.sandbox.close()


@scenario('tenant_document_read')
def g101(f,o):
    f.doc();o.denied(lambda:f.c.retrieve(Actor('reader','foreign'),'doc'),'tenant_mismatch')
    a=f.c.list_anchors(f.a,'doc')[0];o.denied(lambda:f.c.get_anchor(Actor('reader','foreign'),'doc',a.anchor_id),'tenant_mismatch')
@scenario('tenant_search_isolation')
def g102(f,o):
    f.doc('alpha private tenant marker');o.check(not f.c.search(Actor('reader','foreign'),'alpha').hits,'safety')
@scenario('department_exact_boundary')
def g103(f,o):
    f.doc(acl=DocumentACL(access_level='department',allowed_department_ids=('dep',)))
    o.denied(lambda:f.c.retrieve(f.u,'doc'));o.check(bool(f.c.retrieve(replace(f.u,department_ids=('dep',)),'doc').text),'positive')
@scenario('department_ancestor_inheritance')
def g104(f,o):
    f.doc(acl=DocumentACL(access_level='department',allowed_department_ids=('dep',),include_sub_departments=True))
    o.denied(lambda:f.c.retrieve(f.u,'doc'));o.check(bool(f.c.retrieve(replace(f.u,ancestor_department_ids=('dep',)),'doc').text),'positive')
@scenario('department_no_ancestor_expansion')
def g105(f,o):
    f.doc(acl=DocumentACL(access_level='department',allowed_department_ids=('dep',),include_sub_departments=False))
    o.denied(lambda:f.c.retrieve(replace(f.u,ancestor_department_ids=('dep',)),'doc'))
    o.check(bool(f.c.retrieve(replace(f.u,department_ids=('other','dep')),'doc').text),'positive')
@scenario('explicit_deny_owner')
def g106(f,o):
    f.doc(acl=DocumentACL(deny_users=('admin',)));o.denied(lambda:f.c.retrieve(f.a,'doc'),'explicit_acl_deny')
@scenario('explicit_deny_nonowner_admin')
def g107(f,o):
    f.doc(acl=DocumentACL(deny_users=('second-admin',)));o.denied(lambda:f.c.retrieve(Actor('second-admin','org',org_roles=('admin',)),'doc'),'explicit_acl_deny')
@scenario('explicit_deny_role')
def g108(f,o):
    f.doc(acl=DocumentACL(deny_roles=('contractor',)));o.denied(lambda:f.c.retrieve(replace(f.u,roles=('contractor',)),'doc'),'explicit_acl_deny')
@scenario('explicit_deny_department')
def g109(f,o):
    f.doc(acl=DocumentACL(deny_departments=('dep',)));o.denied(lambda:f.c.retrieve(replace(f.u,department_ids=('dep',)),'doc'),'explicit_acl_deny')
@scenario('historic_receipt_current_revocation')
def g110(f,o):
    f.doc();ref=f.c.reference(f.u,'doc',excerpt='alpha');f.c.ingest(f.a,'kb','alpha updated',doc_id='doc')
    f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));r=f.c.consume(f.u,ref);o.check((r.status,r.reason_code)==('denied','resource_revoked'),'safety')
@scenario('agent_kb_intersection')
def g111(f,o):
    f.doc();agent=replace(f.agent,allowed_kb_ids=('other',));o.check(not f.c.search(f.u,'alpha',agent=agent).hits,'safety');o.denied(lambda:f.c.retrieve(f.u,'doc',agent=agent),'agent_scope_denied')
@scenario('agent_clearance_ceiling')
def g112(f,o):
    f.doc(acl=DocumentACL(required_clearance='restricted'));o.denied(lambda:f.c.retrieve(f.a,'doc',agent=replace(f.agent,max_clearance_level='internal')),'agent_clearance_exceeded')
@scenario('agent_purpose_intersection')
def g113(f,o):
    f.doc(rights=ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True));o.denied(lambda:f.c.retrieve(f.u,'doc',agent=f.agent,purpose=Purpose.GROUND_EXTERNAL_LLM),'agent_purpose_denied')
@scenario('external_llm_default_prohibition')
def g114(f,o):
    f.doc();o.denied(lambda:f.c.retrieve(f.u,'doc',purpose=Purpose.GROUND_EXTERNAL_LLM),'external_llm_prohibited')
    o.denied(lambda:f.c.retrieve(f.u,'doc',purpose=Purpose.EVAL_AND_TRAIN),'training_prohibited')
@scenario('l2_validity_personal_hard_boundaries')
def g115(f,o):
    f.c.create_kb(f.a,'controlled','enterprise',kb_id='controlled',governance_tier='l2_controlled')
    f.c.ingest(f.a,'controlled','alpha',doc_id='draft',lifecycle_state='draft')
    o.denied(lambda:f.c.retrieve(f.u,'draft'),'lifecycle_not_published')
    f.doc(valid_to='2020-01-01T00:00:00Z');o.denied(lambda:f.c.retrieve(f.u,'doc'),'outside_validity_window')
    f.c.create_kb(f.a,'private','private',kb_id='private',space_type='personal')
    f.c.ingest(f.a,'private','alpha',doc_id='private-doc');o.denied(lambda:f.c.retrieve(f.u,'private-doc'),'space_boundary_denied')
@scenario('allow_cannot_bypass_hard_boundaries_or_deny')
def g116(f,o):
    f.c.policy_engine=DefaultPolicyEngine([PolicyRule('allow','org',DecisionEffect.ALLOW,priority=1),PolicyRule('deny','org',DecisionEffect.DENY,priority=999,scope_doc_id='doc')])
    f.doc();o.denied(lambda:f.c.retrieve(f.u,'doc'),'explicit_policy_deny')
    f.c.policy_engine=DefaultPolicyEngine([PolicyRule('allow','org',DecisionEffect.ALLOW,priority=1)])
    f.c.create_kb(f.a,'private','private',kb_id='private',space_type='personal');f.c.ingest(f.a,'private','alpha',doc_id='private-doc')
    o.denied(lambda:f.c.retrieve(f.u,'private-doc'),'space_boundary_denied')
    o.denied(lambda:f.c.retrieve(Actor('foreign','other'),'doc'),'tenant_mismatch')
@scenario('missing_redactor_never_plaintext')
def g117(f,o):
    f.doc('alpha SECRET',rights=ResourceRights(redaction_profile='missing'))
    o.denied(lambda:f.c.retrieve(f.u,'doc'),'redaction_hook_missing');o.check(not f.c.search(f.u,'alpha').hits,'safety')
    o.denied(lambda:f.c.list_anchors(f.u,'doc'),'redaction_hook_missing');spy=ModelSpy();answer=f.c.ask(f.u,'alpha',generator=spy);o.model_calls+=spy.calls
    o.check(answer.status=='refused' and spy.calls==0,'safety')
class Embed:
    def __init__(self):self.calls=0
    def embed(self,texts):self.calls+=1;return [[1] for _ in texts]
class Index:
    def __init__(self,rows):self.rows=rows
    def search(self,vector,limit):return self.rows[:limit]
    def delete_document(self,*args):pass
    def upsert(self,*args):pass
def vector(f,rows):f.c.vector_index=Index(rows);f.c.embedder=Embed()
@scenario('stale_vector_revoked')
def g118(f,o):
    f.doc('alpha SECRET');ch=f.c.store.get_chunks('doc',1)[0];f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));vector(f,[VectorHit('doc',1,ch.chunk_id,1)])
    o.check(not f.c.search(f.u,'alpha',mode='vector').hits,'safety')
    f.c.set_document_rights(f.a,'doc',ResourceRights());f.c.archive(f.a,'doc');o.check(not f.c.search(f.u,'alpha',mode='vector').hits,'safety')
@scenario('forged_cross_tenant_vector')
def g119(f,o):
    other=Actor('owner','other');k=f.c.create_kb(other,'other');v=f.c.ingest(other,k.kb_id,'alpha SECRET');ch=f.c.store.get_chunks(v.doc_id,1)[0];vector(f,[VectorHit(v.doc_id,1,ch.chunk_id,1)])
    o.check(not f.c.search(f.u,'alpha',mode='vector').hits,'safety')
    f.doc(rights=ResourceRights(redaction_profile='crash'))
    class Crash:
        def redact(self,*args):raise RuntimeError('SECRET')
    f.c.redaction_registry.register('crash',Crash());o.denied(lambda:f.c.retrieve(f.u,'doc'),'redaction_failed')
@scenario('mcp_no_existence_title_or_count_oracle')
def g120(f,o):
    f.doc('alpha SECRET TITLE',title='SECRET TITLE',rights=ResourceRights(revoked=True))
    revoked=f.call('verify_citation',source_uri=f.uri());absent=f.call('verify_citation',source_uri=f.uri('absent'))
    o.check(revoked==absent and 'SECRET' not in json.dumps(revoked) and 'count' not in json.dumps(revoked),'safety')

class ModelSpy:
    def __init__(self):self.calls=0
    def generate(self,*args):self.calls+=1;return GeneratedAnswer('unexpected model path',True)
def refusal(f,o,**kwargs):
    spy=ModelSpy();answer=f.c.ask(f.u,'alpha',generator=spy,**kwargs);o.model_calls+=spy.calls
    o.check(answer.status==f.case['expected']['status'] and not answer.model_called and spy.calls==f.case['expected']['generator_calls'],'safety')
@scenario('refusal_empty_corpus')
def g201(f,o):refusal(f,o)
@scenario('refusal_unrelated_content')
def g202(f,o):
    f.doc('unrelated beta');refusal(f,o)
@scenario('refusal_explicit_acl_only')
def g203(f,o):f.doc(acl=DocumentACL(deny_users=('reader',)));refusal(f,o)
@scenario('refusal_archived_only')
def g204(f,o):f.doc();f.c.archive(f.a,'doc');refusal(f,o)
@scenario('refusal_revoked_only')
def g205(f,o):f.doc(rights=ResourceRights(revoked=True));refusal(f,o)
@scenario('refusal_l2_draft_only')
def g206(f,o):
    f.c.create_kb(f.a,'controlled','enterprise',kb_id='controlled',governance_tier='l2_controlled');f.c.ingest(f.a,'controlled','alpha',doc_id='draft',lifecycle_state='draft');refusal(f,o)
@scenario('refusal_expired_validity_only')
def g207(f,o):
    f.doc(valid_to='2020-01-01T00:00:00Z');refusal(f,o,policy_context=PolicyContext(now='2030-01-01T00:00:00Z'))
@scenario('refusal_missing_hook_only')
def g208(f,o):
    f.doc(rights=ResourceRights(redaction_profile='missing'));refusal(f,o)
@scenario('refusal_below_min_score')
def g209(f,o):
    f.doc();refusal(f,o,min_score=1.0)
@scenario('refusal_generation_time_revocation')
def g210(f,o):
    from knowledge_sdk.client import local as module
    f.doc();original=module.run_search
    def revoke(*args,**kwargs):
        response=original(*args,**kwargs);f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));return response
    with patch.object(module,'run_search',side_effect=revoke):refusal(f,o)
    f.c.set_document_rights(f.a,'doc',ResourceRights());answer=f.c.ask(f.u,'alpha');o.check(answer.status=='answered' and not answer.model_called,'positive')


def many(f,count,denied=0,kb='kb',prefix='a'):
    ids=[]
    for i in range(count):
        doc=prefix+str(i).zfill(4);f.c.ingest(f.a,kb,'dense signal',doc_id=doc,acl=DocumentACL(deny_users=('reader',)) if i<denied else None);ids.append(doc)
    return ids

def recall(o,hits,relevant):
    o.recall=len({h.doc_id for h in hits}.intersection(relevant))/o._expected.get('hits',5)
    o.check(len(hits)==o._expected.get('hits',5) and all(h.doc_id in relevant for h in hits),'positive')

@scenario('fetch_90_percent_acl_150')
def g301(f,o):
    ids=many(f,f.params['count'],f.params['denied']);r=f.c.search(f.u,'dense',limit=5);recall(o,r.hits,ids[-15:]);o.check(not r.candidate_budget_exhausted)
@scenario('fetch_mixed_120_archive_revoke_acl')
def g302(f,o):
    ids=many(f,120,35)
    for doc in ids[35:70]:f.c.archive(f.a,doc)
    for doc in ids[70:105]:f.c.set_document_rights(f.a,doc,ResourceRights(revoked=True))
    r=f.c.search(f.u,'dense',limit=5);recall(o,r.hits,ids[105:]);o.check(not r.candidate_budget_exhausted)
@scenario('fetch_document_scope_prebudget_600')
def g303(f,o):
    many(f,f.params['noise']);ids=many(f,5,prefix='z')
    with patch.object(f.c.store,'keyword_search_pushdown',wraps=f.c.store.keyword_search_pushdown) as spy:
        r=f.c.search(f.u,'dense',limit=5,scope=KnowledgeScope('documents',doc_ids=ids));o.check(spy.call_args.kwargs['doc_ids']==ids)
    recall(o,r.hits,ids)
@scenario('fetch_scope_550_noise_three_targets')
def g304(f,o):
    many(f,550);f.c.create_kb(f.a,'selected','enterprise',kb_id='selected');ids=many(f,3,kb='selected',prefix='z')
    with patch.object(f.c.store,'keyword_search_pushdown',wraps=f.c.store.keyword_search_pushdown) as spy:
        r=f.c.search(f.u,'dense',limit=3,scope=KnowledgeScope('spaces',kb_ids=('selected',)));o.check(spy.call_args.kwargs['kb_ids']==['selected'])
    recall(o,r.hits,ids);o.check(not r.candidate_budget_exhausted)
@scenario('fetch_redacted_hits_count_toward_limit')
def g305(f,o):
    ids=many(f,7)
    for doc in ids:f.c.set_document_rights(f.a,doc,ResourceRights(redaction_profile='mask'))
    f.c.redaction_registry.register('mask',RegexRedactionHook([('dense','[MASK]')]))
    r=f.c.search(f.u,'dense',limit=5);recall(o,r.hits,ids);o.check(all('[MASK]' in h.excerpt and 'dense' not in h.excerpt and h.masking_summary for h in r.hits))
@scenario('fetch_empty_scope_intersection')
def g306(f,o):
    many(f,10)
    with patch.object(f.c.store,'keyword_search_pushdown',side_effect=AssertionError('Empty intersection must not query')):
        r=hybrid_search(f.c.store,f.u,'dense',scope=KnowledgeScope('spaces',kb_ids=('kb',)),additional_scope=KnowledgeScope('spaces',kb_ids=('other',)))
    o.check(not r.hits and not r.candidate_budget_exhausted)
@scenario('fetch_over500_budget_true')
def g307(f,o):
    many(f,f.params['count'],f.params['denied']);r=f.c.search(f.u,'dense',limit=5);o.check(not r.hits and r.candidate_budget_exhausted,'safety')
@scenario('fetch_exact500_exhausted_false')
def g308(f,o):
    many(f,f.params['count'],f.params['denied']);r=f.c.search(f.u,'dense',limit=5);o.check(not r.hits and not r.candidate_budget_exhausted)
@scenario('fetch_hybrid_offline_stub_recall')
def g309(f,o):
    ids=many(f,150,135);rows=[VectorHit(doc,1,f.c.store.get_chunks(doc,1)[0].chunk_id,1-i/1000) for i,doc in enumerate(ids)];vector(f,rows)
    r=f.c.search(f.u,'dense',mode='hybrid',limit=5);recall(o,r.hits,ids[-15:]);o.check(f.c.embedder.calls==1)
@scenario('fetch_repeated_candidates_evaluated_once')
def g310(f,o):
    ids=many(f,60,55);rows=[VectorHit(ids[0],1,f.c.store.get_chunks(ids[0],1)[0].chunk_id,1)]*30
    rows.extend(VectorHit(doc,1,f.c.store.get_chunks(doc,1)[0].chunk_id,.9) for doc in ids);vector(f,rows)
    original=f.c.policy_engine.evaluate;calls={}
    def evaluate(*args,**kwargs):
        if len(args)>6 and args[6]==PolicyAction.SEARCH_INDEX:calls[args[3].doc_id]=calls.get(args[3].doc_id,0)+1
        return original(*args,**kwargs)
    with patch.object(f.c.policy_engine,'evaluate',side_effect=evaluate):r=f.c.search(f.u,'dense',mode='hybrid',limit=5)
    recall(o,r.hits,ids[-5:]);o.check(calls and max(calls.values())==1 and len(calls)<=500)
    second=f.c.search(f.u,'dense',mode='hybrid',limit=5);o.check([(h.doc_id,h.score) for h in r.hits]==[(h.doc_id,h.score) for h in second.hits])

class OfflineLayout:
    def parse_layout(self,data,filename=''):
        value=json.loads(data);text=value['text'];box=PdfBBoxSelector(value.get('page',1),.1,.2,.8,.4)
        return LayoutParseResult(text,(ParsedSpan(text,0,len(text),SelectorKind.PDF_BBOX,pdf_bbox=box),),'host-offline-bbox-fixture','1.0')
def pdf(f,text,page=1,**kwargs):
    f.c.parsers.register(['pdf'],OfflineLayout());return f.c.ingest(f.a,'kb',json.dumps({'text':text,'page':page}).encode(),'fixture.pdf',doc_id='doc',**kwargs)
def anchor(f,text='# H\n\nexact body'):
    f.c.ingest(f.a,'kb',text,'fixture.md',doc_id='doc');return f.c.list_anchors(f.a,'doc')[0]
@scenario('anchor_offline_pdf_bbox_policy_mask')
def g401(f,o):
    pdf(f,'SECRET enterprise policy',rights=ResourceRights(redaction_profile='pii'));f.c.redaction_registry.register('pii',RegexRedactionHook([('SECRET','[MASK]')]))
    a=f.c.list_anchors(f.u,'doc')[0];o.check(a.pdf_bbox.page_no==f.case['expected']['page_no'] and a.pdf_bbox.x0==.1 and a.quote.exact==f.case['expected']['masked_quote'])
    o.denied(lambda:f.c.get_anchor(f.u,'doc',a.anchor_id,purpose=Purpose.GROUND_EXTERNAL_LLM),'external_llm_prohibited')
    pdf(f,'SECRET enterprise policy changed',page=2,rights=ResourceRights(redaction_profile='pii'));o.check(f.c.get_anchor(f.u,'doc',a.anchor_id).reanchor_status==ReanchorStatus.DRIFT_PENDING)
@scenario('anchor_csv_negative_detection_limits')
def g402(f,o):
    f.c.ingest(f.a,'kb','compound,activity,units\nA,>10000,nM\nB,inactive,mg/kg\nC,<0.01,nM','assay.csv',doc_id='doc')
    anchors=f.c.list_anchors(f.u,'doc');by={a.table_cell.row_start:a for a in anchors}
    o.check([by[i].quote.exact for i in (1,2,3)]==f.case['expected']['quotes'])
    o.check(by[1].table_cell.cell_ref=='A2:C2' and by[1].table_cell.unit_hint=='nM')
@scenario('anchor_unique_exact_stable_id')
def g403(f,o):
    a=anchor(f);f.c.ingest(f.a,'kb','# H\n\nnew preceding paragraph\n\nexact body','fixture.md',doc_id='doc');b=f.c.get_anchor(f.u,'doc',a.anchor_id)
    o.check(b.version==2 and b.anchor_id==a.anchor_id and b.reanchor_status.value==f.case['expected']['state'] and b.parent_anchor_id==a.anchor_id)
@scenario('anchor_duplicate_pending_no_alias')
def g404(f,o):
    a=anchor(f);f.c.ingest(f.a,'kb','# H\n\nexact body\n\nexact body','fixture.md',doc_id='doc');anchors=f.c.list_anchors(f.u,'doc')
    o.check(len(anchors)==1 and anchors[0].reanchor_status.value==f.case['expected']['state'])
    o.denied(lambda:f.c.reference(f.u,'doc',anchor_id=a.anchor_id),'anchor_drift_pending')
@scenario('anchor_section_move_pending')
def g405(f,o):
    a=anchor(f);f.c.ingest(f.a,'kb','# Different\n\nexact body','fixture.md',doc_id='doc')
    o.check(f.c.get_anchor(f.u,'doc',a.anchor_id).reanchor_status==ReanchorStatus.DRIFT_PENDING)
    o.denied(lambda:f.c.confirm_anchor_reanchor(f.u,'doc',2,a.anchor_id))
@scenario('anchor_table_header_move_pending')
def g406(f,o):
    f.c.ingest(f.a,'kb','name,units\nA,nM','assay.csv',doc_id='doc');a=f.c.list_anchors(f.u,'doc')[0]
    f.c.ingest(f.a,'kb','units,name\nA,nM','assay.csv',doc_id='doc');o.check(f.c.get_anchor(f.u,'doc',a.anchor_id).reanchor_status.value==f.case['expected']['state'])
@scenario('anchor_historic_pin_current_revocation')
def g407(f,o):
    a=anchor(f);ref=f.c.reference(f.u,'doc',1,anchor_id=a.anchor_id)
    f.c.ingest(f.a,'kb','# H\n\nnew preceding paragraph\n\nexact body','fixture.md',doc_id='doc')
    o.check(f.c.consume(f.u,ref).status=='consumed','positive')
    f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));o.check(f.c.consume(f.u,ref).status=='denied','safety')
@scenario('anchor_orphan_unavailable_not_confirmable')
def g408(f,o):
    a=anchor(f);f.c.ingest(f.a,'kb','# H\n\nreplacement','fixture.md',doc_id='doc');b=f.c.get_anchor(f.u,'doc',a.anchor_id)
    o.check(b.reanchor_status.value==f.case['expected']['state']);o.invalid(lambda:f.c.confirm_anchor_reanchor(f.a,'doc',2,a.anchor_id))
    ref=KnowledgeRef('org','doc',2,f.uri(version=2,anchor=a.anchor_id),[],a.quote.exact,a.quote_sha256,anchor_id=a.anchor_id)
    r=f.c.consume(f.u,ref);o.check((r.status,r.reason_code)==('unavailable','anchor_orphaned'))
@scenario('anchor_explicit_confirm_read_write_gate')
def g409(f,o):
    a=anchor(f);f.c.ingest(f.a,'kb','# Moved\n\nexact body','fixture.md',doc_id='doc')
    o.denied(lambda:f.c.confirm_anchor_reanchor(f.u,'doc',2,a.anchor_id));f.c.confirm_anchor_reanchor(f.a,'doc',2,a.anchor_id)
    ref=f.c.reference(f.u,'doc',anchor_id=a.anchor_id);o.check(f.c.consume(f.u,ref).status=='consumed','positive')
@scenario('anchor_forged_quote_hash_rejected')
def g410(f,o):
    a=anchor(f,text='# SECRET\n\nSECRET body');o.invalid(lambda:replace(a,quote_sha256='0'*64))
    f.c.set_document_rights(f.a,'doc',ResourceRights(redaction_profile='mask'));f.c.redaction_registry.register('mask',RegexRedactionHook([('SECRET','[MASK]')]))
    d=f.c.get_anchor(f.u,'doc',a.anchor_id);o.check('SECRET' not in json.dumps(encode(d)) and d.quote_sha256==hashlib.sha256(d.quote.exact.encode()).hexdigest(),'safety')
    out=f.call('verify_citation',source_uri=f.uri(anchor=a.anchor_id),excerpt_hash='0'*64);o.check(not out['valid'] and out['current_status']=='tampered','safety')


def gateway(f,*,secret=None,**kwargs):return GatewayAuthenticator(secret or f.secret,**kwargs)
def headers(f,secret=None,**kwargs):return signed_headers(f.u,secret or f.secret,'POST','/mcp',b'{}',agent=replace(f.agent,allowed_purposes=tuple(Purpose)).to_dict(),**kwargs)
@scenario('mcp_initialize_and_tool_schemas')
def g501(f,o):
    protocol=MCPProtocol(f.c)
    reply=protocol.dispatch({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},f.ctx);o.check(reply['result']['serverInfo']['version']=='1.2.0','positive')
    listed=protocol.dispatch({'jsonrpc':'2.0','id':2,'method':'tools/list'},f.ctx)['result']['tools'];o.check(len(listed)==4)
    for tool in listed:o.check(not set(tool['inputSchema']['properties']).intersection({'actor','agent','purpose','org_id','user_id','self','policy_context'}),'safety')
@scenario('mcp_search_anchor_real_staged_receipt')
def g502(f,o):
    a=anchor(f,text='# H\n\nalpha evidence');hit=f.call('search_evidence',query='alpha',task_id='task-stage')['hits'][0]
    o.check(hit['anchor'] is not None and '#anchor=' in hit['source_uri'],'positive')
    o.check(hit['receipt']['consumer_type']=='mcp_agent' and hit['receipt']['consumer_id']=='gateway-agent' and hit['receipt']['used_by_stage']=='task-stage' and hit['receipt']['excerpt_hash']==hit['excerpt_hash'],'safety')
@scenario('mcp_runtime_identity_fields_rejected')
def g503(f,o):
    f.doc()
    bases={'search_evidence':{'query':'alpha'},'verify_citation':{'source_uri':f.uri()},
           'get_evidence_pack':{'source_uris':[f.uri()]},
           'report_evidence_issue':{'source_uri':f.uri(),'issue_type':'inaccuracy','description':'inert positive control'}}
    for tool in tool_definitions():
        o.check(tool['inputSchema']['additionalProperties'] is False)
        base=bases[tool['name']]
        positive=f.tools.call(tool['name'],base,f.ctx)
        o.check(positive.get('valid',positive.get('status') in ('ok','queued_for_review')),'positive')
        for key in f.case['expected']['identity_fields']:
            # Otherwise-valid arguments: a missing required field cannot
            # accidentally masquerade as successful identity-injection defense.
            o.invalid(lambda:f.tools.call(tool['name'],{**base,key:'admin'},f.ctx),injection=True)
    o.check(o.injection_attempts==f.case['expected']['attempts'] and o.injection_blocked==f.case['expected']['blocked'])
@scenario('mcp_verify_valid_anchor')
def g504(f,o):
    a=anchor(f);ref=f.c.reference(f.u,'doc',anchor_id=a.anchor_id)
    out=f.call('verify_citation',source_uri=ref.source_uri,excerpt_hash=ref.excerpt_hash);o.check(out['valid'] and out['reanchor_status']=='anchored' and out['receipt']['status']=='consumed','positive')
@scenario('mcp_tampered_citation_hash')
def g505(f,o):
    f.doc();out=f.call('verify_citation',source_uri=f.uri(),excerpt_hash='0'*64);o.check(not out['valid'] and out['current_status']=='tampered','safety')
@scenario('mcp_superseded_and_no_latest_oracle')
def g506(f,o):
    f.doc();f.c.ingest(f.a,'kb','alpha updated',doc_id='doc')
    out=f.call('verify_citation',source_uri=f.uri());o.check(not out['valid'] and out['current_status']=='superseded' and out['latest_version']==2)
    f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));denied=f.call('verify_citation',source_uri=f.uri());o.check(denied['current_status']=='denied' and denied['latest_version'] is None,'safety')
@scenario('mcp_pack_subset_intersection_and_exclusion')
def g507(f,o):
    f.doc('alpha SECRET');f.doc('alpha OTHER',id='other');f.doc('HIDDEN TITLE',id='hidden',title='HIDDEN TITLE',acl=DocumentACL(deny_users=('reader',)))
    f.c.redaction_registry.register('p',RegexRedactionHook([('SECRET','[P]')]));f.c.redaction_registry.register('q',RegexRedactionHook([('OTHER','[Q]')]))
    f.c.set_document_rights(f.a,'doc',ResourceRights(redaction_profile='p'));f.c.set_document_rights(f.a,'other',ResourceRights(redaction_profile='q'))
    pack=f.call('get_evidence_pack',source_uris=[f.uri(),f.uri('other'),f.uri('hidden'),f.uri('absent')]);o.check(pack['status']=='ok' and pack['excluded_count']==2 and len(pack['items'])==2,'positive')
    o.check(not any(v in json.dumps(pack) for v in ('HIDDEN TITLE','SECRET','OTHER','absent','hidden')),'safety')
@scenario('mcp_issue_queue_only_snapshot')
def g508(f,o):
    f.doc();tables=('documents','document_versions','chunks','document_acls','evidence_anchors');before={t:f.c.store._execute('SELECT * FROM '+t) for t in tables}
    out=f.call('report_evidence_issue',source_uri=f.uri(),issue_type='inaccuracy',description='<script>data only</script>');issue=f.c.store.get_issue('org',out['issue_id'])
    o.check(out['status']=='queued_for_review' and issue.status=='open' and issue.reported_by_agent_id=='gateway-agent')
    o.check(before=={t:f.c.store._execute('SELECT * FROM '+t) for t in tables},'safety')
@scenario('mcp_production_gateway_401_replay')
def g509(f,o):
    with tempfile.TemporaryDirectory() as directory:
        path=str(Path(directory)/'replay.db');a=gateway(f,replay_store=f.replay_store(path),fallback_secrets=(f.old_secret,));b=gateway(f,replay_store=f.replay_store(path),fallback_secrets=(f.old_secret,))
        o.check(a.authorize_http({},'POST','/mcp',b'{}')[1]==401,'safety')
        h=headers(f,secret=f.old_secret);context,status=a.authorize_http(h,'POST','/mcp',b'{}');o.check(status==200 and context.purpose==Purpose.GROUND_INTERNAL_LLM,'positive')
        o.check(b.authorize_http(h,'POST','/mcp',b'{}')[1]==401,'safety')
        o.check(gateway(f,bound_purpose=Purpose.GROUND_EXTERNAL_LLM).authenticate(headers(f),'POST','/mcp',b'{}').purpose==Purpose.GROUND_EXTERNAL_LLM)
@scenario('mcp_stdio_identity_and_subprocess_roundtrip')
def g510(f,o):
    with tempfile.TemporaryDirectory() as directory:
        path=str(Path(directory)/'fixture.db')
        if f.engine=='postgres':
            from tests.pg_helpers import golden_client
            c=golden_client(f.sandbox.dsn)
        else:c=LocalKnowledgeClient(SQLiteStore(path))
        try:
            k=c.create_kb(f.a,'k',visibility='enterprise');c.ingest(f.a,k.kb_id,'alpha stdio fixture',doc_id='stdio-doc')
        finally:c.store.close()
        env=dict(os.environ)
        for key in ('KNOWLEDGE_MCP_ACTOR_JSON','KNOWLEDGE_MCP_AGENT_JSON','KNOWLEDGE_MCP_PURPOSE'):env.pop(key,None)
        command=[sys.executable,'-S','-W','error::ResourceWarning','-m','knowledge_sdk.mcp','--db',path]
        if f.engine=='postgres':
            command=[sys.executable,'-W','error::ResourceWarning','-m','knowledge_sdk.mcp']
            env['KNOWLEDGE_SDK_DSN']=f.sandbox.dsn
        missing=subprocess.run(command,env=env,input='',capture_output=True,text=True,timeout=15);o.check(missing.returncode!=0 and not missing.stdout,'safety')
        env['KNOWLEDGE_MCP_ACTOR_JSON']=json.dumps(f.u.__dict__)
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'search_evidence','arguments':{'query':'alpha'}}}]
        result=subprocess.run(command,env=env,input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,timeout=15)
        o.check(result.returncode==0 and 'ResourceWarning:' not in result.stderr,'positive');out=[json.loads(line) for line in result.stdout.splitlines()]
        o.check(out[1]['result']['structuredContent']['hits'][0]['receipt']['consumer_id']=='mcp_stdio','positive')


from .g6 import register_g6
register_g6(scenario)


def load_cases(path=None):
    path=Path(path) if path else Path(__file__).with_name('golden_cases_v2.jsonl')
    cases=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    expected_groups={'G1':20,'G2':10,'G3':10,'G4':10,'G5':10}
    if len(cases)==75:expected_groups['G6']=15
    groups={group:sum(c['group']==group for c in cases) for group in expected_groups}
    if len(cases) not in (60,75) or groups!=expected_groups:raise ValueError('Golden cardinality/group gate failed')
    if len({c['case_id'] for c in cases})!=len(cases) or len({c['scenario'] for c in cases})!=len(cases) or not {c['scenario'] for c in cases}<=set(SCENARIOS):raise ValueError('Cases must have distinct executable scenarios')
    if len(cases)==75 and {c['scenario'] for c in cases}!=set(SCENARIOS):raise ValueError('Missing executable G6 scenarios')
    for case in cases:
        if set(case)!={'case_id','group','title','scenario','expected'} or not isinstance(case['expected'],dict):raise ValueError('Invalid golden schema')
    expected_ids={g+'-'+str(i).zfill(2) for g,n in expected_groups.items() for i in range(1,n+1)}
    if {c['case_id'] for c in cases}!=expected_ids:raise ValueError('Unexpected golden case IDs')
    return cases


def run_suite(path=None,verbose=False,engine='sqlite'):
    cases=load_cases(path);results=[]
    for case in cases:
        observation=Observation(case['expected']);fixture=Fixture(case,engine);error=None
        try:SCENARIOS[case['scenario']](fixture,observation)
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        finally:fixture.close()
        result={'case_id':case['case_id'],'group':case['group'],'scenario':case['scenario'],'status':'passed' if error is None else 'failed','error':error,**{k:v for k,v in observation.__dict__.items() if not k.startswith('_')}}
        results.append(result)
        if verbose:print(case['case_id'],result['status'],case['scenario'],error or '',flush=True)
    passed=sum(r['status']=='passed' for r in results);by_group={g:{'passed':sum(r['status']=='passed' for r in results if r['group']==g),'total':sum(r['group']==g for r in results)} for g in dict.fromkeys(c['group'] for c in cases)}
    ratio=lambda n,d:{'numerator':n,'denominator':d,'rate':n/d if d else None}
    attempts=sum(r['injection_attempts'] for r in results);blocked=sum(r['injection_blocked'] for r in results);recalls=[r['recall'] for r in results if r['recall'] is not None]
    audit_checks=sum(r['audit_checks'] for r in results);audit_detected=sum(r['audit_detected'] for r in results)
    impact_expected=sum(r['impact_expected'] for r in results);impact_found=sum(r['impact_found'] for r in results)
    impact_unexpected=sum(r['impact_unexpected'] for r in results)
    g6_gate=(len(cases)==60 or (by_group['G6']['passed']==15 and audit_checks>0 and audit_detected==audit_checks and impact_expected>0 and impact_found==impact_expected and impact_unexpected==0))
    hard_gate=(passed==len(cases) and g6_gate and sum(r['safety_failures'] for r in results)==0 and sum(r['positive_failures'] for r in results)==0
               and sum(r['model_calls'] for r in results)==0 and attempts==36 and blocked==36 and len(recalls)==7 and all(v==1.0 for v in recalls))
    return {'gate_passed':hard_gate,'case_count':len(cases),'passed':passed,'failed':len(cases)-passed,'skipped':0,'groups':by_group,
      'audit_chain_detection':ratio(audit_detected,audit_checks),'impact_completeness':ratio(impact_found,impact_expected),'unexpected_impact_targets':impact_unexpected,
      'acl_violation_rate':ratio(sum(r['safety_failures'] for r in results if r['group']=='G1'),20),
      'refusal_accuracy':ratio(by_group['G2']['passed'],10),'reanchor_accuracy':ratio(by_group['G4']['passed'],10),
      'mcp_injection_blocked':ratio(blocked,attempts),'implicit_model_calls':sum(r['model_calls'] for r in results),
      'mcp_pass_rate':ratio(by_group['G5']['passed'],10),'positive_control_failures':sum(r['positive_failures'] for r in results),'security_assertion_failures':sum(r['safety_failures'] for r in results),
      'offline_recall_at_requested_k':{'eligible_cases':len(recalls),'mean':sum(recalls)/len(recalls) if recalls else None,'values':recalls},'results':results}


# Retain the entire original 75-case registry, loader, assertions and suite.
# New groups use a separate registry and do not weaken any legacy hard gate.
run_legacy_suite=run_suite

def run_suite(path=None,verbose=False,engine='sqlite'):
    if path is not None:return run_legacy_suite(path,verbose,engine)
    from .g7_g8 import SCENARIOS as enterprise
    result=run_legacy_suite(None,verbose,engine)
    cases=[json.loads(line) for line in Path(__file__).with_name('golden_cases_v3_enterprise.jsonl').read_text().splitlines() if line.strip()]
    if len(cases)!=25 or {c['scenario'] for c in cases}!=set(enterprise) or {g:sum(c['group']==g for c in cases) for g in ('G7','G8')}!={'G7':15,'G8':10}:raise ValueError('Enterprise cardinality gate failed')
    for case in cases:
        observation=Observation(case['expected']);fixture=Fixture(case,engine);error=None
        try:enterprise[case['scenario']](fixture,observation)
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        finally:fixture.close()
        row={'case_id':case['case_id'],'group':case['group'],'scenario':case['scenario'],'status':'passed' if error is None else 'failed','error':error,**{k:v for k,v in observation.__dict__.items() if not k.startswith('_')}}
        result['results'].append(row)
        if verbose:print(case['case_id'],row['status'],row['scenario'],error or '',flush=True)
    extra=result['results'][75:]
    for group in ('G7','G8'):result['groups'][group]={'total':sum(r['group']==group for r in extra),'passed':sum(r['group']==group and r['status']=='passed' for r in extra)}
    result['case_count']=100;result['passed']+=sum(r['status']=='passed' for r in extra);result['failed']=100-result['passed']
    for field,key in (('security_assertion_failures','safety_failures'),('positive_control_failures','positive_failures'),('implicit_model_calls','model_calls')):result[field]+=sum(r[key] for r in extra)
    result['gate_passed']=result['gate_passed'] and result['passed']==100 and result['security_assertion_failures']==0 and result['implicit_model_calls']==0
    return result


run_legacy100_suite=run_suite

def run_suite(path=None,verbose=False,engine='sqlite',legacy100=False):
    result=run_legacy100_suite(path,verbose,engine)
    if path is not None or legacy100:return result
    from .g9 import SCENARIOS as runtime
    cases=[json.loads(line) for line in Path(__file__).with_name('golden_cases_v4_runtime.jsonl').read_text().splitlines() if line.strip()]
    if len(cases)!=15 or {c['case_id'] for c in cases}!={'G9-'+str(i).zfill(2) for i in range(1,16)} or {c['scenario'] for c in cases}!=set(runtime):raise ValueError('Runtime cardinality gate failed')
    for case in cases:
        observation=Observation(case['expected']);fixture=Fixture(case,engine);error=None
        try:runtime[case['scenario']](fixture,observation)
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        finally:fixture.close()
        row={'case_id':case['case_id'],'group':'G9','scenario':case['scenario'],'status':'passed' if error is None else 'failed','error':error,**{k:v for k,v in observation.__dict__.items() if not k.startswith('_')}}
        result['results'].append(row)
        if verbose:print(case['case_id'],row['status'],row['scenario'],error or '',flush=True)
    extra=result['results'][100:];count=sum(r['status']=='passed' for r in extra)
    result['groups']['G9']={'total':15,'passed':count};result['case_count']=115;result['passed']+=count;result['failed']=115-result['passed']
    for field,key in (('security_assertion_failures','safety_failures'),('positive_control_failures','positive_failures'),('implicit_model_calls','model_calls')):result[field]+=sum(r[key] for r in extra)
    result['gate_passed']=result['gate_passed'] and result['passed']==115 and result['security_assertion_failures']==0 and result['implicit_model_calls']==0
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json',action='store_true');parser.add_argument('--cases');parser.add_argument('--legacy75',action='store_true');parser.add_argument('--legacy100',action='store_true');parser.add_argument('--json-output');parser.add_argument('--report');parser.add_argument('--engine',choices=('sqlite','postgres'),default='sqlite');args=parser.parse_args()
    result=run_suite(str(Path(__file__).with_name('golden_cases_v2.jsonl')) if args.legacy75 else args.cases,not args.json,args.engine,legacy100=args.legacy100);result['engine']=args.engine
    result['executed_at']=datetime.now(timezone(timedelta(hours=8))).isoformat();result['timezone']='Asia/Shanghai'
    if args.json_output:Path(args.json_output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    if args.report:
        lines=['# Q2-M4 golden benchmark ('+args.engine+')','',result['executed_at']+' Asia/Shanghai','',f"Cases: {result['passed']}/{result['case_count']} passed; 0 skipped; gate_passed={result['gate_passed']}",'', '| Group | Passed / Total |','|---|---|']
        lines.extend('| '+g+' | '+str(v['passed'])+' / '+str(v['total'])+' |' for g,v in result['groups'].items())
        lines.extend(['','```json',json.dumps({k:v for k,v in result.items() if k!='results'},indent=2),'```','',
         f"These are {result['case_count']} distinct executable scenarios. Original 75 assertions are unchanged; no skips are allowed.",
         'ACL denominator: 20 G1 security scenarios; refusal denominator: 10 G2 no-evidence scenarios with real generator spies; anchor denominator: 10 G4 fixture scenarios.',
         'MCP injection denominator: actual runtime rejected argument/purpose attempts (not tool schema declarations). Positive controls and safety assertions are tracked separately.',
         'implicit_model_calls is the measured generator-spy invocation count in G1 missing-hook ask and G2; no remote model or embedding service is configured. PostgreSQL mode uses real local PG/pgvector fixtures; deterministic adversarial vector stubs are retained. Positive answer control uses the local extractive generator.',
         'Recall@k (k=3 for the three-target scope fixture, otherwise5) is measured only on the seven eligible selected-engine keyword / deterministic hybrid-stub fixtures. Two deliberate 500-cap negative fixtures are excluded. No online semantic improvement or historical baseline uplift is claimed.',
         'PDF geometry is a host-injected offline layout fixture, not a PDF/OCR parser. Handler golden checks are not HTTP/stdio wire acceptance; actual transports are separately exercised at L3.',''])
        Path(args.report).write_text('\n'.join(lines))
    print(json.dumps(result if args.json else {k:v for k,v in result.items() if k!='results'},ensure_ascii=False,indent=2))
    return 0 if result['gate_passed'] and result['implicit_model_calls']==0 and result['security_assertion_failures']==0 else 1

if __name__=='__main__':raise SystemExit(main())
