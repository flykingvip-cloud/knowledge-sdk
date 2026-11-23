from __future__ import annotations
import unittest
from knowledge_sdk import Actor, LocalKnowledgeClient
from knowledge_sdk.retrieval.base import VectorHit
class MemoryIndex:
    def __init__(self): self.entries=[]; self.dirty=[]; self.deleted=[]; self.fail=False
    def upsert(self,entries):
        if self.fail: raise OSError("Index offline")
        self.entries.extend(entries)
    def search(self,vector,limit=100):
        return self.dirty+[VectorHit(h.doc_id,h.version,h.chunk_id,sum(a*b for a,b in zip(v,vector))) for h,v in self.entries][:limit]
    def delete_document(self,doc_id):
        self.deleted.append(doc_id)
        if self.fail: raise OSError("Index offline")
        self.entries=[(h,v) for h,v in self.entries if h.doc_id!=doc_id]
class ClientCase(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient(); self.a=Actor("owner","org"); self.viewer=Actor("viewer","org"); self.other=Actor("owner","other")
        self.k=self.c.create_kb(self.a,"Main",visibility="team")
        self.v=self.c.ingest(self.a,self.k.kb_id,"# Guide\nKnowledge 知识库 search and evidence.\nMore material.",filename="guide.md")
    def tearDown(self): self.c.store.close()
