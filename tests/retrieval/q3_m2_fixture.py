"""Fixed labeled corpus; real lexical hashing + real cosine/pgvector, no canned ranks."""
from pathlib import Path
import json, math, hashlib
from knowledge_sdk import Actor, LocalKnowledgeClient, DocumentACL
from knowledge_sdk.retrieval.base import VectorHit
from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
from knowledge_sdk.retrieval.eval import RetrievalEvalCase, PairwiseEvalConfig, digest

ROOT=Path(__file__).parent

class MemoryCosineIndex:
    def __init__(self,store):self.store=store;self.entries={}
    def delete_document(self,doc_id):
        self.entries={k:v for k,v in self.entries.items() if k[0]!=doc_id}
    def upsert(self,entries):
        for hit,vector in entries:
            org=self.store.get_document(hit.doc_id).org_id
            self.entries[(hit.doc_id,hit.version,hit.chunk_id)]=(org,tuple(vector))
    def search_for_org(self,org,vector,limit=100):
        norm=math.sqrt(sum(v*v for v in vector)) or 1
        hits=[]
        for (d,v,c),(tenant,embedding) in self.entries.items():
            if tenant!=org:continue
            denom=norm*(math.sqrt(sum(x*x for x in embedding)) or 1)
            hits.append(VectorHit(d,v,c,sum(a*b for a,b in zip(vector,embedding))/denom))
        return sorted(hits,key=lambda h:(-h.score,h.doc_id,h.version,h.chunk_id))[:limit]

class EvalFixture:
    def __init__(self,engine='sqlite'):
        self.sandbox=None;self.engine=engine
        if engine=='postgres':
            from tests.pg_helpers import PgSandbox,golden_client
            self.sandbox=PgSandbox();self.c=golden_client(self.sandbox.dsn)
        else:
            from knowledge_sdk.storage.sqlite_store import SQLiteStore
            store=SQLiteStore();self.c=LocalKnowledgeClient(store,vector_index=MemoryCosineIndex(store),embedder=HashEmbedder())
        self.admin=Actor('admin','eval-org',org_roles=('admin',),clearance_level='restricted')
        self.reader=Actor('reader','eval-org',clearance_level='internal')
        self.foreign=Actor('admin','foreign-org',org_roles=('admin',),clearance_level='restricted')
        self.c.create_kb(self.admin,'evaluation','enterprise',kb_id='eval-kb')
        self.c.create_kb(self.admin,'controlled','enterprise',kb_id='controlled-kb',governance_tier='l2_controlled')
        self.c.create_kb(self.foreign,'foreign','enterprise',kb_id='foreign-kb')
        self.verify_freeze()
        for row in (json.loads(s) for s in (ROOT/'eval_corpus_q3_m2.jsonl').read_text().splitlines()):
            row=dict(row);actor=self.admin if row.pop('org_id')=='eval-org' else self.foreign
            revisions=row.pop('revisions',[]);acl=DocumentACL(**row.pop('acl',{}));text=row.pop('text')
            for revision in revisions:self.c.ingest(actor,content=revision,filename='fixture.txt',acl=acl,**row)
            self.c.ingest(actor,content=text,filename='fixture.txt',acl=acl,**row)
        self.cases=tuple(RetrievalEvalCase.from_dict(json.loads(s)) for s in (ROOT/'eval_dataset_q3_m2.jsonl').read_text().splitlines())
        self.config=PairwiseEvalConfig.from_dict(json.loads((ROOT/'eval_config_q3_m2.json').read_text()))
    @staticmethod
    def verify_freeze():
        freeze=json.loads((ROOT/'eval_freeze_q3_m2.json').read_text())
        for file,expected in freeze['files'].items():assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==expected
    def index_hash(self):
        if self.engine=='sqlite':
            return digest([(k,list(v[1])) for k,v in sorted(self.c.vector_index.entries.items())])
        result=[]
        for org in ('eval-org','foreign-org'):
            with self.c.store.tenant_scope(org):
                rows=self.c.store._execute('SELECT doc_id,version,chunk_id,embedding::text FROM chunk_embeddings ORDER BY doc_id,version,chunk_id')
                result.extend([(r[0],r[1],r[2],json.loads(r[3])) for r in rows])
        return digest(result)
    def close(self):
        try:self.c.store.close()
        finally:
            if self.sandbox:self.sandbox.close()
