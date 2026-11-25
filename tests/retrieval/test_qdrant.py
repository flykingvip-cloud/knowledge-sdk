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
        with patch.object(q,"_request",return_value={"result":{"points":[]}}) as call:
            q.upsert([(VectorHit("d",1,"c",0),[0.,1.])])
            method,path,body=call.call_args[0]; self.assertEqual((method,path),("PUT","/points?wait=true"))
            self.assertEqual(body["points"][0]["payload"],{"doc_id":"d","version":1,"chunk_id":"c"})
            q.delete_document("d"); self.assertEqual(call.call_args[0][2]["filter"]["must"][0]["match"]["value"],"d")
            q.search([0.,1.]); self.assertEqual(call.call_args[0][2]["with_payload"],True)
    def test_hit_decode(self):
        q=QdrantIndex("https://vectors.example.test","c")
        with patch.object(q,"_request",return_value={"result":{"points":[{"payload":{"doc_id":"d","version":2,"chunk_id":"c"},"score":.5}]}}):
            self.assertEqual(q.search([1.])[0],VectorHit("d",2,"c",.5))

    def test_uuid_ids_stable_and_version_scoped(self):
        import uuid
        q=QdrantIndex("http://example.test","c")
        with patch.object(q,"_request") as call:
            entries=[(VectorHit("arbitrary doc",1,"chunk",0),[1.]),
                     (VectorHit("arbitrary doc",2,"chunk",0),[1.])]
            q.upsert(entries)
            first=call.call_args[0][2]["points"]
            self.assertNotEqual(first[0]["id"],first[1]["id"])
            for point in first: uuid.UUID(point["id"])
            q.upsert(entries)
            self.assertEqual(first,call.call_args[0][2]["points"])

    def test_legacy_fallback_only_missing_endpoint(self):
        from urllib.error import HTTPError
        q=QdrantIndex("http://example.test","c")
        with patch.object(q,"_request",side_effect=[HTTPError("",404,"",{},__import__("io").BytesIO()),{"result":[]}]) as call:
            self.assertEqual(q.search([1.]),[])
            self.assertEqual(call.call_args_list[0][0][1],"/points/query")
            self.assertEqual(call.call_args_list[1][0][1],"/points/search")
        for code in (401,403,400,500):
            error=HTTPError("",code,"",{},__import__("io").BytesIO())
            try:
                with patch.object(q,"_request",side_effect=error) as call:
                    with self.assertRaises(HTTPError): q.search([1.])
                    self.assertEqual(call.call_count,1)
            finally:
                error.close()

    def test_malformed_secondary_points_are_ignored(self):
        q=QdrantIndex("http://example.test","c")
        rows=[{"payload":None}, {"payload":{}},
              {"payload":{"doc_id":"d","chunk_id":"c","version":"1"},"score":1}]
        with patch.object(q,"_request",return_value={"result":{"points":rows}}):
            self.assertEqual(q.search([1.]),[])
