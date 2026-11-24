from __future__ import annotations
from ..contracts.models import SearchHit, SearchResponse
from ..contracts.uri import build_uri
from ..exceptions import NotFoundError, ValidationError, PermissionDeniedError
from ..contracts.policy import PolicyAction, Purpose, DecisionEffect
from ..permissions.engine import DefaultPolicyEngine
from ..permissions.redaction import RedactionRegistry
from ..permissions.policy import can_read
from .excerpt import make_excerpt

def search(store,actor,query,mode="keyword",limit=20,filters=None,vector_index=None,embedder=None,policy=None,keyword_weight=0.5,scope=None,additional_scope=None,*,policy_engine=None,redaction_registry=None,agent=None,purpose=Purpose.READ,policy_context=None):
    if mode not in ("keyword","vector","hybrid"): raise ValidationError("Unknown search mode")
    if not isinstance(query,str) or not 0<len(query)<=10000 or not 1<=limit<=100: raise ValidationError("Invalid search query/limit")
    if mode!="keyword" and (vector_index is None or embedder is None): raise ValidationError("Vector mode requires index and embedder")
    filters=filters if filters is not None else {}
    if not isinstance(filters,dict): raise ValidationError("Search filters must be an object")
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
    policy_engine=policy_engine if policy_engine is not None else DefaultPolicyEngine()
    redaction_registry=redaction_registry if redaction_registry is not None else RedactionRegistry()
    hits=[]
    for (doc_id,version,cid),score in sorted(candidates.items(),key=lambda p:(-p[1],p[0])):
        try:
            # Never trust vector payload text, org, ACL, version or archive flags.
            d=store.get_document(doc_id); kb=store.get_kb(d.kb_id)
            if scope is not None and not scope.contains(d,kb): continue
            if additional_scope is not None and not additional_scope.contains(d,kb): continue
            if d.current_version!=version: continue
            decision=policy_engine.evaluate(actor,agent,kb,d,store.get_acl(doc_id),store.member_role(kb.kb_id,actor.user_id),PolicyAction.SEARCH_INDEX,purpose,policy_context)
            if not decision.allowed: continue
            if any(filters.get(k) is not None and filters[k]!=getattr(d,k) for k in ("kb_id","doc_id")): continue
            if not set(filters.get("tags",[])).issubset(d.metadata.get("tags",[])): continue
            chunk=next((c for c in store.get_chunks(doc_id,version) if c.chunk_id==cid),None)
            if chunk is None: continue
            text=chunk.text; title=d.title; notice=d.metadata.get("partial_notice",""); summary=d.metadata.get("masking_summary","")
            if decision.effect == DecisionEffect.ALLOW_WITH_REDACTION:
                def mask(value): return redaction_registry.apply(value,decision.redaction_profile,purpose,{"doc_id":doc_id,"version":version})
                text,summary=mask(text); title=mask(title)[0]; notice=mask(notice)[0]
            excerpt=make_excerpt(text,policy,d.visibility=="enterprise",query=query,partial_notice=notice,masking_summary=summary)
            hits.append(SearchHit(doc_id,version,cid,title,score,source_uri=build_uri(d.org_id,doc_id,version,cid),**excerpt))
            if len(hits)>=limit: break
        except (NotFoundError,PermissionDeniedError): continue
    return SearchResponse(hits,mode)
