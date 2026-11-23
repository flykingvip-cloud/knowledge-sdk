from __future__ import annotations
import base64
import inspect
import json
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from ..contracts.models import encode, decode
from ..server.auth import signed_headers
from .. import exceptions
from .local import LocalKnowledgeClient

# Operation table is shared with the server so transport contracts cannot silently diverge.
OPERATIONS={
    "create_kb":("POST","/v1/kbs"),"list_kbs":("GET","/v1/kbs"),
    "grant_kb_member":("POST","/v1/kbs/members"),
    "ingest":("POST","/v1/documents"),"list_documents":("GET","/v1/documents"),
    "get_document":("POST","/v1/documents/get"),"preview":("POST","/v1/documents/preview"),
    "archive":("POST","/v1/documents/archive"),"restore":("POST","/v1/documents/restore"),
    "set_document_acl":("POST","/v1/documents/acl"),"search":("POST","/v1/search"),
    "retrieve":("POST","/v1/retrieve"),"reference":("POST","/v1/references"),
    "consume":("POST","/v1/references/consume"),"batch_consume":("POST","/v1/references/batch-consume"),
    "ask":("POST","/v1/ask"), "create_ref":("POST","/v1/references/create"),
    "attach":("POST","/v1/references/attach"), "verify_ref":("POST","/v1/references/verify"),
    "verify_receipt":("POST","/v1/receipts/verify"),
    "validate_scope":("POST","/v1/scopes/validate"), "validate_binding":("POST","/v1/bindings/validate"),
    "bind_consumer":("POST","/v1/bindings"), "get_consumer_binding":("POST","/v1/bindings/get"),
    "can_manage_kb":("POST","/v1/kbs/can-manage"), "can_upload_to_kb":("POST","/v1/kbs/can-upload"),
    "reindex":("POST","/v1/reindex")}

class HttpKnowledgeClient:
    def __init__(self,base_url,auth_secret=None,dev_insecure=False,timeout=30):
        p=urlparse(base_url)
        if p.scheme not in ("http","https") or not p.netloc or p.username or p.password or p.query or p.fragment:
            raise exceptions.ValidationError("Invalid server URL")
        if not dev_insecure and (not auth_secret or len(auth_secret)<32): raise exceptions.ValidationError("Auth secret required")
        self.base_url=base_url.rstrip("/"); self.auth_secret=auth_secret; self.dev_insecure=dev_insecure; self.timeout=timeout
    def _call(self,name,actor,params):
        method,path=OPERATIONS[name]
        if name == "ask":
            if params.get("generator") is not None:
                raise exceptions.ValidationError("HTTP generators are configured server-side, never serialized")
            params.pop("generator", None)
        params=encode(params)
        if name=="ingest" and isinstance(params.get("content"),bytes):
            params["content_b64"]=base64.b64encode(params.pop("content")).decode()
        body=b""
        if method=="GET": path+="?"+urlencode({"params":json.dumps(params,separators=(",",":"))})
        else: body=json.dumps({"params":params},ensure_ascii=False,separators=(",",":")).encode()
        headers={"Content-Type":"application/json"}
        if self.dev_insecure:
            headers["X-KB-Actor"]=base64.urlsafe_b64encode(json.dumps(actor.__dict__).encode()).decode()
        else: headers.update(signed_headers(actor,self.auth_secret,method,path,body))
        req=Request(self.base_url+path,data=body if method!="GET" else None,headers=headers,method=method)
        try:
            with urlopen(req,timeout=self.timeout) as response: return decode(json.load(response))
        except HTTPError as exc:
            try: error=json.load(exc)
            except (ValueError,UnicodeDecodeError): error={}
            cls=getattr(exceptions,error.get("error",""),exceptions.KnowledgeSDKError)
            if not isinstance(cls,type) or not issubclass(cls,exceptions.KnowledgeSDKError): cls=exceptions.KnowledgeSDKError
            raise cls(error.get("message","HTTP request failed: "+str(exc.code))) from None
    def health(self):
        with urlopen(self.base_url+"/v1/health",timeout=self.timeout) as response: return json.load(response)

def _method(name):
    signature=inspect.signature(getattr(LocalKnowledgeClient,name))
    def call(self,*args,**kwargs):
        bound=signature.bind(self,*args,**kwargs); bound.apply_defaults(); values=dict(bound.arguments)
        values.pop("self"); actor=values.pop("actor")
        return self._call(name,actor,values)
    call.__name__=name; call.__signature__=signature
    call.__doc__="Remote equivalent of LocalKnowledgeClient."+name
    return call
for _name in OPERATIONS: setattr(HttpKnowledgeClient,_name,_method(_name))
