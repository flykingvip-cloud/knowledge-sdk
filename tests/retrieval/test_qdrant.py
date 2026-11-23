from __future__ import annotations
import unittest
from unittest.mock import patch
from knowledge_sdk.retrieval.adapters.qdrant import QdrantIndex
from knowledge_sdk.retrieval.base import VectorHit
from knowledge_sdk import ValidationError
class QdrantTests(unittest.TestCase):
    def test_explicit_configuration(self):
        for url,collection in [("","x"),("http://host",""),("file:///tmp","x"),("http://user:password@host","x")]:
            with self.assertRaises(ValidationError): QdrantIndex(url,collection)
    def test_rest_contract(self):
        q=QdrantIndex("https://vectors.example.test","my collection")
        with patch.object(q,"_request",return_value={"result":[]}) as call:
            q.upsert([(VectorHit("d",1,"c",0),[0.,1.])])
            method,path,body=call.call_args[0]; self.assertEqual((method,path),("PUT","/points?wait=true"))
            self.assertEqual(body["points"][0]["payload"],{"doc_id":"d","version":1,"chunk_id":"c"})
            q.delete_document("d"); self.assertEqual(call.call_args[0][2]["filter"]["must"][0]["match"]["value"],"d")
            q.search([0.,1.]); self.assertEqual(call.call_args[0][2]["with_payload"],True)
    def test_hit_decode(self):
        q=QdrantIndex("https://vectors.example.test","c")
        with patch.object(q,"_request",return_value={"result":[{"payload":{"doc_id":"d","version":2,"chunk_id":"c"},"score":.5}]}):
            self.assertEqual(q.search([1.])[0],VectorHit("d",2,"c",.5))
