"""Owner-authorized, isolated nonproduction JSON v2 minimum runtime.

Exactly eight routes. Explicit schema upgrade and trusted issuer configuration are
required; no startup migration, jobs endpoint, scheduler or production cutover.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
from fastapi import Request
from fastapi.responses import JSONResponse
from ..contracts.models import KnowledgeScope,KnowledgeRef
from ..contracts.uri import parse_uri_v2,build_uri
from ..contracts.v2_json import loads,validate
from ..contracts.policy import PolicyAction
from ..exceptions import ValidationError,PermissionDeniedError,NotFoundError,ConflictError,TamperedExcerptError
from ..storage.migration_v6 import require_v6,version_id
from ..storage.persistent_contracts import PersistentIdempotencyStore
from ..storage import v2_metadata
from .v2_auth import authenticate,current_identity,WireError

ROUTES=(('POST','/v2/spaces'),('GET','/v2/spaces'),('GET','/v2/spaces/{kb_id}'),
        ('POST','/v2/assets'),('GET','/v2/assets/{doc_id}'),('POST','/v2/assets/{doc_id}:rollback'),
        ('POST','/v2/retrieval:search'),('POST','/v2/citations:verify'))


def mount_v2(app,client,secret,fallback_secrets,replay_store,issuer):
    require_v6(client.store)
    if type(issuer) is not str or not issuer.strip():raise ValidationError('Explicit trusted v2 issuer required')

    def space(kb):
        fields=v2_metadata.current(client.store,kb.org_id,kb.kb_id)
        return dict(kb_id=kb.kb_id,tenant_id=kb.org_id,name=kb.name,space_type=kb.space_type or {'private':'personal','team':'department','enterprise':'enterprise_public'}[kb.visibility],
                    visibility=kb.visibility,governance_tier=kb.governance_tier,owner_user_id=kb.owner_user_id or kb.owner_id,
                    owner_department_id=kb.owner_department_id,description=fields.get('description',''),tags=fields.get('tags',[]),
                    status=fields.get('status','active'),metadata=fields.get('metadata',{}),created_at=fields.get('created_at',''),updated_at=fields.get('updated_at',''))

    def draft_receipt_authority(actor,doc_id,created_version,ctx):
        d=client.store.get_document(doc_id);kb=client.store.get_kb(d.kb_id)
        version=client.store.get_version(doc_id,created_version)
        if kb.governance_tier!='l2_controlled' or version.lifecycle_state!='draft' or version.author_id!=actor.user_id:
            raise PermissionDeniedError()
        # This is a receipt for this user's submitted bytes (or an already
        # read-authorized rollback source), NOT an unpublished content read API.
        # Re-authorize WRITE including per-document ACL/rights/explicit Deny.
        decision=client.evaluate_policy(actor,doc_id,action=PolicyAction.WRITE_DOCUMENT,**ctx)
        if not decision.allowed or decision.redaction_profile:raise PermissionDeniedError()
        return version

    def write(actor,v,rollback_from=None,ctx=None):
        if not v.raw_hash:
            v=draft_receipt_authority(actor,v.doc_id,v.version,ctx)

        d=client.store.get_document(v.doc_id)
        return dict(doc_id=v.doc_id,version=v.version,version_id=version_id(client.store,actor.org_id,v.doc_id,v.version),version_label=str(v.version),
                    filename=v.filename,raw_hash=v.raw_hash,semantic_hash=v.semantic_hash,lifecycle_state=v.lifecycle_state,
                    author_id=v.author_id,reviewer_id=v.reviewer_id,publisher_id=v.publisher_id,source_issue_id=v.source_issue_id,
                    rollback_from_version=rollback_from,created_at=v.created_at,published_at=v.published_at,hash_algorithm='sha256',
                    created_version=v.version,current_version=d.current_version,activated=v.version==d.current_version and v.lifecycle_state=='published',
                    rollback_scope='content_and_filename_only')

    async def route(request:Request):
        request_id=''
        try:
            body=await request.body()
            context=authenticate(request,body,secret,fallback_secrets,replay_store,issuer)
            request_id=context['request_id']
            with client._lock,client.store.runtime_transaction():
                require_v6(client.store)
                def identity():
                    actor,ctx,types,task_scope=current_identity(client,context)
                    request.state.actor=actor;request.state.agent=ctx['agent'];request.state.purpose=ctx['purpose']
                    return actor,ctx,types,task_scope
                actor,ctx,types,task_scope=identity()
                def check_space(kb_id,*,write_access=False,manage=False):
                    kb=client._kb(actor,kb_id,write=write_access,admin=manage,**ctx)
                    if types and kb.space_type not in types:raise PermissionDeniedError('PERMISSION_DENIED')
                    if task_scope is not None:
                        if task_scope.mode=='none':raise PermissionDeniedError()
                        if task_scope.mode=='spaces' and ((task_scope.kb_ids and kb_id not in task_scope.kb_ids) or (task_scope.space_types and kb.space_type not in task_scope.space_types)):raise PermissionDeniedError()
                        if task_scope.mode=='documents' and not any(d.kb_id==kb_id and d.org_id==actor.org_id and d.doc_id in task_scope.doc_ids for d in client.store.list_documents(actor.org_id)):raise PermissionDeniedError()
                    return kb
                def check_doc(doc_id):
                    d=client.store.get_document(doc_id)
                    if d.org_id!=actor.org_id:raise PermissionDeniedError('PERMISSION_DENIED')
                    kb=check_space(d.kb_id)
                    if task_scope is not None and not task_scope.contains(d,kb):raise PermissionDeniedError()
                    return d
                if request.url.query:raise ValidationError()
                payload=loads(body) if body else None
                path=request.scope['route'].path
                method=request.method
                result=None;schema=None
                if path=='/v2/spaces' and method=='POST':
                    validate('KnowledgeBase',payload)
                    if task_scope is not None and task_scope.mode!='all_authorized':raise PermissionDeniedError()
                    if payload['tenant_id']!=actor.org_id:raise PermissionDeniedError('PERMISSION_DENIED')
                    if types and payload['space_type'] not in types:raise PermissionDeniedError('PERMISSION_DENIED')
                    if payload['status']!='active':raise WireError(409,'LIFECYCLE_CONFLICT')
                    # Replaying an exact response never bypasses current space rights.
                    def authorize():
                        identity()
                        from ..contracts.models import KnowledgeBase
                        proposed=KnowledgeBase(payload['kb_id'],actor.org_id,payload['name'],actor.user_id,payload['visibility'],payload['space_type'],payload['owner_department_id'],payload['owner_user_id'],governance_tier=payload['governance_tier'])
                        decision=client.policy_engine.evaluate(actor,ctx['agent'],proposed,action=PolicyAction.MANAGE_SPACE,purpose=ctx['purpose'],context=ctx['policy_context'])
                        if not decision.allowed:raise PermissionDeniedError('PERMISSION_DENIED')
                        try:existing=client.store.get_kb(payload['kb_id'])
                        except NotFoundError:return
                        if existing.org_id!=actor.org_id:raise PermissionDeniedError('PERMISSION_DENIED')
                        check_space(existing.kb_id,manage=True)
                    def mutate():
                        kb=client.create_kb(actor,payload['name'],payload['visibility'],payload['kb_id'],space_type=payload['space_type'],owner_department_id=payload['owner_department_id'],owner_user_id=payload['owner_user_id'],governance_tier=payload['governance_tier'],**ctx)
                        v2_metadata.set_current(client.store,actor.org_id,kb.kb_id,{k:payload[k] for k in ('description','tags','status','metadata','created_at','updated_at')})
                        return validate('KnowledgeBase',space(kb))
                    key=request.headers.get('idempotency-key')
                    if key is not None:
                        if not 1<=len(key)<=256:raise ValidationError()
                        result=PersistentIdempotencyStore(client.store,actor.org_id).execute(method,path,key,dict(actor=actor.user_id,agent=context.get('agent',{}).get('agent_id'),purpose=context['purpose'],payload=payload),authorize=authorize,mutate=mutate)
                    else:authorize();result=mutate()
                    schema='KnowledgeBase'
                elif path=='/v2/spaces':
                    if body or request.url.query:raise ValidationError()
                    result=[]
                    for kb in client.list_kbs(actor,**ctx):
                        try:check_space(kb.kb_id)
                        except PermissionDeniedError:continue
                        result.append(space(kb))
                    for item in result:validate('KnowledgeBase',item)
                elif path=='/v2/spaces/{kb_id}':
                    if body or request.url.query:raise ValidationError()
                    result=space(check_space(request.path_params['kb_id']));schema='KnowledgeBase'
                elif path=='/v2/assets':
                    validate('AssetIngestRequest',payload)
                    if request.url.query:raise ValidationError()
                    check_space(payload['kb_id'],write_access=True)
                    key=request.headers.get('idempotency-key')
                    if key is not None and (not 1<=len(key)<=256 or payload['idempotency_key'] not in ('',key)):raise ValidationError()
                    # Legacy body key is not inferred as a header/retry authorization.
                    def authorize():
                        identity();check_space(payload['kb_id'],write_access=True)
                    def mutate():
                        v=client.ingest(actor,payload['kb_id'],payload['content'],payload['filename'],metadata={'asset_type':payload['asset_type']},**ctx)
                        return validate('DocumentWriteResponse',write(actor,v,ctx=ctx))
                    result=(PersistentIdempotencyStore(client.store,actor.org_id).execute(method,path,key,dict(actor=actor.user_id,agent=context.get('agent',{}).get('agent_id'),purpose=context['purpose'],payload=payload),authorize=authorize,mutate=mutate) if key is not None else mutate())
                    # Exact replay still passes fresh document-specific Deny/redaction.
                    if result['lifecycle_state']=='draft':
                        fresh=draft_receipt_authority(actor,result['doc_id'],result['created_version'],ctx)
                    else:
                        _,fresh,_,_,_=client._delivered_source(actor,result['doc_id'],result['created_version'],**ctx)
                    if fresh.filename!=result['filename']:raise PermissionDeniedError()
                    schema='DocumentWriteResponse'
                elif path=='/v2/assets/{doc_id}':
                    if body or request.url.query:raise ValidationError()
                    d=check_doc(request.path_params['doc_id'])
                    d=client.get_document(actor,d.doc_id,**ctx)
                    result=dict(doc_id=d.doc_id,tenant_id=d.org_id,kb_id=d.kb_id,owner_id=d.owner_id,title=d.title,
                                asset_type=d.metadata.get('asset_type','document'),source_kind=d.metadata.get('source_kind','upload'),source_ref=d.metadata.get('source_ref',''),
                                visibility=d.visibility,current_version=d.current_version,current_version_id=version_id(client.store,actor.org_id,d.doc_id,d.current_version),
                                lifecycle_state=d.lifecycle_state,archived=d.archived,archived_at=None,tags=d.metadata.get('tags',[]),metadata=d.metadata,
                                domain_metadata=d.metadata.get('domain_metadata',{'schema_ref':None,'payload':{}}),valid_from=d.valid_from,valid_to=d.valid_to)
                    schema='KnowledgeAsset'
                elif path=='/v2/assets/{doc_id}:rollback':
                    validate('RollbackRequest',payload);d=check_doc(request.path_params['doc_id'])
                    v=client.rollback_document(actor,d.doc_id,payload['target_version'],**ctx)
                    result=write(actor,v,payload['target_version'],ctx=ctx);schema='DocumentWriteResponse'
                elif path=='/v2/retrieval:search':
                    validate('SearchRequest',payload)
                    raw_scope=payload['scope'];scope=KnowledgeScope('all_authorized' if raw_scope['mode']=='all' else raw_scope['mode'],raw_scope.get('kb_ids',()),raw_scope.get('space_types',()),raw_scope.get('doc_ids',()))
                    filters=payload['filters'];selected=[]
                    if types or task_scope is not None or filters['asset_types'] or filters['lifecycle_states']:
                        for d in client.store.list_documents(actor.org_id):
                            kb=client.store.get_kb(d.kb_id)
                            if scope.contains(d,kb) and (task_scope is None or task_scope.contains(d,kb)) and (not types or kb.space_type in types) and (not filters['asset_types'] or d.metadata.get('asset_type','document') in filters['asset_types']) and (not filters['lifecycle_states'] or d.lifecycle_state in filters['lifecycle_states']):selected.append(d.doc_id)
                        scope=KnowledgeScope('documents',doc_ids=tuple(selected)) if selected else KnowledgeScope('none')
                    from ..retrieval.strategies import resolve
                    from ..retrieval.hybrid import search
                    rr=payload['rerank'];cal=payload['calibration']
                    reranker,calibrator=resolve(rerank=rr['enabled'],reranker_id=rr['reranker_id'] if rr['enabled'] else None,min_calibrated_score=cal['min_calibrated_score'] if cal['enabled'] else None,rerank_top_k=rr['top_k'],reranker_registry=client.reranker_registry,calibrator_registry=client.calibrator_registry)
                    trace={}
                    response=search(client.store,actor,payload['query'],payload['mode'],payload['limit'],{'tags':filters['tags']},client.vector_index,client.embedder,client.excerpt_policy,scope=scope,
                                    policy_engine=client.policy_engine,redaction_registry=client.redaction_registry,reranker=reranker,calibrator=calibrator,min_calibrated_score=cal['min_calibrated_score'] if cal['enabled'] else None,rerank_top_k=rr['top_k'],trace=trace,**ctx)
                    hits=[]
                    for h in response.hits:
                        d=check_doc(h.doc_id);ranks=trace.get((h.doc_id,h.version,h.chunk_id),{})
                        hits.append(dict(doc_id=h.doc_id,kb_id=d.kb_id,version=h.version,version_id=version_id(client.store,actor.org_id,h.doc_id,h.version),chunk_id=h.chunk_id,title=h.title,
                                         score=h.score,raw_score=h.raw_score if h.raw_score is not None else h.score,rerank_score=h.rerank_score if h.rerank_score is not None else 0.0,
                                         calibrated_score=h.calibrated_score if h.calibrated_score is not None else 0.0,excerpt=h.excerpt,excerpt_hash=h.excerpt_hash,source_uri=h.source_uri,
                                         truncated=h.truncated,masking_summary=h.masking_summary,score_breakdown=dict(keyword_rank=ranks.get('keyword_rank',0),vector_rank=ranks.get('vector_rank',0),fusion_method='rrf'),hash_algorithm='sha256'))
                    result=dict(mode=response.mode,reranker_id=response.reranker_id,calibrator_id=response.calibrator_id,calibration_applied=response.calibration_applied,candidate_budget_exhausted=response.candidate_budget_exhausted,filtered_below_threshold=response.filtered_below_threshold,hits=hits)
                    schema='SearchResponse'
                elif path=='/v2/citations:verify':
                    validate('EvidenceRecord',payload)
                    if payload['tenant_id']!=actor.org_id:raise PermissionDeniedError()
                    d=check_doc(payload['doc_id']);uri=parse_uri_v2(payload['canonical_uri'])
                    if (uri.org_id,uri.doc_id,uri.version)!=(actor.org_id,d.doc_id,payload['version']) or d.kb_id!=payload['kb_id'] or (uri.anchor_id!=payload['anchor_id'] if uri.anchor_id is not None else uri.chunk_id!=payload['chunk_id'] or bool(payload['anchor_id'])):raise ValidationError()
                    if version_id(client.store,actor.org_id,d.doc_id,payload['version'])!=payload['version_id']:raise WireError(404,'ANCHOR_UNRESOLVABLE')
                    ref=KnowledgeRef(actor.org_id,d.doc_id,payload['version'],payload['canonical_uri'],[] if uri.anchor_id else [payload['chunk_id']],payload['excerpt'],payload['excerpt_hash'],payload['anchor_id'])
                    receipt=client.verify_ref(actor,ref,**ctx)
                    if receipt.status not in ('consumed','partial'):raise WireError(403,'PERMISSION_DENIED')
                    delivered,_,safe_chunks,_,summary=client._delivered_source(actor,d.doc_id,payload['version'],**ctx)
                    chunks={c.chunk_id:c for c in safe_chunks}
                    if payload['chunk_id'] not in chunks:raise WireError(404,'ANCHOR_UNRESOLVABLE')
                    chunk=chunks[payload['chunk_id']]
                    section=list(chunk.section_path)
                    locator=dict(page=0,char_start=chunk.start_offset,char_end=chunk.end_offset,table_cell=None)
                    if uri.anchor_id:
                        anchor=client.get_anchor(actor,d.doc_id,uri.anchor_id,payload['version'],**ctx)
                        if anchor.quote.exact not in chunk.text:raise WireError(404,'ANCHOR_UNRESOLVABLE')
                        if anchor.section_quote:
                            section=list(anchor.section_quote.section_path)
                            locator.update(char_start=anchor.section_quote.start_offset,char_end=anchor.section_quote.end_offset)
                        else:
                            # Geometry-only selectors have no asserted text offset.
                            locator.update(char_start=0,char_end=0,page=anchor.pdf_bbox.page_no if anchor.pdf_bbox else 0,table_cell=anchor.table_cell.cell_ref if anchor.table_cell else None)
                    if section!=payload['section_path'] or locator!=payload['locator'] or delivered.title!=payload['title']:raise ValidationError()
                    result=dict(payload,masking_summary=summary,verification_status='verified');schema='EvidenceRecord'
                else:raise WireError(404,'RESOURCE_NOT_FOUND')
                if schema:validate(schema,result)
                return JSONResponse(result)
        except WireError as exc:status,code=exc.status,exc.code
        except TamperedExcerptError:status,code=400,'TAMPERED_EXCERPT'
        except (ValidationError,ValueError,TypeError,KeyError,UnicodeError):status,code=400,'VALIDATION_ERROR'
        except PermissionDeniedError:status,code=403,'PERMISSION_DENIED'
        except NotFoundError:status,code=404,'RESOURCE_NOT_FOUND'
        except ConflictError as exc:status,code=409,'IDEMPOTENCY_CONFLICT' if str(exc)=='IDEMPOTENCY_CONFLICT' else 'CONFLICT'
        except Exception:status,code=503,'BACKEND_UNAVAILABLE'
        request.state.operation_error=code
        return JSONResponse({'error':{'code':code,'message':'Request unavailable','retryable':status==503,'request_id':request_id,'details':{}}},status_code=status)

    for method,path in ROUTES:
        app.add_api_route(path,route,methods=[method],name='v2_'+method+'_'+path,include_in_schema=True)
