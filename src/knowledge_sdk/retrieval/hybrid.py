from __future__ import annotations
from ..contracts.models import SearchHit, SearchResponse
from ..contracts.uri import build_uri
from ..exceptions import NotFoundError, ValidationError
from ..permissions.policy import can_read
from .excerpt import make_excerpt

def search(store,actor,query,mode="keyword",limit=20,filters=None,vector_index=None,embedder=None,policy=None,keyword_weight=0.5):
    if mode not in ("keyword","vector","hybrid"): raise ValidationError("Unknown search mode")
    if not isinstance(query,str) or not 0<len(query)<=10000 or not 1<=limit<=100: raise ValidationError("Invalid search query/limit")
    if mode!="keyword" and (vector_index is None or embedder is None): raise ValidationError("Vector mode requires index and embedder")
    filters=filters or {}
    if set(filters)-{"kb_id","doc_id","tags"}: raise ValidationError("Unsupported search filter")
    # Weighted reciprocal rank fusion avoids comparing incompatible BM25/cosine scales.
    candidates={}; count=max(100,limit*10)
    def add(key,score): candidates[key]=candidates.get(key,0)+score
    if mode!="vector":
        for rank,(doc_id,version,cid,score) in enumerate(store.keyword_search(query,actor.org_id,count),1):
            add((doc_id,int(version),cid),(1 if mode=="keyword" else keyword_weight)/(60+rank))
    if mode!="keyword":
        for rank,hit in enumerate(vector_index.search(embedder.embed([query])[0],count),1):
            add((hit.doc_id,hit.version,hit.chunk_id),(1 if mode=="vector" else 1-keyword_weight)/(60+rank))
    hits=[]
    for (doc_id,version,cid),score in sorted(candidates.items(),key=lambda p:(-p[1],p[0])):
        try:
            # Never trust vector payload text, org, ACL, version or archive flags.
            d=store.get_document(doc_id); kb=store.get_kb(d.kb_id)
            if d.current_version!=version or not can_read(actor,kb,d,store.get_acl(doc_id),store.member_role(kb.kb_id,actor.user_id)): continue
            if any(filters.get(k) is not None and filters[k]!=getattr(d,k) for k in ("kb_id","doc_id")): continue
            if not set(filters.get("tags",[])).issubset(d.metadata.get("tags",[])): continue
            chunk=next((c for c in store.get_chunks(doc_id,version) if c.chunk_id==cid),None)
            if chunk is None: continue
            excerpt=make_excerpt(chunk.text,policy,d.visibility=="enterprise",query=query,
                                 partial_notice=d.metadata.get("partial_notice",""),masking_summary=d.metadata.get("masking_summary",""))
            hits.append(SearchHit(doc_id,version,cid,d.title,score,source_uri=build_uri(d.org_id,doc_id,version,cid),**excerpt))
            if len(hits)>=limit: break
        except NotFoundError: continue
    return SearchResponse(hits,mode)
