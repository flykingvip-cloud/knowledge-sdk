"""Fifteen independent executable runtime scenarios. No substitutions for G1-G8."""
from __future__ import annotations
from dataclasses import replace
from knowledge_sdk import (Actor,Purpose,ContextBudget,DocumentACL,ResourceRights,
                           PermissionDeniedError,ConflictError,KnowledgeScope,ReanchorStatus)
from knowledge_sdk.server.scim import SCIMService
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.mcp import GatewayContext,EvidenceTools

SCENARIOS={}
def case(n):
    def decorate(fn):SCENARIOS['runtime_'+str(n).zfill(2)]=fn;return fn
    return decorate

def setup(f,**profile):
    f.doc('alpha evidence original',filename='fixture.md')
    f.c.register_agent_profile(f.a,f.agent.agent_id,**profile)
    task=f.c.create_task_context(f.u,f.agent.agent_id,purpose=f.ctx.purpose)
    snap=f.c.create_context_snapshot(f.u,task.task_id,[{'doc_id':'doc'}])
    return task,snap

def deny(f,o,task,snapshot):
    o.denied(lambda:f.c.read_task_snapshot(f.u,task.task_id,snapshot.snapshot_id))
    o.check(f.c.store.get_task_context('org',task.task_id).status=='revoked','safety')
    o.check(bool(f.c.store.list_task_revocations('org',task.task_id)),'positive')
    o.check(any(e.decision_effect.value=='deny' for e in f.c.store.list_audit_events('org',actor_id=f.u.user_id)),'positive')

@case(1)
def profile_purpose(f,o):
    f.c.register_agent_profile(f.a,f.agent.agent_id,allowed_kb_ids=('other',))
    o.denied(lambda:f.c.create_task_context(f.u,f.agent.agent_id,purpose=Purpose.GROUND_EXTERNAL_LLM))
    f.doc();t=f.c.create_task_context(f.u,f.agent.agent_id)
    o.check(not f.c.create_context_snapshot(f.u,t.task_id,[{'doc_id':'doc'}]).items,'safety')

@case(2)
def budget(f,o):
    f.doc('alpha evidence original');f.doc('alpha second',id='doc2')
    b=ContextBudget(1,2,8,10,30);f.c.register_agent_profile(f.a,f.agent.agent_id,default_budget=b)
    t=f.c.create_task_context(f.u,f.agent.agent_id,budget=ContextBudget(100,100,100,10000,500),ttl_seconds=800)
    o.check(t.budget==b,'positive')
    s=f.c.create_context_snapshot(f.u,t.task_id,[{'doc_id':'doc'},{'doc_id':'doc2'},{'doc_id':'doc'}])
    o.check(s.total_chars==10 and len({i.doc_id for i in s.items})==1 and s.items[0].text=='alpha ev','positive')

@case(3)
def clearance(f,o):
    f.doc(acl=DocumentACL(access_level='role_clearance',required_clearance='confidential'))
    f.c.register_agent_profile(f.a,f.agent.agent_id,max_clearance_level='internal')
    a=replace(f.u,clearance_level='restricted');t=f.c.create_task_context(a,f.agent.agent_id)
    o.check(not f.c.create_context_snapshot(a,t.task_id,[{'doc_id':'doc'}]).items,'safety')

@case(4)
def immutable_oldversion(f,o):
    t,s=setup(f);f.c.ingest(f.a,'kb','alpha evidence revised',doc_id='doc')
    got=f.c.read_task_snapshot(f.u,t.task_id,s.snapshot_id)
    o.check(got==s and got.items[0].version==1 and got.items[0].text=='alpha evidence original','positive')
    f.c.drain_outbox(f.a)
    o.check(any(a.target_type=='task_context' and a.impact_reason.value=='superseded' for a in f.c.list_impact_alerts(f.u)),'positive')

@case(5)
def revoked(f,o):
    t,s=setup(f);f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));deny(f,o,t,s)
@case(6)
def archived(f,o):
    t,s=setup(f);f.c.archive(f.a,'doc');deny(f,o,t,s)
@case(7)
def acl(f,o):
    t,s=setup(f);f.c.set_document_acl(f.a,'doc',DocumentACL(deny_users=['reader']));deny(f,o,t,s)
@case(8)
def anchor(f,o):
    f.doc('# H\n\nalpha evidence',filename='fixture.md');f.c.register_agent_profile(f.a,f.agent.agent_id)
    for status in (ReanchorStatus.DRIFT_PENDING,ReanchorStatus.ORPHANED):
        anchors=f.c.store.get_anchors('org','doc',1);a=anchors[0]
        f.c.store.update_anchor(replace(a,reanchor_status=ReanchorStatus.ANCHORED))
        t=f.c.create_task_context(f.u,f.agent.agent_id);s=f.c.create_context_snapshot(f.u,t.task_id,[{'doc_id':'doc','anchor_id':a.anchor_id}])
        o.check(bool(s.items),'positive');f.c.store.update_anchor(replace(a,reanchor_status=status));deny(f,o,t,s)
@case(9)
def scim(f,o):
    f.c.store.upsert_principal(IdentityPrincipal('org','reader'))
    f.u=replace(f.u,policy_generation='1');f.ctx=replace(f.ctx,actor=f.u)
    t,s=setup(f);SCIMService(f.c).patch(f.a,'reader',{'Operations':[{'op':'replace','path':'department_ids','value':['new']}]});deny(f,o,t,s)
@case(10)
def profile_disable(f,o):
    t,s=setup(f);f.c.update_agent_profile(f.a,f.agent.agent_id,active=False);deny(f,o,t,s)
@case(11)
def proactive(f,o):
    t,s=setup(f);f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True))
    o.check(f.c.store.get_task_context('org',t.task_id).status=='revoked','positive')
    f.c.drain_outbox(f.a)
    records=f.c.store.list_task_revocations('org',t.task_id);alerts=f.c.store.list_impact_alerts('org',target_id=t.task_id)
    o.check(records and records[0].trigger_event_id and len(alerts)==1 and alerts[0].target_type=='task_context' and 'alpha evidence' not in alerts[0].summary,'safety')
    o.check(f.c.store.get_context_snapshot('org',s.snapshot_id).status=='revoked','positive')
@case(12)
def mcp(f,o):
    t,s=setup(f);f.c.archive(f.a,'doc')
    for name,args in [('search_evidence',{'query':'alpha'}),('verify_citation',{'source_uri':f.uri()}),('get_evidence_pack',{'source_uris':[f.uri()]})]:
        o.denied(lambda:EvidenceTools(f.c).call(name,dict(args,task_id=t.task_id,snapshot_id=s.snapshot_id),f.ctx))
@case(13)
def ownership(f,o):
    t,s=setup(f)
    messages=[]
    for a,tid in [(Actor('other','org'),t.task_id),(Actor('reader','other'),t.task_id),(f.u,'unknown')]:
        try:f.c.read_task_snapshot(a,tid,s.snapshot_id)
        except PermissionDeniedError as e:messages.append(str(e))
    o.check(messages==['runtime_resource_unavailable']*3,'safety')
@case(14)
def seal(f,o):
    t,s=setup(f);store=f.c.store
    with store.transaction():
        if f.engine=='postgres':
            with store.tenant_scope('org'):store._execute('UPDATE context_snapshots SET snapshot_sha256=%s WHERE snapshot_id=%s',('0'*64,s.snapshot_id))
        else:store._execute('UPDATE context_snapshots SET snapshot_sha256=? WHERE snapshot_id=?',('0'*64,s.snapshot_id))
    try:f.c.read_task_snapshot(f.u,t.task_id,s.snapshot_id)
    except ConflictError:return
    o.check(False,'safety')
@case(15)
def terminal(f,o):
    f.c.register_agent_profile(f.a,f.agent.agent_id)
    expired=f.c.create_task_context(f.u,f.agent.agent_id,ttl_seconds=0)
    o.denied(lambda:f.c.create_context_snapshot(f.u,expired.task_id,[]))
    t=f.c.create_task_context(f.u,f.agent.agent_id);f.c.complete_task_context(f.u,t.task_id)
    o.denied(lambda:f.c.create_context_snapshot(f.u,t.task_id,[]))
