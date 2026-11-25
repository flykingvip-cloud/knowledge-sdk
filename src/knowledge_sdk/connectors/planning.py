"""Read-only preflight shared by plan and commit. Never run-sync-then-rollback."""
from __future__ import annotations
from dataclasses import replace
import hashlib
from ..contracts.models import Document,DocumentACL
from ..contracts.policy import PolicyAction,ResourceRights,Purpose
from ..contracts.connectors import ConnectorSyncBatch
from ..permissions.engine import DefaultPolicyEngine
from ..exceptions import PermissionDeniedError,ValidationError,NotFoundError


def authorize(c,actor,kb,document=None,acl=None,action=PolicyAction.MANAGE_SPACE,*,agent=None,purpose=Purpose.READ,policy_context=None):
    # Planning cannot invoke arbitrary third-party side-effectful policy callbacks.
    engine=c.policy_engine.delegate
    if type(engine) is not DefaultPolicyEngine:raise ValidationError('Read-only planning requires the standard pure policy engine')
    if engine.principal_store is not None:
        from ..permissions.identity import check_principal
        check_principal(engine.principal_store,actor,required=engine.require_principal)
    # The pure clone retains every policy rule but cannot append delegate DENY
    # audit events. Identity checks above are read-only, including rejected plans.
    engine=DefaultPolicyEngine(engine.rules)
    decision=engine.evaluate(actor,agent,kb,document,acl,c.store.member_role(kb.kb_id,actor.user_id),action,purpose,policy_context)
    if not decision.allowed:raise PermissionDeniedError('connector_access_denied')


def decisions(c,actor,connector,org_id,kb_id,batch,*,agent=None,purpose=Purpose.READ,policy_context=None):
    s=c.store
    if not isinstance(batch,ConnectorSyncBatch):raise ValidationError('Invalid connector result')
    kb=s.get_kb(kb_id)
    from functools import partial
    auth=partial(authorize,c,actor,kb,agent=agent,purpose=purpose,policy_context=policy_context)
    auth()
    documents={};acls={};upserts=[];tombstones=[];unchanged=0
    def source(item,missing=False):
        if item.doc_id not in documents:
            try:d=s.get_document(item.doc_id)
            except NotFoundError:
                if not missing:raise
                d=None
            documents[item.doc_id]=d
        d=documents[item.doc_id]
        if d is not None:
            if d.org_id!=org_id or d.kb_id!=kb_id or d.metadata.get('_connector_id')!=connector.connector_id or d.metadata.get('_external_id')!=item.external_id:raise PermissionDeniedError('connector_source_mismatch')
            if item.doc_id not in acls:acls[item.doc_id]=s.get_acl(item.doc_id)
        elif not missing:raise NotFoundError('Resource not found')
        return d
    def acl_change(item,d):
        changed=False
        if item.acl is not None:
            acl=DocumentACL(**dict(item.acl))
            if acl!=acls[item.doc_id]:
                auth(d,acls[item.doc_id]);acls[item.doc_id]=acl;changed=True
        if item.rights is not None and item.rights!=d.rights:
            auth(d,acls[item.doc_id]);d=replace(d,rights=item.rights);documents[item.doc_id]=d;changed=True
        return changed
    for item in batch.upserts:
        if item.kb_id!=kb_id or item.governance_tier!=kb.governance_tier:raise PermissionDeniedError('connector_space_mismatch')
        raw=item.content.encode() if isinstance(item.content,str) else item.content;sha=hashlib.sha256(raw).hexdigest()
        if item.source_sha256 and item.source_sha256!=sha:raise ValidationError('Source digest mismatch')
        d=source(item,True)
        same=d is not None and d.metadata.get('_source_sha256')==sha and not d.archived and d.lifecycle_state!='revoked'
        if same:
            if acl_change(item,d):upserts.append(dict(external_id=item.external_id,doc_id=item.doc_id,content_hash=sha,operation='policy_update'))
            else:unchanged+=1
            continue
        if len(raw)>32*1024*1024 or not c.parsers.parse_layout(raw,item.filename).full_text.strip():raise ValidationError('Invalid source content')
        if d is not None:
            auth(d,acls[item.doc_id],PolicyAction.WRITE_DOCUMENT)
            if kb.governance_tier!='l2_controlled':auth(d,acls[item.doc_id],PolicyAction.READ_CONTENT)
        else:
            identity=Document(item.doc_id,org_id,kb_id,actor.user_id,'',kb.visibility)
            auth(identity,DocumentACL(**dict(item.acl)) if item.acl is not None else None,PolicyAction.WRITE_DOCUMENT)
        metadata=dict(item.metadata);metadata.update(_connector_id=connector.connector_id,_external_id=item.external_id,_source_sha256=sha)
        d=replace(d,metadata=metadata,rights=item.rights if item.rights is not None else d.rights) if d else Document(item.doc_id,org_id,kb_id,actor.user_id,item.title or item.filename,kb.visibility,metadata=metadata,rights=item.rights)
        documents[item.doc_id]=d;acls[item.doc_id]=DocumentACL(**dict(item.acl)) if item.acl is not None else acls.get(item.doc_id,DocumentACL())
        upserts.append(dict(external_id=item.external_id,doc_id=item.doc_id,content_hash=sha,operation='upsert'))
    for item in batch.acl_updates:
        d=source(item)
        if acl_change(item,d):upserts.append(dict(external_id=item.external_id,doc_id=item.doc_id,operation='policy_update'))
        else:unchanged+=1
    for item in batch.tombstones:
        d=source(item)
        if (item.action=='archive' and d.archived) or (item.action=='revoke' and d.rights is not None and d.rights.revoked):unchanged+=1;continue
        auth(d,acls[item.doc_id],PolicyAction.WRITE_DOCUMENT if item.action=='archive' else PolicyAction.MANAGE_SPACE)
        documents[item.doc_id]=replace(d,archived=True) if item.action=='archive' else replace(d,rights=replace(d.rights or ResourceRights(),revoked=True))
        tombstones.append(dict(external_id=item.external_id,doc_id=item.doc_id,action=item.action,reason=item.reason))
    return dict(to_upsert=upserts,to_tombstone=tombstones,unchanged_count=unchanged)
