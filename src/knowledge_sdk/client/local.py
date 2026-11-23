from __future__ import annotations
from datetime import datetime, timezone
from functools import wraps
import threading
import uuid
from ..contracts.models import (KnowledgeBase, Document, DocumentVersion, DocumentACL, KnowledgeRef, RetrieveResponse, ExcerptPolicy)
from ..contracts.uri import build_uri
from ..contracts.receipts import consume, batch_consume, validate_excerpt
from ..exceptions import PermissionDeniedError, NotFoundError, ValidationError, ConflictError
from ..permissions.policy import can_admin, can_read, can_write
from ..storage.sqlite_store import SQLiteStore
from ..ingestion.parsers import ParserRegistry
from ..ingestion.chunkers import HierarchicalChunker
from ..ingestion.fingerprint import fingerprints, classify, normalize_text, sha256
from ..retrieval.base import VectorHit
from ..retrieval.hybrid import search as run_search

def serialized(method):
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with self._lock: return method(self,*args,**kwargs)
    return wrapped

class LocalKnowledgeClient:
    """Trusted in-process API. Caller supplies an authenticated Actor, not user input."""
    def __init__(self,store=None,blob_store=None,parsers=None,chunker=None,vector_index=None,embedder=None,excerpt_policy=None):
        self.store=store if store is not None else SQLiteStore()
        self.blob_store=blob_store; self.parsers=parsers or ParserRegistry.defaults(); self.chunker=chunker or HierarchicalChunker()
        if (vector_index is None)!=(embedder is None): raise ValidationError("Provide both vector_index and embedder")
        self.vector_index=vector_index; self.embedder=embedder; self.excerpt_policy=excerpt_policy or ExcerptPolicy()
        self._lock=threading.RLock()
    def _kb(self,actor,kb_id,write=False,admin=False):
        kb=self.store.get_kb(kb_id); role=self.store.member_role(kb_id,actor.user_id)
        allowed=can_admin(actor,kb,role) if admin else (can_write(actor,kb,role) if write else can_read(actor,kb,member_role=role))
        if not allowed: raise PermissionDeniedError("Access denied")
        return kb
    def _read(self,actor,doc_id,include_archived=False):
        d=self.store.get_document(doc_id); kb=self.store.get_kb(d.kb_id)
        if not can_read(actor,kb,d,self.store.get_acl(doc_id),self.store.member_role(kb.kb_id,actor.user_id),include_archived):
            raise PermissionDeniedError("Access denied")
        return d
    @staticmethod
    def _visibility(value):
        if value not in ("private","team","enterprise"): raise ValidationError("Invalid visibility")
    @serialized
    def create_kb(self,actor,name,visibility="private",kb_id=None):
        self._visibility(visibility)
        if not isinstance(name,str) or not name.strip(): raise ValidationError("KB name required")
        kb_id=kb_id or str(uuid.uuid4())
        try: self.store.get_kb(kb_id)
        except NotFoundError: pass
        else: raise ConflictError("KB identity already exists")
        kb=KnowledgeBase(kb_id,actor.org_id,name,actor.user_id,visibility)
        with self.store.transaction():
            self.store.put_kb(kb); self.store.grant_member(kb_id,actor.user_id,"admin")
        return kb
    @serialized
    def list_kbs(self,actor):
        return [k for k in self.store.list_kbs(actor.org_id) if can_read(actor,k,member_role=self.store.member_role(k.kb_id,actor.user_id))]
    @serialized
    def grant_kb_member(self,actor,kb_id,user_id,role):
        self._kb(actor,kb_id,admin=True)
        if role not in ("viewer","editor","admin") or not user_id: raise ValidationError("Invalid member/role")
        self.store.grant_member(kb_id,user_id,role)
    def _sync_vector(self,doc_id):
        if self.vector_index is None: return
        # Durable dirty marker is cleared only after the remote index acknowledges all writes.
        self.store.mark_pending(doc_id)
        d=self.store.get_document(doc_id)
        self.vector_index.delete_document(doc_id)
        if not d.archived:
            chunks=self.store.get_chunks(doc_id,d.current_version)
            vectors=self.embedder.embed([c.text for c in chunks])
            if len(vectors)!=len(chunks): raise ValidationError("Embedder returned wrong number of vectors")
            self.vector_index.upsert([(VectorHit(c.doc_id,c.version,c.chunk_id,0),v) for c,v in zip(chunks,vectors)])
        self.store.mark_pending(doc_id,False)
    @serialized
    def ingest(self,actor,kb_id,content,filename="document.txt",title=None,visibility=None,doc_id=None,metadata=None):
        kb=self._kb(actor,kb_id,write=True)
        if not isinstance(content,(str,bytes)): raise ValidationError("content must be UTF-8 text or bytes")
        raw=content.encode("utf-8") if isinstance(content,str) else content
        if len(raw)>32*1024*1024: raise ValidationError("Document exceeds 32 MiB limit")
        text=self.parsers.parse(raw,filename)
        if not text.strip(): raise ValidationError("Empty document")
        raw_hash,semantic_hash=fingerprints(raw,text); previous=None; d=None
        if doc_id:
            try: d=self.store.get_document(doc_id)
            except NotFoundError: pass
            if d:
                if d.kb_id!=kb_id or d.org_id!=actor.org_id: raise PermissionDeniedError("Access denied")
                self._read(actor,doc_id)
                previous=self.store.get_version(doc_id,d.current_version)
        if classify(previous,raw_hash,semantic_hash)!="new_semantic_version": return previous
        visibility=visibility or (d.visibility if d else kb.visibility); self._visibility(visibility)
        doc_id=doc_id or str(uuid.uuid4()); version=previous.version+1 if previous else 1
        metadata=metadata if metadata is not None else (d.metadata if d else {})
        # JSON serializability is checked before writing any blob or DB rows.
        import json
        json.dumps(metadata)
        if not isinstance(metadata,dict): raise ValidationError("metadata must be an object")
        chunks=self.chunker.split(text,doc_id,version)
        blob_key=self.blob_store.put(actor.org_id,doc_id,raw_hash,raw) if self.blob_store else None
        d=Document(doc_id,actor.org_id,kb_id,d.owner_id if d else actor.user_id,title or (d.title if d else filename),visibility,version,False,metadata)
        v=DocumentVersion(doc_id,version,text,raw_hash,semantic_hash,datetime.now(timezone.utc).isoformat(),filename,blob_key)
        with self.store.transaction():
            # Separate processes can race; the unique version key prevents lost history.
            if previous and self.store.get_document(doc_id).current_version!=previous.version: raise ConflictError("Concurrent version update")
            if previous is None:
                try: self.store.get_document(doc_id)
                except NotFoundError: pass
                else: raise ConflictError("Document identity already exists")
            self.store.put_document(d); self.store.put_version(v,chunks); self.store.refresh_fts(doc_id)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
        return v
    @serialized
    def list_documents(self,actor,kb_id=None,include_archived=False):
        if kb_id: self._kb(actor,kb_id)
        result=[]
        for d in self.store.list_documents(actor.org_id):
            if kb_id and d.kb_id!=kb_id: continue
            try: self._read(actor,d.doc_id,include_archived); result.append(d)
            except PermissionDeniedError: pass
        return result
    @serialized
    def get_document(self,actor,doc_id,version=None):
        d=self._read(actor,doc_id)
        return self.store.get_version(doc_id,version) if version is not None else d
    @serialized
    def preview(self,actor,doc_id,version=None,limit=800):
        return self.retrieve(actor,doc_id,version,offset=0,limit=limit)
    @serialized
    def archive(self,actor,doc_id):
        d=self._read(actor,doc_id,True); self._kb(actor,d.kb_id,write=True)
        with self.store.transaction():
            d.archived=True; self.store.put_document(d); self.store.refresh_fts(doc_id)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
    @serialized
    def restore(self,actor,doc_id):
        d=self._read(actor,doc_id,True); self._kb(actor,d.kb_id,write=True)
        with self.store.transaction():
            d.archived=False; self.store.put_document(d); self.store.refresh_fts(doc_id)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
    @serialized
    def set_document_acl(self,actor,doc_id,acl):
        d=self.store.get_document(doc_id); self._kb(actor,d.kb_id,admin=True)
        if not isinstance(acl,DocumentACL): raise ValidationError("Expected DocumentACL")
        self.store.set_acl(doc_id,acl)
    @serialized
    def search(self,actor,query,mode="keyword",limit=20,filters=None):
        return run_search(self.store,actor,query,mode,limit,filters,self.vector_index,self.embedder,self.excerpt_policy)
    @serialized
    def retrieve(self,actor,doc_id,version=None,chunk_ids=None,offset=0,limit=8000):
        d=self._read(actor,doc_id); version=version if version is not None else d.current_version
        if not isinstance(version,int) or version<1 or not isinstance(offset,int) or not isinstance(limit,int) or offset<0 or not 1<=limit<=100000:
            raise ValidationError("Invalid version/pagination")
        v=self.store.get_version(doc_id,version); chunks=self.store.get_chunks(doc_id,version)
        if chunk_ids:
            selected=[c for c in chunks if c.chunk_id in chunk_ids]
            if len(set(chunk_ids))!=len(selected): raise NotFoundError("Chunk not found")
            text="\n".join(c.text for c in selected)
        else: text=v.text
        page=text[offset:offset+limit]; end=offset+len(page); truncated=end<len(text)
        return RetrieveResponse(doc_id,version,page,offset,limit,len(text),truncated,end if truncated else None,build_uri(d.org_id,doc_id,version),list(chunk_ids or []))
    @serialized
    def reference(self,actor,doc_id,version=None,chunk_ids=None,excerpt=""):
        d=self._read(actor,doc_id); version=version if version is not None else d.current_version
        v=self.store.get_version(doc_id,version); chunk_ids=list(chunk_ids or [])
        ref=KnowledgeRef(d.org_id,doc_id,version,build_uri(d.org_id,doc_id,version,chunk_ids[0] if len(chunk_ids)==1 else None),chunk_ids,excerpt,sha256(excerpt))
        validate_excerpt(ref,v,self.store.get_chunks(doc_id,version)); return ref
    @serialized
    def consume(self,actor,ref): return consume(self,actor,ref)
    @serialized
    def batch_consume(self,actor,refs): return batch_consume(self,actor,refs)
    @serialized
    def reindex(self,actor,kb_id):
        self._kb(actor,kb_id,admin=True)
        for d in self.store.list_documents(actor.org_id):
            if d.kb_id==kb_id:
                with self.store.transaction(): self.store.refresh_fts(d.doc_id)
                self._sync_vector(d.doc_id)
    @serialized
    def health(self):
        pending=self.store.pending_documents()
        return {"status":"degraded" if pending else "ok","version":"1.0.0","pending_index_count":len(pending)}
