"""Current (not historical) space presentation metadata in the existing JSON row.

No new table/column, no metadata snapshot, no alternative security authority.
Legacy model/wire output remains exactly its original field set.
"""
from __future__ import annotations
import json
from contextlib import nullcontext
from ..exceptions import PermissionDeniedError,NotFoundError

KEY='_v2_space'


def current(store,org_id,kb_id):
    pg=hasattr(store,'_pg')
    with store.tenant_scope(org_id) if pg else store.transaction():
        rows=store._execute('SELECT data FROM knowledge_bases WHERE org_id='+('%s' if pg else '?')+' AND kb_id='+('%s' if pg else '?'),(org_id,kb_id))
        if not rows:raise NotFoundError('RESOURCE_NOT_FOUND')
        return json.loads(rows[0][0]).get(KEY,{})


def set_current(store,org_id,kb_id,fields):
    pg=hasattr(store,'_pg')
    with store.tenant_scope(org_id) if pg else store.transaction():
        rows=store._execute('SELECT data FROM knowledge_bases WHERE org_id='+('%s' if pg else '?')+' AND kb_id='+('%s' if pg else '?'),(org_id,kb_id))
        if not rows:raise NotFoundError('RESOURCE_NOT_FOUND')
        raw=json.loads(rows[0][0]);raw[KEY]=fields
        store._execute('UPDATE knowledge_bases SET data='+('%s' if pg else '?')+' WHERE org_id='+('%s' if pg else '?')+' AND kb_id='+('%s' if pg else '?'),(json.dumps(raw,sort_keys=True,separators=(',',':')),org_id,kb_id))


def preserve_dump(store,kb):
    raw=json.loads(store._dump(kb))
    # Called only inside the existing put_kb write/tenant transaction.
    pg=hasattr(store,'_pg')
    rows=store._execute('SELECT data FROM knowledge_bases WHERE org_id='+('%s' if pg else '?')+' AND kb_id='+('%s' if pg else '?'),(kb.org_id,kb.kb_id))
    if rows and KEY in json.loads(rows[0][0]):
        raw[KEY]=json.loads(rows[0][0])[KEY]
        return json.dumps(raw,sort_keys=True,separators=(',',':'))
    return store._dump(kb)
