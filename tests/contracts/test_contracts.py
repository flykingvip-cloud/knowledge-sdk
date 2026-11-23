from __future__ import annotations
from dataclasses import replace
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.ingestion.fingerprint import sha256
from tests.helpers import ClientCase
class ContractTests(ClientCase):
    def test_uri_roundtrip(self):
        identity=("组织/a","d@1 /",2,"c#x")
        self.assertEqual(parse_uri(build_uri(*identity)),identity)
    def test_uri_rejects_unversioned(self):
        for uri in ("kb://org/a/doc/d","https://x","kb://org/a/doc/d@0"):
            with self.assertRaises(ValidationError): parse_uri(uri)
    def test_uri_requires_positive_integer(self):
        for v in (0,-1,True,1.2):
            with self.assertRaises(ValidationError): build_uri("a","b",v)
    def test_model_transport_roundtrip(self):
        response=self.c.search(self.a,"Knowledge")
        self.assertEqual(decode(encode(response)),response)
    def test_full_receipt(self):
        r=self.c.reference(self.a,self.v.doc_id)
        receipt=self.c.consume(self.a,r)
        self.assertEqual((receipt.status,receipt.evidence_kind),("consumed","document"))
    def test_excerpt_receipt(self):
        r=self.c.reference(self.a,self.v.doc_id,excerpt="Knowledge 知识库")
        self.assertEqual(self.c.consume(self.a,r).status,"partial")
    def test_forged_excerpt_matching_hash_is_rejected(self):
        r=self.c.reference(self.a,self.v.doc_id)
        with self.assertRaises(TamperedExcerptError): self.c.consume(self.a,replace(r,excerpt="fabricated",excerpt_hash=sha256("fabricated")))
    def test_forged_digest_is_rejected(self):
        r=self.c.reference(self.a,self.v.doc_id,excerpt="Knowledge")
        with self.assertRaises(TamperedExcerptError): self.c.consume(self.a,replace(r,excerpt_hash="f"*64))
    def test_forged_uri_is_rejected(self):
        r=self.c.reference(self.a,self.v.doc_id)
        with self.assertRaises(TamperedExcerptError): self.c.consume(self.a,replace(r,source_uri=build_uri("org","different",1)))
    def test_unknown_chunk_rejected(self):
        with self.assertRaises(TamperedExcerptError): self.c.reference(self.a,self.v.doc_id,chunk_ids=["missing"])
    def test_chunk_bound_excerpt(self):
        hit=self.c.search(self.a,"Knowledge").hits[0]
        r=self.c.reference(self.a,hit.doc_id,hit.version,[hit.chunk_id],hit.excerpt)
        self.assertEqual(self.c.consume(self.a,r).chunk_ids,[hit.chunk_id])
    def test_denied_and_unavailable(self):
        r=self.c.reference(self.a,self.v.doc_id)
        self.assertEqual(self.c.consume(self.other,r).status,"denied")
        self.assertEqual(self.c.consume(self.viewer,r).status,"denied")
        self.c.archive(self.a,self.v.doc_id)
        self.assertEqual(self.c.consume(self.a,r).reason_code,"archived")
    def test_missing_version_unavailable(self):
        r=self.c.reference(self.a,self.v.doc_id)
        r=replace(r,version=99,source_uri=build_uri("org",r.doc_id,99))
        self.assertEqual(self.c.consume(self.a,r).status,"unavailable")
    def test_batch(self):
        r=self.c.reference(self.a,self.v.doc_id)
        self.assertEqual([x.status for x in self.c.batch_consume(self.a,[r,r])],["consumed","consumed"])
        with self.assertRaises(ValidationError): self.c.batch_consume(self.a,[r]*101)
    def test_previous_reference_remains_verifiable(self):
        r=self.c.reference(self.a,self.v.doc_id,excerpt="Knowledge")
        self.c.ingest(self.a,self.k.kb_id,"completely revised",doc_id=self.v.doc_id)
        self.assertEqual(self.c.consume(self.a,r).status,"partial")

    def test_metadata_transport_tag_is_not_interpreted_as_a_model(self):
        metadata={"__type__":"Actor","user_id":"tagged","org_id":"not-a-claim"}
        v=self.c.ingest(self.a,self.k.kb_id,"tagged metadata",metadata=metadata)
        self.assertEqual(self.c.get_document(self.a,v.doc_id).metadata,metadata)
