from __future__ import annotations
import knowledge_sdk
import base64
import inspect
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ..contracts.models import encode, decode
from ..exceptions import KnowledgeSDKError, PermissionDeniedError, NotFoundError, ConflictError, ValidationError
from ..client.http_client import OPERATIONS
from .auth import verify_headers, InMemoryReplayStore, extension_claims, _validate_secrets

def create_app(client,auth_secret=None,dev_insecure=False,answer_generator=None,*,enable_ui=True,enable_demo_switcher=False,replay_store=None,fallback_secrets=(),ui_prefix="/ui"):
    if not dev_insecure and (not auth_secret or len(auth_secret)<32): raise ValidationError("Auth secret must contain at least 32 characters")
    if enable_demo_switcher and (dev_insecure or not auth_secret or len(auth_secret)<32):
        raise ValidationError("Demo switcher requires HMAC authentication, not dev_insecure")
    if not dev_insecure: _validate_secrets(auth_secret, fallback_secrets)
    from ..ui.routes import normalize_ui_prefix, public_ui_path, route_path
    ui_prefix = normalize_ui_prefix(ui_prefix)
    replay_store = replay_store if replay_store is not None else InMemoryReplayStore()
    app=FastAPI(title="knowledge-sdk",version=knowledge_sdk.__version__)
    @app.exception_handler(KnowledgeSDKError)
    async def sdk_error(request,exc):
        status=403 if isinstance(exc,PermissionDeniedError) else 404 if isinstance(exc,NotFoundError) else 409 if isinstance(exc,ConflictError) else 400
        return JSONResponse(status_code=status,content={"error":type(exc).__name__,"message":str(exc)})
    @app.middleware("http")
    async def authenticate(request,call_next):
        path = route_path(request)
        # Disabled signer and former/default UI paths never become auth endpoints.
        if ((not enable_ui and public_ui_path(path, ui_prefix))
            or path in ("/ui/demo/sign", ui_prefix + "/demo/sign") and not enable_demo_switcher
            or (ui_prefix != "/ui" and (path == "/ui" or path.startswith("/ui/")))):
            return JSONResponse(status_code=404, content={"message": "Not found"})
        if enable_ui and public_ui_path(path, ui_prefix):
            # Only static/config/demo routes live here. All business APIs remain signed.
            return await call_next(request)
        if path in ("/v1/health",): return await call_next(request)
        if path in ("/docs","/openapi.json","/redoc"):
            # Schema has no runtime data. Deployments may disable these at the gateway.
            return await call_next(request)
        body=await request.body()
        if len(body)>48*1024*1024: return JSONResponse(status_code=413,content={"message":"Request too large"})
        raw_path=request.scope.get("raw_path",request.url.path.encode("utf-8")).decode("ascii")
        target=raw_path+("?"+request.url.query if request.url.query else "")
        try:
            request.state.actor=verify_headers(request.headers,auth_secret,request.method,target,body,dev_insecure=dev_insecure,replay_store=replay_store,fallback_secrets=fallback_secrets)
            request.state.agent, request.state.purpose = extension_claims(request.headers, request.state.actor)
        except ValidationError:
            return JSONResponse(status_code=401,content={"error":"PermissionDeniedError","message":"Invalid request authentication"})
        return await call_next(request)
    @app.get("/v1/health")
    async def health(): return client.health()
    def endpoint(operation):
        async def handle(request: Request):
            try:
                if request.method=="GET": params=decode(json.loads(request.query_params.get("params","{}")))
                else:
                    envelope=await request.json()
                    if not isinstance(envelope,dict): raise ValidationError("Expected request object")
                    params=decode(envelope.get("params",{}))
                if not isinstance(params,dict) or "actor" in params or "self" in params: raise ValidationError("Invalid parameters")
                if operation=="ingest" and "content_b64" in params:
                    params["content"]=base64.b64decode(params.pop("content_b64"),validate=True)
                if operation == "ask":
                    if "generator" in params: raise ValidationError("Generators must be configured server-side")
                    params["generator"] = answer_generator
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
    if enable_ui:
        from ..ui.routes import mount_workbench
        mount_workbench(app, client, auth_secret, enable_demo_switcher, ui_prefix)
    return app
