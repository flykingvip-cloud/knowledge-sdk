"""Atomic batch application. Cursors are committed with authority and events."""
from __future__ import annotations
from abc import ABC,abstractmethod
from dataclasses import replace
import hashlib
from ..contracts.connectors import ConnectorSyncBatch,ConnectorSyncReport
from ..contracts.identity import ConnectorSyncState
from ..contracts.models import DocumentACL
from ..contracts.policy import PolicyAction,ResourceRights,Purpose
from ..exceptions import PermissionDeniedError,ValidationError,NotFoundError,ConflictError
from ..governance.workflow import now

class BaseConnector(ABC):
    connector_id: str
    org_id: str
    @abstractmethod
    def sync_since(self,cursor,*,org_id,kb_id)->ConnectorSyncBatch:...


class ConnectorSyncRunner:
    def __init__(self,client):self.client=client;self.store=client.store
    def plan_sync(self,actor,connector,*,org_id,kb_id,webhook=None,batch=None,agent=None,purpose=Purpose.READ,policy_context=None):
        from .planning import decisions,authorize
        from .filesystem import ControlledFilesystemConnector
        from .webhook_sync import WebhookSyncConnector
        c=self.client;s=self.store
        with c._lock,s.runtime_transaction():
            c._check_principal(actor)
            if actor.org_id!=org_id or connector.org_id!=org_id:raise PermissionDeniedError('connector_tenant_mismatch')
            if not set(actor.org_roles)&{'admin','manage_org','connector_admin'}:raise PermissionDeniedError('connector_admin_required')
            ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
            authorize(c,actor,s.get_kb(kb_id),**ctx)
            state=s.get_connector_sync_state(org_id,connector.connector_id);cursor=state.cursor if state else ''
            if batch is not None and webhook is not None:raise ValidationError('Choose batch or webhook')
            if batch is None:
                if type(connector) is ControlledFilesystemConnector and webhook is None:
                    batch=ControlledFilesystemConnector.sync_since(connector,cursor,org_id=org_id,kb_id=kb_id)
                elif type(connector) is WebhookSyncConnector:
                    batch=WebhookSyncConnector.batch_from_webhook(connector,*webhook,cursor=cursor,org_id=org_id,kb_id=kb_id) if webhook else ConnectorSyncBatch(next_cursor=cursor)
                else:raise ValidationError('Planning custom connectors requires an explicit immutable batch; sync_since is never invoked')
            return decisions(c,actor,connector,org_id,kb_id,batch,**ctx)

    def run_once(self,actor,connector,*,org_id,kb_id,webhook=None):
        c=self.client;s=self.store
        try:
            c._check_principal(actor)
            if actor.org_id!=org_id or connector.org_id!=org_id:raise PermissionDeniedError('connector_tenant_mismatch')
            if not set(actor.org_roles)&{'admin','manage_org','connector_admin'}:raise PermissionDeniedError('connector_admin_required')
            decision=c.evaluate_policy(actor,kb_id=kb_id,action=PolicyAction.MANAGE_SPACE)
            if not decision.allowed:raise PermissionDeniedError(decision.reason_code)
            with c._lock,s.runtime_transaction():
                c._check_principal(actor)
                s.lock_connector(org_id,connector.connector_id)
                state=s.get_connector_sync_state(org_id,connector.connector_id)
                cursor=state.cursor if state else ''
                batch=connector.batch_from_webhook(*webhook,cursor=cursor,org_id=org_id,kb_id=kb_id) if webhook else connector.sync_since(cursor,org_id=org_id,kb_id=kb_id)
                if not isinstance(batch,ConnectorSyncBatch):raise ValidationError('Invalid connector result')
                from .planning import decisions
                from ..permissions.engine import DefaultPolicyEngine
                if type(c.policy_engine.delegate) is DefaultPolicyEngine:decisions(c,actor,connector,org_id,kb_id,batch)
                counts=[0,0,0];events=0;before=s.count_outbox_events(org_id)
                def source(item,missing=False):
                    try:d=s.get_document(item.doc_id)
                    except NotFoundError:
                        if missing:return None
                        raise
                    if d.org_id!=org_id or d.kb_id!=kb_id or d.metadata.get('_connector_id')!=connector.connector_id or d.metadata.get('_external_id')!=item.external_id:raise PermissionDeniedError('connector_source_mismatch')
                    return d
                for item in batch.upserts:
                    if item.kb_id!=kb_id or item.governance_tier!=s.get_kb(kb_id).governance_tier:raise PermissionDeniedError('connector_space_mismatch')
                    raw=item.content.encode() if isinstance(item.content,str) else item.content
                    sha=hashlib.sha256(raw).hexdigest()
                    if item.source_sha256 and item.source_sha256!=sha:raise ValidationError('Source digest mismatch')
                    d=source(item,True)
                    unchanged=d is not None and d.metadata.get('_source_sha256')==sha and not d.archived and d.lifecycle_state!='revoked'
                    acl=DocumentACL(**dict(item.acl)) if item.acl is not None else None
                    if unchanged:
                        if acl is not None and acl!=s.get_acl(d.doc_id):c.set_document_acl(actor,d.doc_id,acl);counts[1]+=1;events+=1
                        if item.rights is not None and item.rights!=d.rights:c.set_document_rights(actor,d.doc_id,item.rights);counts[1]+=1;events+=1
                        continue
                    metadata=dict(item.metadata);metadata.update(_connector_id=connector.connector_id,_external_id=item.external_id,_source_sha256=sha)
                    c.ingest(actor,kb_id,item.content,filename=item.filename,title=item.title or item.filename,doc_id=item.doc_id,metadata=metadata,acl=acl,rights=item.rights,valid_from=item.valid_from,valid_to=item.valid_to)
                    counts[0]+=1;events+=1
                for item in batch.acl_updates:
                    d=source(item)
                    if item.acl is not None:
                        acl=DocumentACL(**dict(item.acl))
                        if acl!=s.get_acl(d.doc_id):c.set_document_acl(actor,d.doc_id,acl);counts[1]+=1;events+=1
                    if item.rights is not None and item.rights!=d.rights:c.set_document_rights(actor,d.doc_id,item.rights);counts[1]+=1;events+=1
                for item in batch.tombstones:
                    d=source(item)
                    if item.action=='archive':
                        if d.archived:continue
                        c.archive(actor,d.doc_id)
                    else:
                        if d.rights is not None and d.rights.revoked:continue
                        c.set_document_rights(actor,d.doc_id,replace(d.rights or ResourceRights(),revoked=True))
                        # The public rights API already atomically emits doc.revoked.
                    counts[2]+=1;events+=1
                s.put_connector_sync_state(ConnectorSyncState(org_id,connector.connector_id,batch.next_cursor,now()))
                c._audit_operation(actor,'connector.sync',{},None)
                return ConnectorSyncReport(connector.connector_id,org_id,*counts,s.count_outbox_events(org_id)-before,cursor,batch.next_cursor)
        except PermissionDeniedError:
            c._audit_operation(actor,'connector.sync',{},None,denied=True);raise
