from __future__ import annotations
from knowledge_sdk import *
from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
from knowledge_sdk.retrieval.base import VectorHit
from tests.helpers import ClientCase,MemoryIndex
class RetrievalTests(ClientCase):
    def test_fts5_bm25_really_runs(self):
        traced=[]; self.c.store.db.set_trace_callback(traced.append)
        self.assertTrue(self.c.search(self.a,"Knowledge").hits)
        self.assertTrue(any("bm25(" in sql and "MATCH" in sql for sql in traced))
    def test_chinese_and_mixed(self):
        self.assertTrue(self.c.search(self.a,"知识库").hits)
        self.assertTrue(self.c.search(self.a,"知识 search").hits)
    def test_fts_special_characters(self):
        for q in ['" OR NOT * : () -',"knowledge' OR 1=1; --","知识 + (search)","😀"]:
            self.c.search(self.a,q)
    def test_filter_and_invalid_mode(self):
        self.assertEqual(self.c.search(self.a,"Knowledge",filters={"kb_id":"other"}).hits,[])
        for kwargs in [{"mode":"unknown"},{"mode":"vector"},{"limit":0},{"filters":{"org_id":"other"}}]:
            with self.assertRaises(ValidationError): self.c.search(self.a,"Knowledge",**kwargs)
    def test_latest_version_only(self):
        self.c.ingest(self.a,self.k.kb_id,"replacement",doc_id=self.v.doc_id)
        self.assertEqual(self.c.search(self.a,"Knowledge").hits,[])
        self.assertTrue(self.c.search(self.a,"replacement").hits)
    def vector_client(self):
        index=MemoryIndex(); c=LocalKnowledgeClient(self.c.store,vector_index=index,embedder=HashEmbedder()); return c,index
    def test_dirty_vector_hits_authoritative_acl_recheck(self):
        c,index=self.vector_client()
        k=c.create_kb(self.other,"Other","enterprise"); cross=c.ingest(self.other,k.kb_id,"Knowledge cross tenant")
        archived=c.ingest(self.a,self.k.kb_id,"Knowledge archived"); ah=index.entries[-1][0]; c.archive(self.a,archived.doc_id)
        denied=c.ingest(self.a,self.k.kb_id,"Knowledge denied"); dh=index.entries[-1][0]
        c.set_document_acl(self.a,denied.doc_id,DocumentACL(deny_users=["owner"]))
        good=c.ingest(self.a,self.k.kb_id,"Knowledge permitted"); gh=index.entries[-1][0]
        cross_chunk=c.store.get_chunks(cross.doc_id,1)[0]
        index.dirty=[VectorHit(cross.doc_id,1,cross_chunk.chunk_id,100),ah,dh,VectorHit("missing",1,"fake",100),VectorHit(good.doc_id,9,gh.chunk_id,100),VectorHit(good.doc_id,1,"fake",100)]
        for mode in ("vector","hybrid"):
            hits=c.search(self.a,"Knowledge",mode=mode).hits
            self.assertIn(good.doc_id,[h.doc_id for h in hits])
            self.assertFalse({cross.doc_id,archived.doc_id,denied.doc_id}&{h.doc_id for h in hits})
    def test_archive_restore_fts_and_vector(self):
        c,index=self.vector_client(); v=c.ingest(self.a,self.k.kb_id,"uniquearchive")
        c.archive(self.a,v.doc_id)
        self.assertIn(v.doc_id,index.deleted); self.assertFalse(any(h.doc_id==v.doc_id for h,_ in index.entries))
        self.assertEqual(c.search(self.a,"uniquearchive").hits,[])
        c.restore(self.a,v.doc_id); self.assertTrue(c.search(self.a,"uniquearchive").hits)
        self.assertTrue(any(h.doc_id==v.doc_id for h,_ in index.entries))
    def test_failed_secondary_index_remains_authoritatively_archived(self):
        c,index=self.vector_client(); v=c.ingest(self.a,self.k.kb_id,"offlineindex")
        index.fail=True
        with self.assertRaises(OSError): c.archive(self.a,v.doc_id)
        self.assertTrue(c.store.get_document(v.doc_id).archived)
        self.assertEqual(c.search(self.a,"offlineindex").hits,[]); self.assertEqual(c.health()["status"],"degraded")
        index.fail=False; c.reindex(self.a,self.k.kb_id); self.assertEqual(c.health()["status"],"ok")
    def test_hash_embedder_deterministic_nonsemantic(self):
        e=HashEmbedder(); self.assertTrue(e.non_semantic); self.assertEqual(len(e.embed(["x"])[0]),256)
        self.assertEqual(e.embed(["知识 x"]),e.embed(["知识 x"]))

    def test_cjk_bigrams_do_not_match_single_shared_character(self):
        v=self.c.ingest(self.a,self.k.kb_id,"知道答案")
        self.assertNotIn(v.doc_id,[h.doc_id for h in self.c.search(self.a,"知识").hits])
