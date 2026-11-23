from __future__ import annotations
import base64
import inspect
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ..contracts.models import encode, decode
from ..exceptions import KnowledgeSDKError, PermissionDeniedError, NotFoundError, ConflictError, ValidationError
from ..client.http_client import OPERATIONS
from .auth import verify_headers

def create_app(client,auth_secret=None,dev_insecure=False):
    if not dev_insecure and (not auth_secret or len(auth_secret)<32): raise ValidationError("Auth secret must contain at least 32 characters")
    app=FastAPI(title="knowledge-sdk",version="1.0.0"); seen={}
    @app.exception_handler(KnowledgeSDKError)
    async def sdk_error(request,exc):
        status=403 if isinstance(exc,PermissionDeniedError) else 404 if isinstance(exc,NotFoundError) else 409 if isinstance(exc,ConflictError) else 400
        return JSONResponse(status_code=status,content={"error":type(exc).__name__,"message":str(exc)})
    @app.middleware("http")
    async def authenticate(request,call_next):
        if request.url.path in ("/v1/health",): return await call_next(request)
        if request.url.path in ("/docs","/openapi.json","/redoc"):
            # Schema has no runtime data. Deployments may disable these at the gateway.
            return await call_next(request)
        body=await request.body()
        if len(body)>48*1024*1024: return JSONResponse(status_code=413,content={"message":"Request too large"})
        target=request.url.path+("?"+request.url.query if request.url.query else "")
        try: request.state.actor=verify_headers(request.headers,auth_secret,request.method,target,body,dev_insecure=dev_insecure,seen=seen)
        except ValidationError:
            return JSONResponse(status_code=401,content={"error":"PermissionDeniedError","message":"Invalid request authentication"})
        return await call_next(request)
    @app.get("/v1/health")
    async def health(): return client.health()
    def endpoint(operation):
        async def handle(request: Request):
            try:
                if request.method=="GET": params=decode(json.loads(request.query_params.get("params","{}")))
                else: params=decode((await request.json()).get("params",{}))
                if not isinstance(params,dict) or "actor" in params or "self" in params: raise ValidationError("Invalid parameters")
                if operation=="ingest" and "content_b64" in params:
                    params["content"]=base64.b64decode(params.pop("content_b64"),validate=True)
                method=getattr(client,operation)
                inspect.signature(method).bind(actor=request.state.actor,**params)
            except (TypeError,ValueError,KeyError) as exc: raise ValidationError("Invalid request parameters") from exc
            return encode(method(actor=request.state.actor,**params))
        handle.__name__=operation
        return handle
    for name,(verb,path) in OPERATIONS.items():
        extra={"security":[{"ActorSignature":[]}]}
        if verb!="GET":
            extra["requestBody"]={"required":True,"content":{"application/json":{"schema":{"type":"object","required":["params"],"properties":{"params":{"type":"object","description":"See docs/api-contract.md for operation parameters"}}}}}}
        app.add_api_route(path,endpoint(name),methods=[verb],operation_id=name,openapi_extra=extra)
    # Resource-oriented aliases. Same domain methods/authorization as transport operations.
    @app.get("/v1/documents/{doc_id}/versions/{version}")
    async def get_version(doc_id:str,version:int,request:Request):
        return encode(client.get_document(request.state.actor,doc_id,version))
    @app.post("/v1/documents/{doc_id}/archive")
    async def archive(doc_id:str,request:Request): return encode(client.archive(request.state.actor,doc_id))
    @app.post("/v1/documents/{doc_id}/restore")
    async def restore(doc_id:str,request:Request): return encode(client.restore(request.state.actor,doc_id))
    @app.post("/v1/documents/{doc_id}/acl")
    async def acl(doc_id:str,request:Request):
        try:
            from ..contracts.models import DocumentACL
            body=await request.json(); value=decode(body.get("acl",body))
            if isinstance(value,dict): value=DocumentACL(**value)
        except (ValueError,TypeError) as exc: raise ValidationError("Invalid ACL") from exc
        return encode(client.set_document_acl(request.state.actor,doc_id,value))
    original_openapi=app.openapi
    def openapi():
        schema=original_openapi()
        schema.setdefault("components",{}).setdefault("securitySchemes",{})["ActorSignature"]={
            "type":"apiKey","in":"header","name":"X-KB-Signature",
            "description":"HMAC-SHA256 over method, request target, Actor, timestamp, nonce and body digest; see docs/api-contract.md"}
        return schema
    app.openapi=openapi
    return app
