from __future__ import annotations
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from ..contracts.models import (KnowledgeBase, Document, DocumentVersion, DocumentACL, Chunk, Actor, ConsumerBinding, encode, decode)
from ..exceptions import NotFoundError, ConflictError

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
        self.db.execute("PRAGMA foreign_keys=ON"); self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        schema=self.db.execute("PRAGMA user_version").fetchone()[0]
        if schema not in (0,1): raise ConflictError("Unsupported database schema version")
        self.db.executescript("""
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
        PRAGMA user_version=1;
        """)
    @contextmanager
    def transaction(self):
        with self.lock:
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
    def put_kb(self,kb): self._execute("INSERT INTO knowledge_bases VALUES(?,?,?)",(kb.kb_id,kb.org_id,self._dump(kb)))
    def get_kb(self,kb_id): return self._get("SELECT data FROM knowledge_bases WHERE kb_id=?",(kb_id,))
    def list_kbs(self,org_id): return [decode(json.loads(r[0])) for r in self._execute("SELECT data FROM knowledge_bases WHERE org_id=? ORDER BY kb_id",(org_id,))]
    def grant_member(self,kb_id,user_id,role):
        self._execute("INSERT INTO kb_members VALUES(?,?,?) ON CONFLICT(kb_id,user_id) DO UPDATE SET role=excluded.role",(kb_id,user_id,role))
    def member_role(self,kb_id,user_id):
        rows=self._execute("SELECT role FROM kb_members WHERE kb_id=? AND user_id=?",(kb_id,user_id)); return rows[0][0] if rows else None
    def get_document(self,doc_id): return self._get("SELECT data FROM documents WHERE doc_id=?",(doc_id,))
    def put_document(self,d):
        self._execute("INSERT INTO documents VALUES(?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET data=excluded.data",(d.doc_id,d.org_id,d.kb_id,self._dump(d)))
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
        self._execute("INSERT INTO document_acls VALUES(?,?) ON CONFLICT(doc_id) DO UPDATE SET data=excluded.data",(doc_id,self._dump(acl)))
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

    def put_binding(self, actor: Actor, binding: ConsumerBinding) -> None:
        self._execute("INSERT INTO consumer_bindings VALUES(?,?,?,?,?) ON CONFLICT(org_id,user_id,consumer_type,consumer_id) DO UPDATE SET data=excluded.data",
                      (actor.org_id, actor.user_id, binding.consumer_type, binding.consumer_id, self._dump(binding)))

    def get_binding(self, actor: Actor, consumer_type: str, consumer_id: str) -> ConsumerBinding:
        return self._get("SELECT data FROM consumer_bindings WHERE org_id=? AND user_id=? AND consumer_type=? AND consumer_id=?",
                         (actor.org_id, actor.user_id, consumer_type, consumer_id))

    def list_bindings(self, actor: Actor):
        return [decode(json.loads(row[0])) for row in self._execute(
            "SELECT data FROM consumer_bindings WHERE org_id=? AND user_id=? ORDER BY consumer_type,consumer_id",
            (actor.org_id, actor.user_id))]
