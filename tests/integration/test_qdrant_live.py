"""Opt-in destructive writes are restricted to new randomly named collections.

Existing collections are only inspected for configuration and exact point counts.
No credentials or .env files are discovered. Optional embedding config is public
endpoint/model configuration, never a provider key.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import unittest
import urllib.request
import uuid
from urllib.parse import quote

from knowledge_sdk import (Actor, LocalKnowledgeClient, ExcerptPolicy, DocumentACL,
                           OpenAICompatibleEmbedder, PermissionDeniedError)
from knowledge_sdk.retrieval.adapters.qdrant import QdrantIndex
from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
from knowledge_sdk.retrieval.excerpt import make_excerpt


URL = os.environ.get("KNOWLEDGE_SDK_LIVE_QDRANT_URL", "").rstrip("/")
EMBEDDING_URL = os.environ.get("KNOWLEDGE_SDK_LIVE_EMBEDDING_URL", "")
MODEL = os.environ.get("KNOWLEDGE_SDK_LIVE_EMBEDDING_MODEL", "")


@unittest.skipUnless(URL, "Set KNOWLEDGE_SDK_LIVE_QDRANT_URL for isolated live integration")
class LiveQdrantTests(unittest.TestCase):
    def request(self, method, path, body=None):
        req=urllib.request.Request(URL+path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)["result"]

    def collections(self):
        return {c["name"] for c in self.request("GET","/collections")["collections"]}

    def snapshot(self, names):
        result={}
        for name in sorted(names):
            path="/collections/"+quote(name,safe="")
            info=self.request("GET",path)
            count=self.request("POST",path+"/points/count",{"exact":True})["count"]
            result[name]={"config":info["config"],"count":count}
        return result

    @contextmanager
    def isolated(self, embedder):
        before=self.collections()
        baseline=self.snapshot(before)
        name="knowledge_sdk_e2e_"+uuid.uuid4().hex
        self.assertNotIn(name,before)
        path="/collections/"+name
        # All mutation paths below are derived exclusively from this generated name.
        self.assertTrue(name.startswith("knowledge_sdk_e2e_"))
        dimensions=len(embedder.embed(["dimension probe"])[0])
        client=None
        try:
            self.request("PUT",path,{"vectors":{"size":dimensions,"distance":"Cosine"}})
            client=LocalKnowledgeClient(vector_index=QdrantIndex(URL,name),embedder=embedder,
                excerpt_policy=ExcerptPolicy(default_chars=80,enterprise_chars=120))
            print("LIVE created",name,"dimensions",dimensions,flush=True)
            yield client,path
        finally:
            try:
                # Also handles a timed-out create whose server-side outcome is ambiguous.
                if name in self.collections(): self.request("DELETE",path)
            finally:
                if client is not None: client.store.close()
                self.assertEqual(self.collections(),before,"Temporary collection cleanup/list mismatch")
                self.assertEqual(self.snapshot(before),baseline,"Existing collection config/count changed")
                print("LIVE cleanup verified; existing configurations and exact point counts unchanged:",
                      {n:baseline[n]["count"] for n in sorted(before)},flush=True)

    def workflow(self, embedder):
        with self.isolated(embedder) as (c,path):
            owner=Actor("owner","alpha"); member=Actor("member","alpha")
            outsider=Actor("outsider","alpha"); foreign=Actor("owner","beta")
            kb=c.create_kb(owner,"Live","enterprise")
            c.grant_kb_member(owner,kb.kb_id,member.user_id,"viewer")
            docs={}
            for visibility in ("private","team","enterprise"):
                docs[visibility]=c.ingest(owner,kb.kb_id,
                    "liveprobe "+visibility+" "+("Evidence and knowledge material. "*15),
                    visibility=visibility)
            fk=c.create_kb(foreign,"Foreign","enterprise")
            cross=c.ingest(foreign,fk.kb_id,"liveprobe cross tenant confidential material")
            denied=c.ingest(owner,kb.kb_id,"liveprobe denied confidential material",visibility="enterprise")
            c.set_document_acl(owner,denied.doc_id,DocumentACL(deny_users=[member.user_id,outsider.user_id]))
            for mode in ("keyword","vector","hybrid"):
                owned={h.doc_id for h in c.search(owner,"liveprobe",mode=mode).hits}
                self.assertTrue({d.doc_id for d in docs.values()} <= owned)
                member_hits=c.search(member,"liveprobe",mode=mode).hits
                self.assertEqual({h.doc_id for h in member_hits},{docs["team"].doc_id,docs["enterprise"].doc_id})
                self.assertEqual({h.doc_id for h in c.search(outsider,"liveprobe",mode=mode).hits},
                                 {docs["enterprise"].doc_id})
            print("LIVE PASS multi-tenant / three-domain keyword, vector, hybrid",flush=True)

            # Inject actual REST points, not a mocked index. Even fake public tenant/ACL
            # payload cannot override SQLite authority. Include missing/stale/fake chunks.
            dirty=[]
            for v in (cross,docs["private"],denied):
                ch=c.store.get_chunks(v.doc_id,1)[0]
                dirty.append({"doc_id":v.doc_id,"version":1,"chunk_id":ch.chunk_id})
            good=docs["enterprise"]; ch=c.store.get_chunks(good.doc_id,1)[0]
            dirty.extend([{"doc_id":"nonexistent","version":1,"chunk_id":"fake"},
                          {"doc_id":good.doc_id,"version":99,"chunk_id":ch.chunk_id},
                          {"doc_id":good.doc_id,"version":1,"chunk_id":"fake"}, {}])
            vec=embedder.embed(["liveprobe"])[0]
            points=[{"id":str(uuid.uuid4()),"vector":vec,
                     "payload":dict(p,org_id="alpha",visibility="enterprise",excerpt="FORGED-SECRET")}
                    for p in dirty]
            self.request("PUT",path+"/points?wait=true",{"points":points})
            self.assertEqual(self.request("POST",path+"/points/count",{"exact":True})["count"],
                             5+len(points))
            raw=c.vector_index.search(vec,100)
            self.assertTrue(any(h.doc_id==cross.doc_id for h in raw),"Dirty cross-tenant point must be returned by Qdrant")
            for mode in ("vector","hybrid"):
                hits=c.search(member,"liveprobe",mode=mode).hits
                self.assertEqual({h.doc_id for h in hits},{docs["team"].doc_id,good.doc_id})
                self.assertTrue(all("FORGED-SECRET" not in h.excerpt for h in hits))
            print("LIVE PASS dirty cross-tenant/private/denied/stale/missing hits blocked by SQLite",flush=True)

            hits=c.search(member,"liveprobe",mode="hybrid").hits
            for h in hits:
                self.assertTrue(h.truncated)
                self.assertGreater(h.remaining_chars,0)
                self.assertLessEqual(len(h.excerpt),120 if h.doc_id==good.doc_id else 80)
                ref=c.reference(member,h.doc_id,h.version,[h.chunk_id],h.excerpt)
                self.assertEqual(ref.excerpt_hash,h.excerpt_hash)
                self.assertEqual(c.consume(member,ref).status,"partial")
            ref=c.reference(owner,docs["private"].doc_id)
            self.assertEqual(c.consume(member,ref).status,"denied")
            with self.assertRaises(PermissionDeniedError): c.retrieve(member,ref.doc_id)
            self.assertEqual(make_excerpt("confidential",allowed=False)["excerpt"],"")
            full=c.reference(owner,good.doc_id)
            self.assertEqual(c.consume(owner,full).status,"consumed")
            print("LIVE PASS excerpt budgets/fail-closed/reference hashes/partial+consumed+denied receipts",flush=True)

            c.archive(owner,good.doc_id)
            count_body={"exact":True,"filter":{"must":[{"key":"doc_id","match":{"value":good.doc_id}}]}}
            self.assertEqual(self.request("POST",path+"/points/count",count_body)["count"],0)
            for mode in ("keyword","vector","hybrid"):
                self.assertNotIn(good.doc_id,{h.doc_id for h in c.search(member,"liveprobe",mode=mode).hits})
            c.restore(owner,good.doc_id); c.reindex(owner,kb.kb_id)
            self.assertGreater(self.request("POST",path+"/points/count",count_body)["count"],0)
            for mode in ("keyword","vector","hybrid"):
                self.assertIn(good.doc_id,{h.doc_id for h in c.search(member,"liveprobe",mode=mode).hits})
            self.assertEqual(c.health()["status"],"ok")
            print("LIVE PASS archive remote point count zero / restore / reindex",flush=True)

    def test_hash_full_lifecycle(self):
        self.workflow(HashEmbedder())

    @unittest.skipUnless(EMBEDDING_URL and MODEL,"Set live local embedding URL/model for semantic integration")
    def test_real_embedding_full_lifecycle(self):
        self.workflow(OpenAICompatibleEmbedder(EMBEDDING_URL,MODEL,timeout=120,batch_size=2))

    @unittest.skipUnless(EMBEDDING_URL and MODEL,"Set live local embedding URL/model for semantic integration")
    def test_real_synonym_recall_without_literal_overlap(self):
        embedder=OpenAICompatibleEmbedder(EMBEDDING_URL,MODEL,timeout=120,batch_size=2)
        with self.isolated(embedder) as (c,path):
            actor=Actor("owner","synonyms")
            kb=c.create_kb(actor,"Synonyms")
            target=c.ingest(actor,kb.kb_id,"Car servicing includes engine oil changes and tire inspection.")
            c.ingest(actor,kb.kb_id,"Bananas and apples are nutritious fruits rich in vitamins.")
            c.ingest(actor,kb.kb_id,"Ocean whales communicate through underwater songs.")
            query="automobile maintenance"
            self.assertEqual(c.search(actor,query,mode="keyword").hits,[])
            hit=c.search(actor,query,mode="vector",limit=1).hits[0]
            self.assertEqual(hit.doc_id,target.doc_id)
            print("LIVE PASS semantic synonym top-1; keyword hits zero; non_semantic=False",flush=True)
