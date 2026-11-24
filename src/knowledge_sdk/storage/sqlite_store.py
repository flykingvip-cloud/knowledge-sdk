from __future__ import annotations
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from ..contracts.models import (KnowledgeBase, Document, DocumentVersion, DocumentACL, Chunk, Actor, ConsumerBinding, encode, decode)
from ..exceptions import NotFoundError, ConflictError, ValidationError

def tokens(text):
    # unicode61 cannot segment CJK. Add individual CJK characters and bigrams.
    words=re.findall(r"[^\W_]+",text.lower(),re.UNICODE); out=[]
    for word in words:
        parts=re.findall(r"[\u3400-\u9fff]+|[^\u3400-\u9fff]+",word)
        for part in parts:
            if re.fullmatch(r"[\u3400-\u9fff]+",part):
                out.extend(part); out.extend(part[i:i+2] for i in range(len(part)-1))
            else: out.append(part)
    return list(dict.fromkeys(out))

class SQLiteStore:
    """Single-connection, serialized transactions; SQLite remains authoritative."""
    def __init__(self,path=":memory:"):
        self.lock=threading.RLock()
        self.db=sqlite3.connect(str(path),check_same_thread=False,isolation_level=None)
        try:
            self.db.execute("PRAGMA foreign_keys=ON");self.db.execute("PRAGMA busy_timeout=5000")
            schema=self.db.execute("PRAGMA user_version").fetchone()[0]
            if schema not in (0,1,2,3):raise ConflictError("Unsupported database schema version")
            if schema<2:
                with self.transaction():
                    for statement in self._BASE_SCHEMA.split(';'):
                        if statement.strip():self.db.execute(statement)
                    columns={r[1] for r in self.db.execute("PRAGMA table_info(documents)")}
                    for name,kind in self._DERIVED:
                        if name not in columns:self.db.execute('ALTER TABLE documents ADD COLUMN '+name+' '+kind)
                    for statement in self._V2_SCHEMA.split(';'):
                        if statement.strip():self.db.execute(statement)
                    self._backfill()
                    self.db.execute("PRAGMA user_version=2")
            if schema<3:
                with self.transaction():
                    for statement in self._V3_SCHEMA.split(';'):
                        if statement.strip():self.db.execute(statement)
                    self.db.execute("PRAGMA user_version=3")
            self.db.execute("PRAGMA journal_mode=WAL")
        except BaseException:
            self.db.close();raise

    _BASE_SCHEMA="""
        CREATE TABLE IF NOT EXISTS knowledge_bases(kb_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS kb_members(kb_id TEXT NOT NULL REFERENCES knowledge_bases(kb_id),user_id TEXT NOT NULL,role TEXT NOT NULL,PRIMARY KEY(kb_id,user_id));
        CREATE TABLE IF NOT EXISTS documents(doc_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,kb_id TEXT NOT NULL REFERENCES knowledge_bases(kb_id),data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS documents_org ON documents(org_id,kb_id);
        CREATE TABLE IF NOT EXISTS document_versions(doc_id TEXT NOT NULL REFERENCES documents(doc_id),version INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(doc_id,version));
        CREATE TABLE IF NOT EXISTS document_acls(doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id),data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks(doc_id TEXT NOT NULL,version INTEGER NOT NULL,chunk_id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(doc_id,version,chunk_id),FOREIGN KEY(doc_id,version) REFERENCES document_versions(doc_id,version));
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(doc_id UNINDEXED,version UNINDEXED,chunk_id UNINDEXED,org_id UNINDEXED,content,tokenize='unicode61');
        CREATE TABLE IF NOT EXISTS pending_indexes(doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id));
        CREATE TABLE IF NOT EXISTS consumer_bindings(org_id TEXT NOT NULL,user_id TEXT NOT NULL,consumer_type TEXT NOT NULL,consumer_id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(org_id,user_id,consumer_type,consumer_id));

        """
    _DERIVED=(('space_type',"TEXT NOT NULL DEFAULT ''"),('governance_tier',"TEXT NOT NULL DEFAULT 'l1_agile'"),
              ('access_level',"TEXT NOT NULL DEFAULT ''"),('lifecycle_state',"TEXT NOT NULL DEFAULT 'published'"),
              ('archived','INTEGER NOT NULL DEFAULT 0'),('revoked','INTEGER NOT NULL DEFAULT 0'),('valid_from','TEXT'),('valid_to','TEXT'))
    _V2_SCHEMA="""
        CREATE INDEX IF NOT EXISTS idx_docs_pushdown ON documents(org_id,kb_id,archived,revoked,lifecycle_state,access_level);
        CREATE TABLE IF NOT EXISTS evidence_anchors(anchor_id TEXT NOT NULL,org_id TEXT NOT NULL,doc_id TEXT NOT NULL,version INTEGER NOT NULL,selector_kind TEXT NOT NULL,reanchor_status TEXT NOT NULL DEFAULT 'anchored',data TEXT NOT NULL,PRIMARY KEY(org_id,doc_id,version,anchor_id),FOREIGN KEY(doc_id,version) REFERENCES document_versions(doc_id,version));
        CREATE INDEX IF NOT EXISTS idx_anchors_lookup ON evidence_anchors(org_id,anchor_id);
        CREATE TABLE IF NOT EXISTS policy_rules(rule_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,scope_kb_id TEXT NOT NULL DEFAULT '',scope_doc_id TEXT NOT NULL DEFAULT '',priority INTEGER NOT NULL DEFAULT 100,effect TEXT NOT NULL,data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_policy_org_scope ON policy_rules(org_id,scope_kb_id,scope_doc_id,priority);
        CREATE TABLE IF NOT EXISTS evidence_issues(issue_id TEXT PRIMARY KEY,org_id TEXT NOT NULL,doc_id TEXT NOT NULL,version INTEGER NOT NULL,anchor_id TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL,data TEXT NOT NULL);
    """
    _V3_SCHEMA="""
CREATE TABLE IF NOT EXISTS outbox_events (
  event_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  dispatched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending
  ON outbox_events(status, available_at, created_at);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  seq_no INTEGER NOT NULL,
  prev_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  agent_id TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  purpose TEXT NOT NULL,
  resource_uri TEXT NOT NULL DEFAULT '',
  doc_id TEXT NOT NULL DEFAULT '',
  decision_effect TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  policy_generation TEXT NOT NULL DEFAULT '0',
  redaction_profile TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL,
  UNIQUE(org_id, seq_no)
);
CREATE INDEX IF NOT EXISTS idx_audit_org_time
  ON audit_events(org_id, occurred_at, seq_no);
CREATE TABLE IF NOT EXISTS usage_events (
  usage_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  anchor_id TEXT NOT NULL DEFAULT '',
  consumer_type TEXT NOT NULL,
  consumer_id TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  actor_id TEXT NOT NULL,
  agent_id TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL,
  receipt_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_doc
  ON usage_events(org_id, doc_id, version, anchor_id);
CREATE TABLE IF NOT EXISTS impact_alerts (
  alert_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  source_version INTEGER NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  impact_reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  data TEXT NOT NULL,
  UNIQUE(org_id, source_event_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS idx_impact_org_status
  ON impact_alerts(org_id, status, created_at);
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
  subscription_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  event_types TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
  delivery_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  subscription_id TEXT NOT NULL,
  outbox_event_id TEXT NOT NULL,
  status TEXT NOT NULL,
  http_status INTEGER NOT NULL DEFAULT 0,
  attempted_at TEXT NOT NULL,
  data TEXT NOT NULL,
  UNIQUE(subscription_id, outbox_event_id)
);
CREATE TABLE IF NOT EXISTS review_decisions (
  decision_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  stage TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_packs (
  pack_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'sealed',
  pack_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connector_sync_state (
  connector_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  cursor TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  data TEXT NOT NULL,
  PRIMARY KEY(org_id, connector_id)
);
    """
    @contextmanager
    def _write_scope(self):
        with self.lock:
            if self.db.in_transaction:yield
            else:
                with self.transaction():yield
    def _sync_document(self,doc_id):
        d=self.get_document(doc_id);kb=self.get_kb(d.kb_id);acl=self.get_acl(doc_id)
        if d.org_id!=kb.org_id:raise ConflictError('Document tenant mismatch')
        values=(kb.space_type,kb.governance_tier,acl.access_level,d.lifecycle_state,int(d.archived),
                int(d.lifecycle_state=='revoked' or bool(d.rights and d.rights.revoked)),d.valid_from,d.valid_to,doc_id)
        self._execute('UPDATE documents SET '+','.join(name+'=?' for name,_ in self._DERIVED)+' WHERE doc_id=?',values)
    def _backfill(self):
        for row in self._execute('SELECT doc_id FROM documents'):self._sync_document(row[0])
    @contextmanager
    def transaction(self):
        with self.lock:
            if self.db.in_transaction:
                import uuid
                name='kb_'+uuid.uuid4().hex
                self.db.execute('SAVEPOINT '+name)
                try:yield;self.db.execute('RELEASE '+name)
                except BaseException:
                    self.db.execute('ROLLBACK TO '+name);self.db.execute('RELEASE '+name);raise
            else:
                self.db.execute("BEGIN IMMEDIATE")
                try: yield; self.db.execute("COMMIT")
                except BaseException: self.db.execute("ROLLBACK"); raise
    def close(self):
        with self.lock: self.db.close()
    def _execute(self,sql,args=()):
        with self.lock:
            try: return self.db.execute(sql,args).fetchall()
            except sqlite3.IntegrityError as exc: raise ConflictError("Storage constraint conflict") from exc
    def _get(self,sql,args):
        rows=self._execute(sql,args)
        if not rows: raise NotFoundError("Resource not found")
        return decode(json.loads(rows[0][0]))
    @staticmethod
    def _dump(obj): return json.dumps(encode(obj),ensure_ascii=False)
    def put_kb(self,kb):
        with self._write_scope():
            rows=self._execute('SELECT org_id FROM knowledge_bases WHERE kb_id=?',(kb.kb_id,))
            if rows and rows[0][0]!=kb.org_id:raise ConflictError('Knowledge base identity conflict')
            self._execute("INSERT INTO knowledge_bases VALUES(?,?,?) ON CONFLICT(kb_id) DO UPDATE SET data=excluded.data",(kb.kb_id,kb.org_id,self._dump(kb)))
            for row in self._execute('SELECT doc_id FROM documents WHERE kb_id=?',(kb.kb_id,)):self._sync_document(row[0])
    def get_kb(self,kb_id): return self._get("SELECT data FROM knowledge_bases WHERE kb_id=?",(kb_id,))
    def list_kbs(self,org_id): return [decode(json.loads(r[0])) for r in self._execute("SELECT data FROM knowledge_bases WHERE org_id=? ORDER BY kb_id",(org_id,))]
    def grant_member(self,kb_id,user_id,role):
        self._execute("INSERT INTO kb_members VALUES(?,?,?) ON CONFLICT(kb_id,user_id) DO UPDATE SET role=excluded.role",(kb_id,user_id,role))
    def member_role(self,kb_id,user_id):
        rows=self._execute("SELECT role FROM kb_members WHERE kb_id=? AND user_id=?",(kb_id,user_id)); return rows[0][0] if rows else None
    def get_document(self,doc_id): return self._get("SELECT data FROM documents WHERE doc_id=?",(doc_id,))
    def put_document(self,d):
        with self._write_scope():
            rows=self._execute('SELECT org_id,kb_id FROM documents WHERE doc_id=?',(d.doc_id,))
            if rows and rows[0]!=(d.org_id,d.kb_id):raise ConflictError('Document identity conflict')
            self._execute("INSERT INTO documents(doc_id,org_id,kb_id,data) VALUES(?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET data=excluded.data",(d.doc_id,d.org_id,d.kb_id,self._dump(d)))
            self._sync_document(d.doc_id)
    def list_documents(self,org_id): return [decode(json.loads(r[0])) for r in self._execute("SELECT data FROM documents WHERE org_id=? ORDER BY doc_id",(org_id,))]
    def get_version(self,doc_id,version): return self._get("SELECT data FROM document_versions WHERE doc_id=? AND version=?",(doc_id,version))
    def put_version(self,v,chunks):
        self._execute("INSERT INTO document_versions VALUES(?,?,?)",(v.doc_id,v.version,self._dump(v)))
        for c in chunks: self._execute("INSERT INTO chunks VALUES(?,?,?,?)",(c.doc_id,c.version,c.chunk_id,self._dump(c)))
    def get_chunks(self,doc_id,version):
        chunks=[decode(json.loads(r[0])) for r in self._execute("SELECT data FROM chunks WHERE doc_id=? AND version=?",(doc_id,version))]
        return sorted(chunks,key=lambda c:c.start_offset)
    def get_acl(self,doc_id):
        try: return self._get("SELECT data FROM document_acls WHERE doc_id=?",(doc_id,))
        except NotFoundError: return DocumentACL()
    def set_acl(self,doc_id,acl):
        with self._write_scope():
            self._execute("INSERT INTO document_acls VALUES(?,?) ON CONFLICT(doc_id) DO UPDATE SET data=excluded.data",(doc_id,self._dump(acl)))
            self._sync_document(doc_id)
    def refresh_fts(self,doc_id):
        self._execute("DELETE FROM chunks_fts WHERE doc_id=?",(doc_id,))
        d=self.get_document(doc_id)
        if not d.archived:
            for c in self.get_chunks(doc_id,d.current_version):
                self._execute("INSERT INTO chunks_fts VALUES(?,?,?,?,?)",(doc_id,c.version,c.chunk_id,d.org_id," ".join(tokens(c.text))))
    def keyword_search(self,query,org_id,limit=100):
        ts=tokens(query)
        # For multi-character CJK queries, bigrams avoid matching unrelated words
        # merely because they share one character. Single-character queries still work.
        if re.search(r"[\u3400-\u9fff]{2}",query):
            ts=[t for t in ts if not re.fullmatch(r"[\u3400-\u9fff]",t)]
        if not ts: return []
        # Query syntax is never passed through: only individually quoted tokens.
        match=" OR ".join('"'+t.replace('"','""')+'"' for t in ts[:64])
        return self._execute("SELECT doc_id,version,chunk_id,bm25(chunks_fts) FROM chunks_fts WHERE chunks_fts MATCH ? AND org_id=? ORDER BY bm25(chunks_fts) LIMIT ?",(match,org_id,limit))
    def mark_pending(self,doc_id,pending=True):
        if pending: self._execute("INSERT OR IGNORE INTO pending_indexes VALUES(?)",(doc_id,))
        else: self._execute("DELETE FROM pending_indexes WHERE doc_id=?",(doc_id,))
    def pending_documents(self): return [r[0] for r in self._execute("SELECT doc_id FROM pending_indexes ORDER BY doc_id")]

    @staticmethod
    def _binding_data(data):
        value=decode(json.loads(data))
        return value['binding'] if isinstance(value,dict) and 'binding' in value else value

    def put_binding(self,actor,binding,*,agent=None,purpose='read'):
        data=json.dumps({'binding':encode(binding),'actor':encode(actor),'agent':encode(agent),'purpose':purpose},sort_keys=True)
        self._execute("INSERT INTO consumer_bindings VALUES(?,?,?,?,?) ON CONFLICT(org_id,user_id,consumer_type,consumer_id) DO UPDATE SET data=excluded.data",
                      (actor.org_id,actor.user_id,binding.consumer_type,binding.consumer_id,data))

    def get_binding(self,actor,consumer_type,consumer_id):
        rows=self._execute('SELECT data FROM consumer_bindings WHERE org_id=? AND user_id=? AND consumer_type=? AND consumer_id=?',
                           (actor.org_id,actor.user_id,consumer_type,consumer_id))
        if not rows:raise NotFoundError('Binding not found')
        return self._binding_data(rows[0][0])

    def list_bindings(self,actor):
        return [self._binding_data(row[0]) for row in self._execute(
            'SELECT data FROM consumer_bindings WHERE org_id=? AND user_id=? ORDER BY consumer_type,consumer_id',(actor.org_id,actor.user_id))]

    def binding_identity(self,org_id,user_id,consumer_type,consumer_id):
        rows=self._execute('SELECT data FROM consumer_bindings WHERE org_id=? AND user_id=? AND consumer_type=? AND consumer_id=?',
                           (org_id,user_id,consumer_type,consumer_id))
        if not rows:raise NotFoundError('Binding not found')
        value=decode(json.loads(rows[0][0]))
        if isinstance(value,dict) and 'binding' in value:return value.get('actor'),value.get('agent'),value.get('purpose','read')
        return None,None,'read'

    def put_anchors(self,anchors):
        from ..contracts.anchors import EvidenceAnchor
        with self._write_scope():
            for anchor in anchors:
                if not isinstance(anchor,EvidenceAnchor):raise ValidationError('Expected EvidenceAnchor')
                if self.get_document(anchor.doc_id).org_id!=anchor.org_id:raise ConflictError('Anchor tenant mismatch')
                self._execute('INSERT INTO evidence_anchors VALUES(?,?,?,?,?,?,?)',
                    (anchor.anchor_id,anchor.org_id,anchor.doc_id,anchor.version,anchor.selector_kind.value,anchor.reanchor_status.value,self._dump(anchor)))
    def get_anchors(self,org_id,doc_id,version):
        return [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM evidence_anchors WHERE org_id=? AND doc_id=? AND version=? ORDER BY anchor_id',(org_id,doc_id,version))]
    def get_anchor(self,org_id,doc_id,version,anchor_id):
        return self._get('SELECT data FROM evidence_anchors WHERE org_id=? AND doc_id=? AND version=? AND anchor_id=?',(org_id,doc_id,version,anchor_id))
    def update_anchor(self,anchor):
        from ..contracts.anchors import EvidenceAnchor
        if not isinstance(anchor,EvidenceAnchor):raise ValidationError('Expected EvidenceAnchor')
        with self._write_scope():
            self.get_anchor(anchor.org_id,anchor.doc_id,anchor.version,anchor.anchor_id)
            self._execute('UPDATE evidence_anchors SET selector_kind=?,reanchor_status=?,data=? WHERE org_id=? AND doc_id=? AND version=? AND anchor_id=?',
                (anchor.selector_kind.value,anchor.reanchor_status.value,self._dump(anchor),anchor.org_id,anchor.doc_id,anchor.version,anchor.anchor_id))
    def put_policy_rule(self,rule):
        from ..contracts.policy import PolicyRule
        if not isinstance(rule,PolicyRule):raise ValidationError('Expected PolicyRule')
        with self._write_scope():
            rows=self._execute('SELECT org_id FROM policy_rules WHERE rule_id=?',(rule.rule_id,))
            if rows and rows[0][0]!=rule.org_id:raise ConflictError('Policy identity conflict')
            self._execute('INSERT INTO policy_rules VALUES(?,?,?,?,?,?,?) ON CONFLICT(rule_id) DO UPDATE SET scope_kb_id=excluded.scope_kb_id,scope_doc_id=excluded.scope_doc_id,priority=excluded.priority,effect=excluded.effect,data=excluded.data',
                (rule.rule_id,rule.org_id,rule.scope_kb_id,rule.scope_doc_id,rule.priority,rule.effect.value,self._dump(rule)))
    def list_policy_rules(self,org_id):
        return [decode(json.loads(r[0])) for r in self._execute('SELECT data FROM policy_rules WHERE org_id=? ORDER BY priority,rule_id',(org_id,))]
    def delete_policy_rule(self,org_id,rule_id):self._execute('DELETE FROM policy_rules WHERE org_id=? AND rule_id=?',(org_id,rule_id))
    def keyword_search_pushdown(self,query,org_id,limit=100,*,kb_ids=None,doc_ids=None,space_types=None):
        ts=tokens(query)
        if re.search(r"[\u3400-\u9fff]{2}",query):ts=[t for t in ts if not re.fullmatch(r"[\u3400-\u9fff]",t)]
        if not ts:return []
        match=' OR '.join('"'+t.replace('"','""')+'"' for t in ts[:64])
        sql='SELECT chunks_fts.doc_id,version,chunk_id,bm25(chunks_fts) FROM chunks_fts JOIN documents d ON chunks_fts.doc_id=d.doc_id WHERE chunks_fts MATCH ? AND d.org_id=? AND chunks_fts.org_id=? AND d.archived=0 AND d.revoked=0'
        args=[match,org_id,org_id]
        for column,values in (('kb_id',kb_ids),('doc_id',doc_ids),('space_type',space_types)):
            if values is not None:
                if isinstance(values,str) or not isinstance(values,(list,tuple,set,frozenset)) or any(not isinstance(v,str) for v in values):raise ValidationError('Invalid pushdown scope')
                if not values:return []
                sql+=' AND d.'+column+' IN ('+','.join('?' for _ in values)+')';args.extend(values)
        sql+=' ORDER BY bm25(chunks_fts),chunks_fts.doc_id,version,chunk_id LIMIT ?';args.append(limit)
        return self._execute(sql,args)

    def put_issue(self,issue):
        from ..contracts.issues import EvidenceIssue
        if not isinstance(issue,EvidenceIssue):raise ValidationError('Expected EvidenceIssue')
        with self._write_scope():
            if self.get_document(issue.doc_id).org_id!=issue.org_id:raise ConflictError('Issue tenant mismatch')
            self.get_version(issue.doc_id,issue.version)
            if issue.anchor_id:self.get_anchor(issue.org_id,issue.doc_id,issue.version,issue.anchor_id)
            existing=self._execute('SELECT org_id,doc_id,version,anchor_id FROM evidence_issues WHERE issue_id=?',(issue.issue_id,))
            if existing and tuple(existing[0])!=(issue.org_id,issue.doc_id,issue.version,issue.anchor_id):raise ConflictError('Issue identity conflict')
            self._execute('INSERT INTO evidence_issues VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(issue_id) DO UPDATE SET status=excluded.status,created_at=excluded.created_at,data=excluded.data',
                (issue.issue_id,issue.org_id,issue.doc_id,issue.version,issue.anchor_id,issue.status,issue.created_at,self._dump(issue)))
    def get_issue(self,org_id,issue_id):
        from ..contracts.issues import issue_text
        issue_text(org_id,'org_id',True);issue_text(issue_id,'issue_id',True)
        return self._get('SELECT data FROM evidence_issues WHERE org_id=? AND issue_id=?',(org_id,issue_id))
    def list_issues(self,org_id,*,doc_id=None,status=None):
        from ..contracts.issues import issue_text,ISSUE_STATUSES
        issue_text(org_id,'org_id',True)
        sql='SELECT data FROM evidence_issues WHERE org_id=?';args=[org_id]
        if doc_id is not None:issue_text(doc_id,'doc_id',True);sql+=' AND doc_id=?';args.append(doc_id)
        if status is not None:
            if not isinstance(status,str) or status not in ISSUE_STATUSES:raise ValidationError('Invalid status')
            sql+=' AND status=?';args.append(status)
        return [decode(json.loads(row[0])) for row in self._execute(sql+' ORDER BY created_at,issue_id',args)]

    @staticmethod
    def _audit_from_row(row):
        return decode(json.loads(row[-1]))

    def append_audit_event(self,event):
        from dataclasses import replace
        from ..contracts.audit import AuditEvent,audit_hash
        from ..audit.ledger import COLUMNS
        if not isinstance(event,AuditEvent):raise ValidationError('Expected AuditEvent')
        with self._write_scope():
            rows=self._execute('SELECT seq_no,event_hash FROM audit_events WHERE org_id=? ORDER BY seq_no DESC LIMIT 1',(event.org_id,))
            seq,previous=(rows[0][0]+1,rows[0][1]) if rows else (1,'0'*64)
            event=replace(event,seq_no=seq,prev_hash=previous)
            event=replace(event,event_hash=audit_hash(event))
            values=event.to_dict()
            self._execute('INSERT INTO audit_events VALUES('+','.join('?' for _ in range(17))+')',
                          tuple(values[c] for c in COLUMNS)+(self._dump(event),))
        return event

    def list_audit_events(self,org_id,*,doc_id=None,actor_id=None,action=None,since=None,until=None,limit=100):
        from ..contracts.policy import parse_time
        if type(limit) is not int or not 1<=limit<=1000:raise ValidationError('Invalid audit limit')
        sql='SELECT data FROM audit_events WHERE org_id=?';args=[org_id]
        for name,value in (('doc_id',doc_id),('actor_id',actor_id),('action',action)):
            if value is not None:sql+=' AND '+name+'=?';args.append(value)
        for op,value in (('>=',since),('<=',until)):
            if value is not None:
                parse_time(value);sql+=' AND julianday(occurred_at)'+op+'julianday(?)';args.append(value)
        args.append(limit)
        return [decode(json.loads(r[0])) for r in self._execute(sql+' ORDER BY seq_no LIMIT ?',args)]

    def iter_audit_chain(self,org_id,from_seq=1,to_seq=None):
        sql='SELECT * FROM audit_events WHERE org_id=? AND seq_no>=?';args=[org_id,from_seq]
        if to_seq is not None:sql+=' AND seq_no<=?';args.append(to_seq)
        return iter(self._execute(sql+' ORDER BY seq_no',args))

    def enqueue_outbox(self,event):
        from ..contracts.events import OutboxEvent
        if not isinstance(event,OutboxEvent):raise ValidationError('Expected OutboxEvent')
        if event.status!='pending' or event.attempts!=0:raise ValidationError('New outbox event must be pending')
        with self._write_scope():
            rows=self._execute('SELECT * FROM outbox_events WHERE event_id=?',(event.event_id,))
            if rows:
                old=self._outbox_from_row(rows[0])
                if (old.org_id,old.aggregate_type,old.aggregate_id,old.event_type,old.payload)!=(event.org_id,event.aggregate_type,event.aggregate_id,event.event_type,event.payload):
                    raise ConflictError('Outbox identity conflict')
                return
            self._execute('INSERT INTO outbox_events VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (event.event_id,event.org_id,event.aggregate_type,event.aggregate_id,event.event_type,json.dumps(dict(event.payload),sort_keys=True),event.status,event.attempts,event.available_at,event.created_at,event.dispatched_at))

    @staticmethod
    def _outbox_from_row(row):
        from ..contracts.events import OutboxEvent
        return OutboxEvent(*row[:5],payload=json.loads(row[5]),status=row[6],attempts=row[7],available_at=row[8],created_at=row[9],dispatched_at=row[10])

    def claim_outbox_batch(self,now_iso,limit=50,*,org_id=None):
        from datetime import timedelta
        from ..contracts.policy import parse_time
        if type(limit) is not int or not 1<=limit<=1000:raise ValidationError('Invalid outbox limit')
        lease=(parse_time(now_iso)+timedelta(seconds=60)).isoformat()
        with self._write_scope():
            sql="SELECT * FROM outbox_events WHERE status IN ('pending','failed','processing') AND julianday(available_at)<=julianday(?)"
            args=[now_iso]
            if org_id is not None:sql+=' AND org_id=?';args.append(org_id)
            rows=self._execute(sql+' ORDER BY created_at,event_id LIMIT ?',args+[limit])
            events=[]
            for row in rows:
                self._execute("UPDATE outbox_events SET status='processing',attempts=attempts+1,available_at=? WHERE event_id=?",(lease,row[0]))
                events.append(self._outbox_from_row(self._execute('SELECT * FROM outbox_events WHERE event_id=?',(row[0],))[0]))
            return events

    def mark_outbox_dispatched(self,event_id,dispatched_at):
        self._execute("UPDATE outbox_events SET status='dispatched',dispatched_at=? WHERE event_id=? AND status='processing'",(dispatched_at,event_id))

    def mark_outbox_failed(self,event_id,next_available_at,max_attempts=5):
        self._execute("UPDATE outbox_events SET status=CASE WHEN attempts>=? THEN 'dead_letter' ELSE 'failed' END,available_at=? WHERE event_id=? AND status='processing'",(max_attempts,next_available_at,event_id))

    def put_webhook_subscription(self,sub):
        from ..contracts.events import WebhookSubscription
        if not isinstance(sub,WebhookSubscription):raise ValidationError('Expected WebhookSubscription')
        with self._write_scope():
            old=self._execute('SELECT org_id FROM webhook_subscriptions WHERE subscription_id=?',(sub.subscription_id,))
            if old and old[0][0]!=sub.org_id:raise ConflictError('Webhook tenant mismatch')
            self._execute('INSERT INTO webhook_subscriptions VALUES(?,?,?,?,?) ON CONFLICT(subscription_id) DO UPDATE SET event_types=excluded.event_types,active=excluded.active,data=excluded.data',
                (sub.subscription_id,sub.org_id,json.dumps(sub.event_types),int(sub.active),self._dump(sub)))

    def list_webhook_subscriptions(self,org_id,*,active_only=True):
        sql='SELECT data FROM webhook_subscriptions WHERE org_id=?'
        if active_only:sql+=' AND active=1'
        return [decode(json.loads(r[0])) for r in self._execute(sql+' ORDER BY subscription_id',(org_id,))]

    def record_webhook_delivery(self,delivery):
        from ..contracts.events import WebhookDelivery
        if not isinstance(delivery,WebhookDelivery):raise ValidationError('Expected WebhookDelivery')
        with self._write_scope():
            subscriptions=self._execute('SELECT org_id FROM webhook_subscriptions WHERE subscription_id=?',(delivery.subscription_id,))
            events=self._execute('SELECT org_id FROM outbox_events WHERE event_id=?',(delivery.outbox_event_id,))
            if not subscriptions or not events or subscriptions[0][0]!=delivery.org_id or events[0][0]!=delivery.org_id:
                raise ConflictError('Webhook delivery tenant mismatch')
            # Retrying a failed attempt updates the one logical delivery; a success
            # is immutable so replay cannot reset it or trigger another POST.
            self._execute("INSERT INTO webhook_deliveries VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(subscription_id,outbox_event_id) DO UPDATE SET status=excluded.status,http_status=excluded.http_status,attempted_at=excluded.attempted_at,data=excluded.data WHERE webhook_deliveries.status!='delivered'",
                (delivery.delivery_id,delivery.org_id,delivery.subscription_id,delivery.outbox_event_id,delivery.status,delivery.http_status,delivery.attempted_at,self._dump(delivery)))

    def has_webhook_delivery(self,subscription_id,outbox_event_id):
        return bool(self._execute("SELECT 1 FROM webhook_deliveries WHERE subscription_id=? AND outbox_event_id=? AND status='delivered'",(subscription_id,outbox_event_id)))

    def put_usage_event(self,event,*,actor=None,agent=None):
        from ..contracts.impact import UsageEvent
        if not isinstance(event,UsageEvent):raise ValidationError('Expected UsageEvent')
        if actor is not None and (actor.org_id,actor.user_id)!=(event.org_id,event.actor_id):raise ConflictError('Usage identity mismatch')
        if agent is not None and (agent.org_id,agent.agent_id)!=(event.org_id,event.agent_id):raise ConflictError('Usage agent mismatch')
        with self._write_scope():
            data=json.dumps({'event':encode(event),'actor':encode(actor),'agent':encode(agent)},sort_keys=True)
            rows=self._execute('SELECT data FROM usage_events WHERE usage_id=?',(event.usage_id,))
            if rows:
                old=decode(json.loads(rows[0][0]))
                if old.get('event')!=event or (actor is not None and old.get('actor')!=actor) or (agent is not None and old.get('agent')!=agent):raise ConflictError('Usage events are immutable')
                return
            document=self.get_document(event.doc_id)
            if document.org_id!=event.org_id:raise ConflictError('Usage tenant mismatch')
            self.get_version(event.doc_id,event.version)
            if event.anchor_id:self.get_anchor(event.org_id,event.doc_id,event.version,event.anchor_id)
            self._execute('INSERT INTO usage_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (event.usage_id,event.org_id,event.doc_id,event.version,event.anchor_id,event.consumer_type,event.consumer_id,event.task_id,event.actor_id,event.agent_id,event.purpose,event.receipt_hash,event.created_at,data))

    def list_usage_events_for_doc(self,org_id,doc_id,*,version=None):
        sql='SELECT data FROM usage_events WHERE org_id=? AND doc_id=?';args=[org_id,doc_id]
        if version is not None:sql+=' AND version=?';args.append(version)
        return [decode(json.loads(r[0]))['event'] for r in self._execute(sql+' ORDER BY created_at,usage_id',args)]

    def usage_identity(self,org_id,usage_id):
        rows=self._execute('SELECT data FROM usage_events WHERE org_id=? AND usage_id=?',(org_id,usage_id))
        if not rows:raise NotFoundError('Usage not found')
        data=decode(json.loads(rows[0][0]));return data.get('actor'),data.get('agent')

    def put_impact_alert(self,alert,*,actor_id='',usage_id=''):
        from ..contracts.impact import ImpactAlert
        if not isinstance(alert,ImpactAlert):raise ValidationError('Expected ImpactAlert')
        data=json.dumps({'alert':encode(alert),'actor_id':actor_id,'usage_id':usage_id},sort_keys=True)
        with self._write_scope():
            if self.get_document(alert.doc_id).org_id!=alert.org_id:raise ConflictError('Impact tenant mismatch')
            rows=self._execute('SELECT org_id,aggregate_id,payload_json FROM outbox_events WHERE event_id=?',(alert.source_event_id,))
            if not rows or rows[0][0]!=alert.org_id or json.loads(rows[0][2]).get('doc_id')!=alert.doc_id:
                raise ConflictError('Impact event mismatch')
            self._execute('INSERT INTO impact_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(org_id,source_event_id,target_type,target_id) DO NOTHING',
                (alert.alert_id,alert.org_id,alert.source_event_id,alert.doc_id,alert.source_version,alert.target_type,alert.target_id,alert.impact_reason.value,alert.status,alert.created_at,data))

    def list_impact_alerts(self,org_id,*,doc_id=None,status=None,target_id=None):
        if status is not None and status not in ('open','acknowledged','resolved'):raise ValidationError('Invalid impact status')
        sql='SELECT data,status FROM impact_alerts WHERE org_id=?';args=[org_id]
        for name,value in (('doc_id',doc_id),('status',status),('target_id',target_id)):
            if value is not None:sql+=' AND '+name+'=?';args.append(value)
        from dataclasses import replace
        return [replace(decode(json.loads(r[0]))['alert'],status=r[1]) for r in self._execute(sql+' ORDER BY created_at,alert_id',args)]

    def impact_owner(self,org_id,alert_id):
        rows=self._execute('SELECT data FROM impact_alerts WHERE org_id=? AND alert_id=?',(org_id,alert_id))
        if not rows:raise NotFoundError('Impact alert not found')
        return json.loads(rows[0][0]).get('actor_id','')

    def update_impact_alert_status(self,org_id,alert_id,status):
        if status not in ('open','acknowledged','resolved'):raise ValidationError('Invalid impact status')
        with self._write_scope():
            self.impact_owner(org_id,alert_id)
            self._execute('UPDATE impact_alerts SET status=? WHERE org_id=? AND alert_id=?',(status,org_id,alert_id))

    def list_all_bindings(self,org_id):
        return [(r[0],self._binding_data(r[1])) for r in self._execute('SELECT user_id,data FROM consumer_bindings WHERE org_id=? ORDER BY user_id,consumer_type,consumer_id',(org_id,))]

    @contextmanager
    def outbox_processing_scope(self,event):
        with self._write_scope():
            rows=self._execute("SELECT 1 FROM outbox_events WHERE org_id=? AND event_id=? AND status='processing' AND attempts=?",(event.org_id,event.event_id,event.attempts))
            yield bool(rows)

    def list_reserved_pack_records(self,org_id):
        return self._execute('SELECT pack_id,data FROM evidence_packs WHERE org_id=?',(org_id,))

    def mark_reserved_pack_impacted(self,org_id,pack_id):
        self._execute("UPDATE evidence_packs SET status='impacted' WHERE org_id=? AND pack_id=?",(org_id,pack_id))
