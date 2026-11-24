"""Native psycopg3 MetadataStore with transaction-local RLS.

The small resource_directory contains only globally unique identifiers and their
owning tenant. It supports the existing org-less MetadataStore ID methods; it is
NOT an authorization surface. Service callers must still use the policy engine.
Every payload read/write is tenant-filtered, including child tables. Do not grant
SQL access to untrusted users: app.current_org_id is an application trust boundary.
"""
from __future__ import annotations
import inspect
import functools
import json
import re
import threading
from contextlib import contextmanager
from ..contracts.models import DocumentACL, encode, decode
from ..exceptions import NotFoundError, ConflictError, ValidationError
from .sqlite_store import tokens, SQLiteStore
from .pg_support import connect, driver


def tenant_method(fn):
    signature=inspect.signature(fn)
    @functools.wraps(fn)
    def run(self,*args,**kwargs):
        bound=signature.bind(self,*args,**kwargs).arguments
        with self.transaction():
            tenant=bound.get('org_id')
            objects=[v for k,v in bound.items() if k!='self' and hasattr(v,'org_id')]
            if objects:
                tenant=tenant or objects[0].org_id
                if any(o.org_id!=tenant for o in objects):raise ConflictError('Tenant mismatch')
            keys={'doc_id':'document','kb_id':'kb','event_id':'outbox','subscription_id':'webhook'}
            for arg,kind in keys.items():
                if arg in bound and bound[arg] is not None:
                    located=self._locate(kind,bound[arg])
                    if tenant is not None and located!=tenant:raise ConflictError('Tenant mismatch')
                    tenant=located
                    break
            if fn.__name__=='put_version':tenant=self._locate('document',bound['v'].doc_id)
            if fn.__name__=='put_anchors':
                anchors=list(bound['anchors'])
                if not anchors:return None
                tenant=anchors[0].org_id
                if any(a.org_id!=tenant for a in anchors):raise ConflictError('Tenant mismatch')
                args=(anchors,)
            if tenant is None:tenant=self._tenant
            if not tenant:raise ValidationError('Tenant context required')
            with self.tenant_scope(tenant):
                kinds={'put_kb':('kb','kb_id'),'put_document':('document','doc_id'),
                       'put_policy_rule':('policy','rule_id'),'put_issue':('issue','issue_id'),
                       'enqueue_outbox':('outbox','event_id'),'put_webhook_subscription':('webhook','subscription_id'),
                       'put_usage_event':('usage','usage_id'),'put_impact_alert':('impact','alert_id')}
                if fn.__name__ in kinds:
                    kind,key=kinds[fn.__name__];obj=objects[0]
                    self._register(kind,getattr(obj,key),tenant)
                return fn(self,*args,**kwargs)
    return run


class PostgresStore:
    """Serialized connection per instance; independent instances run concurrently.

    Use transaction() for atomic multi-method writes; nested calls use savepoints.
    Optional org_id pins an instance to a tenant, rejecting all context changes.
    """
    _DERIVED=SQLiteStore._DERIVED
    def __init__(self,dsn,*,enable_rls=True,org_id=None,migrate=True):
        self.lock=threading.RLock();self._tenant=None;self.org_id=org_id
        self.enable_rls=enable_rls;self._pg=driver();self.db=connect(dsn)
        try:
            if migrate:
                from .migrations import apply
                apply(self.db,enable_rls)
        except BaseException:
            self.db.close();raise

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                with self.db.transaction():yield
            except self._pg.IntegrityError:
                raise ConflictError('Storage constraint conflict') from None
            except self._pg.Error:
                raise ValidationError('PostgreSQL operation failed (details withheld)') from None

    @contextmanager
    def _write_scope(self):
        with self.transaction():yield

    @contextmanager
    def tenant_scope(self,org_id):
        if not isinstance(org_id,str) or not org_id:raise ValidationError('Tenant required')
        if self.org_id is not None and org_id!=self.org_id:raise ConflictError('Tenant mismatch')
        if self._tenant is not None and org_id!=self._tenant:raise ConflictError('Nested tenant mismatch')
        with self.transaction():
            previous=self._tenant
            self._execute("SELECT set_config('app.current_org_id',%s,true)",(org_id,))
            self._tenant=org_id
            try:yield
            finally:
                self._tenant=previous
                # If the transaction failed PostgreSQL refuses further statements;
                # enclosing savepoint rollback restores its LOCAL setting itself.
                if self.db.info.transaction_status!=self._pg.pq.TransactionStatus.INERROR:
                    self._execute("SELECT set_config('app.current_org_id',%s,true)",(previous or '',))

    def _locate(self,kind,key):
        rows=self._execute('SELECT tenant FROM resource_directory WHERE kind=%s AND id=%s',(kind,key))
        if not rows:raise NotFoundError('Resource not found')
        return rows[0][0]

    def _register(self,kind,key,org):
        rows=self._execute('INSERT INTO resource_directory VALUES(%s,%s,%s) ON CONFLICT(kind,id) DO UPDATE SET tenant=resource_directory.tenant RETURNING tenant',(kind,key,org))
        if rows[0][0]!=org:raise ConflictError('Resource identity conflict')

    def _execute(self,sql,args=()):
        with self.lock:
            try:
                with self.db.cursor() as cur:
                    cur.execute(sql,args)
                    return cur.fetchall() if cur.description else []
            except self._pg.IntegrityError:
                raise ConflictError('Storage constraint conflict') from None
            except self._pg.Error:
                raise ValidationError('PostgreSQL operation failed (details withheld)') from None

    def close(self):
        with self.lock:self.db.close()

    def _sync_document(self, doc_id):
        d = self.get_document(doc_id)
        kb = self.get_kb(d.kb_id)
        acl = self.get_acl(doc_id)
        if d.org_id != kb.org_id:
            raise ConflictError('Document tenant mismatch')
        values = (kb.space_type, kb.governance_tier, acl.access_level, d.lifecycle_state, int(d.archived), int(d.lifecycle_state == 'revoked' or bool(d.rights and d.rights.revoked)), d.valid_from, d.valid_to, doc_id)
        self._execute('UPDATE documents SET ' + ','.join((name + '=%s' for name, _ in self._DERIVED)) + ' WHERE doc_id=%s AND org_id=%s', values + (d.org_id,))

    def _get(self, sql, args):
        rows = self._execute(sql, args)
        if not rows:
            raise NotFoundError('Resource not found')
        return decode(json.loads(rows[0][0]))

    @staticmethod
    def _dump(obj):
        return json.dumps(encode(obj), ensure_ascii=False)

    @tenant_method
    def put_kb(self, kb):
        with self._write_scope():
            rows = self._execute('SELECT org_id FROM knowledge_bases WHERE kb_id=%s AND org_id=%s', (kb.kb_id,) + (self._tenant,))
            if rows and rows[0][0] != kb.org_id:
                raise ConflictError('Knowledge base identity conflict')
            self._execute('INSERT INTO knowledge_bases VALUES(%s,%s,%s) ON CONFLICT(kb_id) DO UPDATE SET data=excluded.data', (kb.kb_id, kb.org_id, self._dump(kb)))
            for row in self._execute('SELECT doc_id FROM documents WHERE kb_id=%s AND org_id=%s', (kb.kb_id,) + (self._tenant,)):
                self._sync_document(row[0])

    @tenant_method
    def get_kb(self, kb_id):
        return self._get('SELECT data FROM knowledge_bases WHERE kb_id=%s AND org_id=%s', (kb_id,) + (self._tenant,))

    @tenant_method
    def list_kbs(self, org_id):
        return [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM knowledge_bases WHERE org_id=%s ORDER BY kb_id', (org_id,))]

    @tenant_method
    def grant_member(self, kb_id, user_id, role):
        self._execute('INSERT INTO kb_members VALUES(%s,%s,%s,%s) ON CONFLICT(kb_id,user_id) DO UPDATE SET role=excluded.role', (self._tenant, kb_id, user_id, role))

    @tenant_method
    def member_role(self, kb_id, user_id):
        rows = self._execute('SELECT role FROM kb_members WHERE kb_id=%s AND user_id=%s AND org_id=%s', (kb_id, user_id) + (self._tenant,))
        return rows[0][0] if rows else None

    @tenant_method
    def get_document(self, doc_id):
        return self._get('SELECT data FROM documents WHERE doc_id=%s AND org_id=%s', (doc_id,) + (self._tenant,))

    @tenant_method
    def put_document(self, d):
        with self._write_scope():
            rows = self._execute('SELECT org_id,kb_id FROM documents WHERE doc_id=%s AND org_id=%s', (d.doc_id,) + (self._tenant,))
            if rows and rows[0] != (d.org_id, d.kb_id):
                raise ConflictError('Document identity conflict')
            self._execute('INSERT INTO documents(doc_id,org_id,kb_id,data) VALUES(%s,%s,%s,%s) ON CONFLICT(doc_id) DO UPDATE SET data=excluded.data', (d.doc_id, d.org_id, d.kb_id, self._dump(d)))
            self._sync_document(d.doc_id)

    @tenant_method
    def list_documents(self, org_id):
        return [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM documents WHERE org_id=%s ORDER BY doc_id', (org_id,))]

    @tenant_method
    def get_version(self, doc_id, version):
        return self._get('SELECT data FROM document_versions WHERE doc_id=%s AND version=%s AND org_id=%s', (doc_id, version) + (self._tenant,))

    @tenant_method
    def put_version(self, v, chunks):
        self._execute('INSERT INTO document_versions VALUES(%s,%s,%s,%s)', (self._tenant, v.doc_id, v.version, self._dump(v)))
        for c in chunks:
            if (c.doc_id,c.version)!=(v.doc_id,v.version):raise ConflictError('Chunk identity mismatch')
            self._execute('INSERT INTO chunks(org_id,doc_id,version,chunk_id,data) VALUES(%s,%s,%s,%s,%s)', (self._tenant, c.doc_id, c.version, c.chunk_id, self._dump(c)))

    @tenant_method
    def get_chunks(self, doc_id, version):
        chunks = [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM chunks WHERE doc_id=%s AND version=%s AND org_id=%s', (doc_id, version) + (self._tenant,))]
        return sorted(chunks, key=lambda c: c.start_offset)

    @tenant_method
    def get_acl(self, doc_id):
        try:
            return self._get('SELECT data FROM document_acls WHERE doc_id=%s AND org_id=%s', (doc_id,) + (self._tenant,))
        except NotFoundError:
            return DocumentACL()

    @tenant_method
    def set_acl(self, doc_id, acl):
        with self._write_scope():
            self._execute('INSERT INTO document_acls VALUES(%s,%s,%s) ON CONFLICT(doc_id) DO UPDATE SET data=excluded.data', (self._tenant, doc_id, self._dump(acl)))
            self._sync_document(doc_id)

    @tenant_method
    def mark_pending(self, doc_id, pending=True):
        if pending:
            self._execute('INSERT INTO pending_indexes VALUES(%s,%s) ON CONFLICT DO NOTHING', (self._tenant, doc_id,))
        else:
            self._execute('DELETE FROM pending_indexes WHERE doc_id=%s AND org_id=%s', (doc_id,) + (self._tenant,))

    @staticmethod
    def _binding_data(data):
        value = decode(json.loads(data))
        return value['binding'] if isinstance(value, dict) and 'binding' in value else value

    @tenant_method
    def put_binding(self, actor, binding, *, agent=None, purpose='read'):
        data = json.dumps({'binding': encode(binding), 'actor': encode(actor), 'agent': encode(agent), 'purpose': purpose}, sort_keys=True)
        self._execute('INSERT INTO consumer_bindings VALUES(%s,%s,%s,%s,%s) ON CONFLICT(org_id,user_id,consumer_type,consumer_id) DO UPDATE SET data=excluded.data', (actor.org_id, actor.user_id, binding.consumer_type, binding.consumer_id, data))

    @tenant_method
    def get_binding(self, actor, consumer_type, consumer_id):
        rows = self._execute('SELECT data FROM consumer_bindings WHERE org_id=%s AND user_id=%s AND consumer_type=%s AND consumer_id=%s', (actor.org_id, actor.user_id, consumer_type, consumer_id))
        if not rows:
            raise NotFoundError('Binding not found')
        return self._binding_data(rows[0][0])

    @tenant_method
    def list_bindings(self, actor):
        return [self._binding_data(row[0]) for row in self._execute('SELECT data FROM consumer_bindings WHERE org_id=%s AND user_id=%s ORDER BY consumer_type,consumer_id', (actor.org_id, actor.user_id))]

    @tenant_method
    def binding_identity(self, org_id, user_id, consumer_type, consumer_id):
        rows = self._execute('SELECT data FROM consumer_bindings WHERE org_id=%s AND user_id=%s AND consumer_type=%s AND consumer_id=%s', (org_id, user_id, consumer_type, consumer_id))
        if not rows:
            raise NotFoundError('Binding not found')
        value = decode(json.loads(rows[0][0]))
        if isinstance(value, dict) and 'binding' in value:
            return (value.get('actor'), value.get('agent'), value.get('purpose', 'read'))
        return (None, None, 'read')

    @tenant_method
    def put_anchors(self, anchors):
        from ..contracts.anchors import EvidenceAnchor
        with self._write_scope():
            for anchor in anchors:
                if not isinstance(anchor, EvidenceAnchor):
                    raise ValidationError('Expected EvidenceAnchor')
                if self.get_document(anchor.doc_id).org_id != anchor.org_id:
                    raise ConflictError('Anchor tenant mismatch')
                self._execute('INSERT INTO evidence_anchors VALUES(%s,%s,%s,%s,%s,%s,%s)', (anchor.anchor_id, anchor.org_id, anchor.doc_id, anchor.version, anchor.selector_kind.value, anchor.reanchor_status.value, self._dump(anchor)))

    @tenant_method
    def get_anchors(self, org_id, doc_id, version):
        return [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM evidence_anchors WHERE org_id=%s AND doc_id=%s AND version=%s ORDER BY anchor_id', (org_id, doc_id, version))]

    @tenant_method
    def get_anchor(self, org_id, doc_id, version, anchor_id):
        return self._get('SELECT data FROM evidence_anchors WHERE org_id=%s AND doc_id=%s AND version=%s AND anchor_id=%s', (org_id, doc_id, version, anchor_id))

    @tenant_method
    def update_anchor(self, anchor):
        from ..contracts.anchors import EvidenceAnchor
        if not isinstance(anchor, EvidenceAnchor):
            raise ValidationError('Expected EvidenceAnchor')
        with self._write_scope():
            self.get_anchor(anchor.org_id, anchor.doc_id, anchor.version, anchor.anchor_id)
            self._execute('UPDATE evidence_anchors SET selector_kind=%s,reanchor_status=%s,data=%s WHERE org_id=%s AND doc_id=%s AND version=%s AND anchor_id=%s', (anchor.selector_kind.value, anchor.reanchor_status.value, self._dump(anchor), anchor.org_id, anchor.doc_id, anchor.version, anchor.anchor_id))

    @tenant_method
    def put_policy_rule(self, rule):
        from ..contracts.policy import PolicyRule
        if not isinstance(rule, PolicyRule):
            raise ValidationError('Expected PolicyRule')
        with self._write_scope():
            rows = self._execute('SELECT org_id FROM policy_rules WHERE rule_id=%s AND org_id=%s', (rule.rule_id,) + (self._tenant,))
            if rows and rows[0][0] != rule.org_id:
                raise ConflictError('Policy identity conflict')
            self._execute('INSERT INTO policy_rules VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(rule_id) DO UPDATE SET scope_kb_id=excluded.scope_kb_id,scope_doc_id=excluded.scope_doc_id,priority=excluded.priority,effect=excluded.effect,data=excluded.data', (rule.rule_id, rule.org_id, rule.scope_kb_id, rule.scope_doc_id, rule.priority, rule.effect.value, self._dump(rule)))

    @tenant_method
    def list_policy_rules(self, org_id):
        return [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM policy_rules WHERE org_id=%s ORDER BY priority,rule_id', (org_id,))]

    @tenant_method
    def delete_policy_rule(self, org_id, rule_id):
        self._execute('DELETE FROM policy_rules WHERE org_id=%s AND rule_id=%s', (org_id, rule_id))

    @tenant_method
    def put_issue(self, issue):
        from ..contracts.issues import EvidenceIssue
        if not isinstance(issue, EvidenceIssue):
            raise ValidationError('Expected EvidenceIssue')
        with self._write_scope():
            if self.get_document(issue.doc_id).org_id != issue.org_id:
                raise ConflictError('Issue tenant mismatch')
            self.get_version(issue.doc_id, issue.version)
            if issue.anchor_id:
                self.get_anchor(issue.org_id, issue.doc_id, issue.version, issue.anchor_id)
            existing = self._execute('SELECT org_id,doc_id,version,anchor_id FROM evidence_issues WHERE issue_id=%s AND org_id=%s', (issue.issue_id,) + (self._tenant,))
            if existing and tuple(existing[0]) != (issue.org_id, issue.doc_id, issue.version, issue.anchor_id):
                raise ConflictError('Issue identity conflict')
            self._execute('INSERT INTO evidence_issues VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(issue_id) DO UPDATE SET status=excluded.status,created_at=excluded.created_at,data=excluded.data', (issue.issue_id, issue.org_id, issue.doc_id, issue.version, issue.anchor_id, issue.status, issue.created_at, self._dump(issue)))

    @tenant_method
    def get_issue(self, org_id, issue_id):
        from ..contracts.issues import issue_text
        issue_text(org_id, 'org_id', True)
        issue_text(issue_id, 'issue_id', True)
        return self._get('SELECT data FROM evidence_issues WHERE org_id=%s AND issue_id=%s', (org_id, issue_id))

    @tenant_method
    def list_issues(self, org_id, *, doc_id=None, status=None):
        from ..contracts.issues import issue_text, ISSUE_STATUSES
        issue_text(org_id, 'org_id', True)
        sql = 'SELECT data FROM evidence_issues WHERE org_id=%s'
        args = [org_id]
        if doc_id is not None:
            issue_text(doc_id, 'doc_id', True)
            sql += ' AND doc_id=%s'
            args.append(doc_id)
        if status is not None:
            if not isinstance(status, str) or status not in ISSUE_STATUSES:
                raise ValidationError('Invalid status')
            sql += ' AND status=%s'
            args.append(status)
        return [decode(json.loads(row[0])) for row in self._execute(sql + ' ORDER BY created_at,issue_id', args)]

    @staticmethod
    def _audit_from_row(row):
        return decode(json.loads(row[-1]))

    @tenant_method
    def append_audit_event(self, event):
        from dataclasses import replace
        from ..contracts.audit import AuditEvent, audit_hash
        from ..audit.ledger import COLUMNS
        if not isinstance(event, AuditEvent):
            raise ValidationError('Expected AuditEvent')
        with self._write_scope():
            self._execute("SELECT pg_advisory_xact_lock(hashtext('audit:' || %s))", (event.org_id,))
            rows = self._execute('SELECT seq_no,event_hash FROM audit_events WHERE org_id=%s ORDER BY seq_no DESC LIMIT 1', (event.org_id,))
            seq, previous = (rows[0][0] + 1, rows[0][1]) if rows else (1, '0' * 64)
            event = replace(event, seq_no=seq, prev_hash=previous)
            event = replace(event, event_hash=audit_hash(event))
            values = event.to_dict()
            self._execute('INSERT INTO audit_events VALUES(' + ','.join(('%s' for _ in range(17))) + ')', tuple((values[c] for c in COLUMNS)) + (self._dump(event),))
        return event

    @tenant_method
    def list_audit_events(self, org_id, *, doc_id=None, actor_id=None, action=None, since=None, until=None, limit=100):
        from ..contracts.policy import parse_time
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValidationError('Invalid audit limit')
        sql = 'SELECT data FROM audit_events WHERE org_id=%s'
        args = [org_id]
        for name, value in (('doc_id', doc_id), ('actor_id', actor_id), ('action', action)):
            if value is not None:
                sql += ' AND ' + name + '=%s'
                args.append(value)
        for op, value in (('>=', since), ('<=', until)):
            if value is not None:
                parse_time(value)
                sql += ' AND occurred_at::timestamptz' + op + '%s::timestamptz'
                args.append(value)
        args.append(limit)
        return [decode(json.loads(r[0])) for r in self._execute(sql + ' ORDER BY seq_no LIMIT %s', args)]

    @tenant_method
    def iter_audit_chain(self, org_id, from_seq=1, to_seq=None):
        sql = 'SELECT * FROM audit_events WHERE org_id=%s AND seq_no>=%s'
        args = [org_id, from_seq]
        if to_seq is not None:
            sql += ' AND seq_no<=%s'
            args.append(to_seq)
        return iter(self._execute(sql + ' ORDER BY seq_no', args))

    @tenant_method
    def enqueue_outbox(self, event):
        from ..contracts.events import OutboxEvent
        if not isinstance(event, OutboxEvent):
            raise ValidationError('Expected OutboxEvent')
        if event.status != 'pending' or event.attempts != 0:
            raise ValidationError('New outbox event must be pending')
        with self._write_scope():
            rows = self._execute('SELECT * FROM outbox_events WHERE event_id=%s AND org_id=%s', (event.event_id,) + (self._tenant,))
            if rows:
                old = self._outbox_from_row(rows[0])
                if (old.org_id, old.aggregate_type, old.aggregate_id, old.event_type, old.payload) != (event.org_id, event.aggregate_type, event.aggregate_id, event.event_type, event.payload):
                    raise ConflictError('Outbox identity conflict')
                return
            self._execute('INSERT INTO outbox_events VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (event.event_id, event.org_id, event.aggregate_type, event.aggregate_id, event.event_type, json.dumps(dict(event.payload), sort_keys=True), event.status, event.attempts, event.available_at, event.created_at, event.dispatched_at))

    @staticmethod
    def _outbox_from_row(row):
        from ..contracts.events import OutboxEvent
        return OutboxEvent(*row[:5], payload=json.loads(row[5]), status=row[6], attempts=row[7], available_at=row[8], created_at=row[9], dispatched_at=row[10])

    @tenant_method
    def mark_outbox_dispatched(self, event_id, dispatched_at):
        self._execute("UPDATE outbox_events SET status='dispatched',dispatched_at=%s WHERE event_id=%s AND status='processing' AND org_id=%s", (dispatched_at, event_id) + (self._tenant,))

    @tenant_method
    def mark_outbox_failed(self, event_id, next_available_at, max_attempts=5):
        self._execute("UPDATE outbox_events SET status=CASE WHEN attempts>=%s THEN 'dead_letter' ELSE 'failed' END,available_at=%s WHERE event_id=%s AND status='processing' AND org_id=%s", (max_attempts, next_available_at, event_id) + (self._tenant,))

    @tenant_method
    def put_webhook_subscription(self, sub):
        from ..contracts.events import WebhookSubscription
        if not isinstance(sub, WebhookSubscription):
            raise ValidationError('Expected WebhookSubscription')
        with self._write_scope():
            old = self._execute('SELECT org_id FROM webhook_subscriptions WHERE subscription_id=%s AND org_id=%s', (sub.subscription_id,) + (self._tenant,))
            if old and old[0][0] != sub.org_id:
                raise ConflictError('Webhook tenant mismatch')
            self._execute('INSERT INTO webhook_subscriptions VALUES(%s,%s,%s,%s,%s) ON CONFLICT(subscription_id) DO UPDATE SET event_types=excluded.event_types,active=excluded.active,data=excluded.data', (sub.subscription_id, sub.org_id, json.dumps(sub.event_types), int(sub.active), self._dump(sub)))

    @tenant_method
    def list_webhook_subscriptions(self, org_id, *, active_only=True):
        sql = 'SELECT data FROM webhook_subscriptions WHERE org_id=%s'
        if active_only:
            sql += ' AND active=1'
        return [decode(json.loads(r[0])) for r in self._execute(sql + ' ORDER BY subscription_id', (org_id,))]

    @tenant_method
    def record_webhook_delivery(self, delivery):
        from ..contracts.events import WebhookDelivery
        if not isinstance(delivery, WebhookDelivery):
            raise ValidationError('Expected WebhookDelivery')
        with self._write_scope():
            subscriptions = self._execute('SELECT org_id FROM webhook_subscriptions WHERE subscription_id=%s AND org_id=%s', (delivery.subscription_id,) + (self._tenant,))
            events = self._execute('SELECT org_id FROM outbox_events WHERE event_id=%s AND org_id=%s', (delivery.outbox_event_id,) + (self._tenant,))
            if not subscriptions or not events or subscriptions[0][0] != delivery.org_id or (events[0][0] != delivery.org_id):
                raise ConflictError('Webhook delivery tenant mismatch')
            self._execute("INSERT INTO webhook_deliveries VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(subscription_id,outbox_event_id) DO UPDATE SET status=excluded.status,http_status=excluded.http_status,attempted_at=excluded.attempted_at,data=excluded.data WHERE webhook_deliveries.status!='delivered'", (delivery.delivery_id, delivery.org_id, delivery.subscription_id, delivery.outbox_event_id, delivery.status, delivery.http_status, delivery.attempted_at, self._dump(delivery)))

    @tenant_method
    def has_webhook_delivery(self, subscription_id, outbox_event_id):
        return bool(self._execute("SELECT 1 FROM webhook_deliveries WHERE subscription_id=%s AND outbox_event_id=%s AND status='delivered' AND org_id=%s", (subscription_id, outbox_event_id) + (self._tenant,)))

    @tenant_method
    def put_usage_event(self, event, *, actor=None, agent=None):
        from ..contracts.impact import UsageEvent
        if not isinstance(event, UsageEvent):
            raise ValidationError('Expected UsageEvent')
        if actor is not None and (actor.org_id, actor.user_id) != (event.org_id, event.actor_id):
            raise ConflictError('Usage identity mismatch')
        if agent is not None and (agent.org_id, agent.agent_id) != (event.org_id, event.agent_id):
            raise ConflictError('Usage agent mismatch')
        with self._write_scope():
            data = json.dumps({'event': encode(event), 'actor': encode(actor), 'agent': encode(agent)}, sort_keys=True)
            rows = self._execute('SELECT data FROM usage_events WHERE usage_id=%s AND org_id=%s', (event.usage_id,) + (self._tenant,))
            if rows:
                old = decode(json.loads(rows[0][0]))
                if old.get('event') != event or (actor is not None and old.get('actor') != actor) or (agent is not None and old.get('agent') != agent):
                    raise ConflictError('Usage events are immutable')
                return
            document = self.get_document(event.doc_id)
            if document.org_id != event.org_id:
                raise ConflictError('Usage tenant mismatch')
            self.get_version(event.doc_id, event.version)
            if event.anchor_id:
                self.get_anchor(event.org_id, event.doc_id, event.version, event.anchor_id)
            self._execute('INSERT INTO usage_events VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (event.usage_id, event.org_id, event.doc_id, event.version, event.anchor_id, event.consumer_type, event.consumer_id, event.task_id, event.actor_id, event.agent_id, event.purpose, event.receipt_hash, event.created_at, data))

    @tenant_method
    def list_usage_events_for_doc(self, org_id, doc_id, *, version=None):
        sql = 'SELECT data FROM usage_events WHERE org_id=%s AND doc_id=%s'
        args = [org_id, doc_id]
        if version is not None:
            sql += ' AND version=%s'
            args.append(version)
        return [decode(json.loads(r[0]))['event'] for r in self._execute(sql + ' ORDER BY created_at,usage_id', args)]

    @tenant_method
    def usage_identity(self, org_id, usage_id):
        rows = self._execute('SELECT data FROM usage_events WHERE org_id=%s AND usage_id=%s', (org_id, usage_id))
        if not rows:
            raise NotFoundError('Usage not found')
        data = decode(json.loads(rows[0][0]))
        return (data.get('actor'), data.get('agent'))

    @tenant_method
    def put_impact_alert(self, alert, *, actor_id='', usage_id=''):
        from ..contracts.impact import ImpactAlert
        if not isinstance(alert, ImpactAlert):
            raise ValidationError('Expected ImpactAlert')
        data = json.dumps({'alert': encode(alert), 'actor_id': actor_id, 'usage_id': usage_id}, sort_keys=True)
        with self._write_scope():
            if self.get_document(alert.doc_id).org_id != alert.org_id:
                raise ConflictError('Impact tenant mismatch')
            rows = self._execute('SELECT org_id,aggregate_id,payload_json FROM outbox_events WHERE event_id=%s AND org_id=%s', (alert.source_event_id,) + (self._tenant,))
            if not rows or rows[0][0] != alert.org_id or json.loads(rows[0][2]).get('doc_id') != alert.doc_id:
                raise ConflictError('Impact event mismatch')
            self._execute('INSERT INTO impact_alerts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(org_id,source_event_id,target_type,target_id) DO NOTHING', (alert.alert_id, alert.org_id, alert.source_event_id, alert.doc_id, alert.source_version, alert.target_type, alert.target_id, alert.impact_reason.value, alert.status, alert.created_at, data))

    @tenant_method
    def list_impact_alerts(self, org_id, *, doc_id=None, status=None, target_id=None):
        if status is not None and status not in ('open', 'acknowledged', 'resolved'):
            raise ValidationError('Invalid impact status')
        sql = 'SELECT data,status FROM impact_alerts WHERE org_id=%s'
        args = [org_id]
        for name, value in (('doc_id', doc_id), ('status', status), ('target_id', target_id)):
            if value is not None:
                sql += ' AND ' + name + '=%s'
                args.append(value)
        from dataclasses import replace
        return [replace(decode(json.loads(r[0]))['alert'], status=r[1]) for r in self._execute(sql + ' ORDER BY created_at,alert_id', args)]

    @tenant_method
    def impact_owner(self, org_id, alert_id):
        rows = self._execute('SELECT data FROM impact_alerts WHERE org_id=%s AND alert_id=%s', (org_id, alert_id))
        if not rows:
            raise NotFoundError('Impact alert not found')
        return json.loads(rows[0][0]).get('actor_id', '')

    @tenant_method
    def update_impact_alert_status(self, org_id, alert_id, status):
        if status not in ('open', 'acknowledged', 'resolved'):
            raise ValidationError('Invalid impact status')
        with self._write_scope():
            self.impact_owner(org_id, alert_id)
            self._execute('UPDATE impact_alerts SET status=%s WHERE org_id=%s AND alert_id=%s', (status, org_id, alert_id))

    @tenant_method
    def list_all_bindings(self, org_id):
        return [(r[0], self._binding_data(r[1])) for r in self._execute('SELECT user_id,data FROM consumer_bindings WHERE org_id=%s ORDER BY user_id,consumer_type,consumer_id', (org_id,))]

    def _tenants(self):
        if self.org_id:return [self.org_id]
        return [r[0] for r in self._execute('SELECT DISTINCT tenant FROM resource_directory ORDER BY tenant')]

    def pending_documents(self):
        result=[]
        for tenant in self._tenants():
            with self.tenant_scope(tenant):
                result.extend(r[0] for r in self._execute('SELECT doc_id FROM pending_indexes WHERE org_id=%s ORDER BY doc_id',(tenant,)))
        return sorted(result)

    @tenant_method
    def refresh_fts(self,doc_id):
        d=self.get_document(doc_id)
        self._execute('UPDATE chunks SET search_vector=NULL WHERE org_id=%s AND doc_id=%s',(d.org_id,doc_id))
        if not d.archived:
            for c in self.get_chunks(doc_id,d.current_version):
                self._execute("UPDATE chunks SET search_vector=to_tsvector('simple',%s) WHERE org_id=%s AND doc_id=%s AND version=%s AND chunk_id=%s",(' '.join(tokens(c.text)),d.org_id,doc_id,c.version,c.chunk_id))

    def keyword_search(self,query,org_id,limit=100):
        return self.keyword_search_pushdown(query,org_id,limit,active_only=False)

    @tenant_method
    def keyword_search_pushdown(self,query,org_id,limit=100,*,kb_ids=None,doc_ids=None,space_types=None,active_only=True):
        if type(limit) is not int or not 1<=limit<=100000:raise ValidationError('Invalid search limit')
        ts=tokens(query)
        if re.search(r'[\u3400-\u9fff]{2}',query):ts=[t for t in ts if not re.fullmatch(r'[\u3400-\u9fff]',t)]
        if not ts:return []
        # Lexemes are produced locally, not tsquery syntax supplied by a caller.
        match=' | '.join("'"+t.replace("'","''")+"'" for t in ts[:64])
        sql="""SELECT c.doc_id,c.version,c.chunk_id,-ts_rank_cd(c.search_vector,q)
        FROM chunks c JOIN documents d ON c.doc_id=d.doc_id AND c.org_id=d.org_id,
        to_tsquery('simple',%s) q WHERE c.org_id=%s AND d.org_id=%s AND c.search_vector @@ q"""
        args=[match,org_id,org_id]
        if active_only:sql+=' AND d.archived=0 AND d.revoked=0'
        for column,values in (('kb_id',kb_ids),('doc_id',doc_ids),('space_type',space_types)):
            if values is not None:
                if isinstance(values,str) or not isinstance(values,(list,tuple,set,frozenset)) or any(not isinstance(v,str) for v in values):raise ValidationError('Invalid pushdown scope')
                if not values:return []
                sql+=' AND d.'+column+' = ANY(%s)';args.append(list(values))
        args.append(limit)
        return self._execute(sql+' ORDER BY 4,c.doc_id,c.version,c.chunk_id LIMIT %s',args)

    def claim_outbox_batch(self,now_iso,limit=50,*,org_id=None):
        from datetime import timedelta
        from ..contracts.policy import parse_time
        if type(limit) is not int or not 1<=limit<=1000:raise ValidationError('Invalid outbox limit')
        lease=(parse_time(now_iso)+timedelta(seconds=60)).isoformat()
        result=[]
        for tenant in [org_id] if org_id is not None else self._tenants():
            with self.tenant_scope(tenant):
                rows=self._execute("""WITH picked AS (
                    SELECT event_id FROM outbox_events WHERE org_id=%s
                    AND status IN ('pending','failed','processing')
                    AND available_at::timestamptz<=%s::timestamptz
                    ORDER BY created_at,event_id LIMIT %s FOR UPDATE SKIP LOCKED)
                    UPDATE outbox_events o SET status='processing',attempts=o.attempts+1,available_at=%s
                    FROM picked WHERE o.event_id=picked.event_id AND o.org_id=%s RETURNING o.*""",
                    (tenant,now_iso,limit-len(result),lease,tenant))
                result.extend(self._outbox_from_row(r) for r in rows)
            if len(result)>=limit:break
        return result

    @contextmanager
    def outbox_processing_scope(self,event):
        # The attempt is the fencing token. Retain the row lock until handlers
        # and their status transaction complete; an expired lease cannot steal it.
        with self.tenant_scope(event.org_id):
            rows=self._execute("SELECT 1 FROM outbox_events WHERE org_id=%s AND event_id=%s AND status='processing' AND attempts=%s FOR UPDATE",(event.org_id,event.event_id,event.attempts))
            yield bool(rows)
