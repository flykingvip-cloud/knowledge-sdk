from __future__ import annotations
from ..contracts.models import SearchHit, SearchResponse, KnowledgeScope
from ..contracts.uri import build_uri
from ..exceptions import NotFoundError, ValidationError, PermissionDeniedError
from ..contracts.policy import PolicyAction, Purpose, DecisionEffect
from ..permissions.engine import DefaultPolicyEngine
from ..permissions.redaction import RedactionRegistry
from ..permissions.policy import can_read
from .excerpt import make_excerpt

def scope_constraints(filters,scope=None,additional_scope=None):
    """SQL narrowing only. None is unrestricted; empty intersection is empty."""
    result={'kb_ids':None,'doc_ids':None,'space_types':None}
    def narrow(key,values):
        values=set(values)
        result[key]=values if result[key] is None else result[key].intersection(values)
    for field,key in (('kb_id','kb_ids'),('doc_id','doc_ids')):
        if filters.get(field) is not None:narrow(key,[filters[field]])
    for item in (scope,additional_scope):
        if isinstance(item,KnowledgeScope):
            # Revalidate frozen values rather than infer an empty selector as all.
            item=KnowledgeScope(item.mode,item.kb_ids,item.space_types,item.doc_ids)
            if item.mode=='spaces':
                if item.kb_ids:narrow('kb_ids',item.kb_ids)
                if item.space_types:narrow('space_types',item.space_types)
            elif item.mode=='documents':narrow('doc_ids',item.doc_ids)
    return {key:None if value is None else sorted(value) for key,value in result.items()}


def search(store,actor,query,mode="keyword",limit=20,filters=None,vector_index=None,embedder=None,policy=None,keyword_weight=0.5,scope=None,additional_scope=None,*,policy_engine=None,redaction_registry=None,agent=None,purpose=Purpose.READ,policy_context=None):
    if mode not in ("keyword","vector","hybrid"): raise ValidationError("Unknown search mode")
    if not isinstance(query,str) or not 0<len(query)<=10000 or not 1<=limit<=100: raise ValidationError("Invalid search query/limit")
    if mode!="keyword" and (vector_index is None or embedder is None): raise ValidationError("Vector mode requires index and embedder")
    filters=filters if filters is not None else {}
    if not isinstance(filters,dict): raise ValidationError("Search filters must be an object")
    if set(filters)-{"kb_id","doc_id","tags"}: raise ValidationError("Unsupported search filter")
    constraints=scope_constraints(filters,scope,additional_scope)
    if any(value==[] for value in constraints.values()):return SearchResponse([],mode)
    # Prefix batches plus one identity-only lookahead; never evaluate key 501.
    policy_engine=policy_engine if policy_engine is not None else DefaultPolicyEngine()
    redaction_registry=redaction_registry if redaction_registry is not None else RedactionRegistry()
    evaluated=set();accepted={};candidates={};more=False
    vector=embedder.embed([query])[0] if mode!='keyword' else None
    batches=tuple(dict.fromkeys((min(max(limit*4,40),500),min(max(limit*12,120),500),500)))
    for batch in batches:
        candidates={};more=False
        def add(key,score):
            if (isinstance(key[0],str) and type(key[1]) is int and key[1]>=1 and isinstance(key[2],str)):
                candidates[key]=candidates.get(key,0)+score
        if mode!='vector':
            pushdown=getattr(store,'keyword_search_pushdown',None)
            if callable(pushdown):
                import inspect
                params=inspect.signature(pushdown).parameters
                kwargs={key:value for key,value in constraints.items() if key in params or any(p.kind==p.VAR_KEYWORD for p in params.values())}
                rows=pushdown(query,actor.org_id,batch+1,**kwargs)
            else:rows=store.keyword_search(query,actor.org_id,batch+1)
            more=more or len(rows)>batch
            for rank,row in enumerate(rows[:batch],1):
                try:add((row[0],int(row[1]),row[2]),(1 if mode=='keyword' else keyword_weight)/(60+rank))
                except (ValueError,TypeError,IndexError):continue
        if mode!='keyword':
            rows=vector_index.search(vector,batch+1);more=more or len(rows)>batch
            for rank,hit in enumerate(rows[:batch],1):
                try:add((hit.doc_id,hit.version,hit.chunk_id),(1 if mode=='vector' else 1-keyword_weight)/(60+rank))
                except AttributeError:continue
        for key,score in candidates.items():
            if key in accepted:
                from dataclasses import replace
                accepted[key]=replace(accepted[key],score=score)
        for (doc_id,version,cid),score in sorted(candidates.items(),key=lambda p:(-p[1],p[0])):
            key=(doc_id,version,cid)
            if key in evaluated:continue
            if len(evaluated)>=500:break
            evaluated.add(key)
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
                accepted[key]=SearchHit(doc_id,version,cid,title,score,source_uri=build_uri(d.org_id,doc_id,version,cid),**excerpt)
                if len(accepted)>=limit: break
            except (NotFoundError,PermissionDeniedError): continue
        if len(accepted)>=limit or len(evaluated)>=500 or not more:break
    hits=sorted(accepted.values(),key=lambda h:(-h.score,h.doc_id,h.version,h.chunk_id))[:limit]
    exhausted=len(hits)<limit and len(evaluated)>=500 and (more or bool(set(candidates)-evaluated))
    return SearchResponse(hits,mode,candidate_budget_exhausted=exhausted)
