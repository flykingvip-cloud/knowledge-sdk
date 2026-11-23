from __future__ import annotations
import hashlib
import json
import urllib.request
from urllib.parse import urlparse, quote
from ..base import VectorHit
from ...exceptions import ValidationError
class QdrantIndex:
    """REST adapter. Collection provisioning/dimensions are deployment-owned."""
    def __init__(self,base_url,collection,api_key=None,timeout=15):
        parsed=urlparse(base_url)
        if parsed.scheme not in ("http","https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or not collection:
            raise ValidationError("Explicit valid Qdrant URL and collection required")
        self.base_url=base_url.rstrip("/"); self.collection=collection; self.api_key=api_key; self.timeout=timeout
    def _request(self,method,suffix,body):
        url=self.base_url+"/collections/"+quote(self.collection,safe="")+suffix
        headers={"Content-Type":"application/json"}
        if self.api_key: headers["api-key"]=self.api_key
        req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=self.timeout) as response: return json.load(response)
    def upsert(self,entries):
        points=[]
        for hit,vector in entries:
            key="{}:{}:{}".format(hit.doc_id,hit.version,hit.chunk_id)
            import uuid
            pid=str(uuid.UUID(hashlib.sha256(key.encode()).hexdigest()[:32]))
            points.append({"id":pid,"vector":vector,"payload":{"doc_id":hit.doc_id,"version":hit.version,"chunk_id":hit.chunk_id}})
        if points: self._request("PUT","/points?wait=true",{"points":points})
    def search(self,vector,limit=100):
        data=self._request("POST","/points/search",{"vector":vector,"limit":limit,"with_payload":True})
        return [VectorHit(r["payload"]["doc_id"],int(r["payload"]["version"]),r["payload"]["chunk_id"],float(r["score"])) for r in data["result"]]
    def delete_document(self,doc_id):
        self._request("POST","/points/delete?wait=true",{"filter":{"must":[{"key":"doc_id","match":{"value":doc_id}}]}})
