"""Reference 2: signed, timestamp-bound Wiki/DMS deltas and persisted event IDs.

No outbound SaaS client. A normalized envelope is verified before parsing and
applied together with its deduplication cursor; retries after rollback are safe.
"""
from __future__ import annotations
import json,hmac,hashlib,time
from ..contracts.connectors import ConnectorDocument,ConnectorACLUpdate,TombstoneRecord,ConnectorSyncBatch
from ..exceptions import ValidationError,PermissionDeniedError
from .base import BaseConnector


def sign_sync(secret,body,event_id,timestamp):
    return 'sha256='+hmac.new(secret.encode(),(str(timestamp)+'.'+event_id+'.').encode()+body,hashlib.sha256).hexdigest()

class WebhookSyncConnector(BaseConnector):
    def __init__(self,connector_id,secret,*,org_id,clock=time.time,tolerance_seconds=300):
        if not isinstance(secret,str) or len(secret)<32 or not 1<=tolerance_seconds<=600:raise ValidationError('Invalid webhook configuration')
        self.connector_id=connector_id;self.org_id=org_id;self._secret=secret;self.clock=clock;self.tolerance=tolerance_seconds
    def sync_since(self,cursor,*,org_id,kb_id):
        if org_id!=self.org_id:raise PermissionDeniedError('connector_tenant_mismatch')
        return ConnectorSyncBatch(next_cursor=cursor)
    def batch_from_webhook(self,body,headers,*,cursor,org_id,kb_id):
        if org_id!=self.org_id:raise PermissionDeniedError('connector_tenant_mismatch')
        if not isinstance(body,bytes) or len(body)>16*1024*1024:raise ValidationError('Invalid webhook body')
        headers={k.lower():v for k,v in headers.items()}
        event=headers.get('x-kb-event-id','');stamp=headers.get('x-kb-webhook-timestamp','');sig=headers.get('x-kb-webhook-signature','')
        try:
            if not event or len(event)>256 or not stamp.isdigit() or abs(self.clock()-int(stamp))>self.tolerance:raise ValueError()
            if not hmac.compare_digest(sign_sync(self._secret,body,event,stamp),sig):raise ValueError()
        except (TypeError,ValueError):raise PermissionDeniedError('Invalid connector signature') from None
        try:seen=json.loads(cursor) if cursor else {};data=json.loads(body)
        except (ValueError,UnicodeError):raise ValidationError('Invalid connector payload')
        digest=hashlib.sha256(body).hexdigest()
        if event in seen:
            if seen[event]!=digest:raise ValidationError('Conflicting webhook event')
            return ConnectorSyncBatch(next_cursor=cursor)
        if not isinstance(data,dict) or set(data)-{'org_id','kb_id','upserts','acl_updates','tombstones'}:raise ValidationError('Invalid connector envelope')
        if data.get('org_id',org_id)!=org_id or data.get('kb_id',kb_id)!=kb_id:raise PermissionDeniedError('connector_tenant_mismatch')
        try:
            upserts=tuple(ConnectorDocument(**dict(item,kb_id=item.get('kb_id',kb_id))) for item in data.get('upserts',[]))
            acls=tuple(ConnectorACLUpdate(**item) for item in data.get('acl_updates',[]))
            tombstones=tuple(TombstoneRecord(**item) for item in data.get('tombstones',[]))
        except (TypeError,KeyError):raise ValidationError('Invalid connector delta') from None
        seen[event]=digest
        # Fail closed instead of evicting dedupe keys and allowing old events again.
        if len(seen)>100000:raise ValidationError('Connector dedupe capacity exhausted; rotate source stream')
        return ConnectorSyncBatch(upserts,acls,tombstones,json.dumps(seen,sort_keys=True,separators=(',',':')))
