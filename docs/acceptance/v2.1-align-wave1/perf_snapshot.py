"""Retained-snapshot paired repeats; phase engine [external-artifact-directory].
Initial before receipts were saved before source edits. Recheck exact d153295 in
a detached worktree, then final feature SHA on the same physical snapshots.
Never pass a production DSN. Caller owns/stops/deletes disposable fixture cluster.
"""
from __future__ import annotations
from pathlib import Path
import sys,json,subprocess,statistics,cProfile,pstats,io,sqlite3
from dataclasses import replace
from knowledge_sdk import Actor,LocalKnowledgeClient
from knowledge_sdk.retrieval.eval import PairwiseRetrievalEvaluator,RetrievalEvalCase,PairwiseEvalConfig,digest,_percentile
from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
from tests.retrieval.q3_m2_fixture import EvalFixture,MemoryCosineIndex,ROOT
ART=Path(sys.argv[3] if len(sys.argv)>3 else '/workspace/knowledge-sdk-align-wave1-artifacts');ART.mkdir(parents=True,exist_ok=True);phase,engine=sys.argv[1:3];output=ART/f'perf-{phase}-{engine}.json';assert not output.exists()
state=ART/f'perf-snapshot-{engine}.json'
if phase=='before':
 f=EvalFixture(engine)
 try:
  if engine=='sqlite':
   dbfile=ART/'perf-snapshot.sqlite';target=sqlite3.connect(dbfile)
   try:f.c.store.db.backup(target)
   finally:target.close()
   entries=[dict(key=list(k),org_id=v[0],vector=list(v[1])) for k,v in f.c.vector_index.entries.items()]
   state.write_text(json.dumps({'sqlite_file':str(dbfile),'entries':entries}))
  else:state.write_text(json.dumps({'dsn':f.sandbox.dsn,'owned_schema':f.sandbox.schema}))
 finally:
  f.c.store.close() # Keep ONLY this owned snapshot/schema for after measurements.
  if engine=='sqlite' and f.sandbox:f.sandbox.close()
config=json.loads(state.read_text())
if engine=='sqlite':
 from knowledge_sdk.storage.sqlite_store import SQLiteStore
 store=SQLiteStore(config['sqlite_file']);index=MemoryCosineIndex(store);index.entries={tuple(e['key']):(e['org_id'],tuple(e['vector'])) for e in config['entries']}
else:
 from tests.pg_helpers import GoldenPostgresStore
 from knowledge_sdk.retrieval.adapters.pgvector_index import PgVectorIndex
 store=GoldenPostgresStore(config['dsn']);index=PgVectorIndex(store=store)
c=LocalKnowledgeClient(store,vector_index=index,embedder=HashEmbedder());actors={'reader':Actor('reader','eval-org',clearance_level='internal'),'foreign':Actor('admin','foreign-org',org_roles=('admin',),clearance_level='restricted')}
cases=tuple(RetrievalEvalCase.from_dict(json.loads(x)) for x in (ROOT/'eval_dataset_q3_m2.jsonl').read_text().splitlines());cfg=PairwiseEvalConfig.from_dict(json.loads((ROOT/'eval_config_q3_m2.json').read_text()))
evaluator=PairwiseRetrievalEvaluator(c,actors,config=cfg)
def actual_index_hash():
 if engine=='sqlite':return digest([(k,list(v[1])) for k,v in sorted(index.entries.items())])
 result=[]
 for org in ('eval-org','foreign-org'):
  with store.tenant_scope(org):
   result.extend((r[0],r[1],r[2],json.loads(r[3])) for r in store._execute('SELECT doc_id,version,chunk_id,embedding::text FROM chunk_embeddings ORDER BY doc_id,version,chunk_id'))
 return digest(result)
index_before=actual_index_hash();pools=[]
from unittest.mock import patch
from knowledge_sdk.retrieval.rerank import DeterministicLexicalReranker
original_score=DeterministicLexicalReranker.score
def observe(self,query,candidates):
 pools.append({'query_sha256':digest(query),'candidates':[{'identity':[x.doc_id,x.version,x.chunk_id],'rank':x.rank,'raw_score':x.raw_score,'title_sha256':digest(x.title),'excerpt_sha256':digest(x.excerpt)} for x in candidates]})
 return original_score(self,query,candidates)
class RollbackMeasurement(Exception):pass
def run():
 result=None
 try:
  with store.transaction():
   with patch.object(DeterministicLexicalReranker,'score',observe):result=evaluator.evaluate(cases,index_sha256=index_before).to_dict()
   raise RollbackMeasurement()
 except RollbackMeasurement:pass
 assert result['gate_passed'];return result
try:
 warm=run();reports=[run() for _ in range(5)]
 result={'phase':phase,'engine':engine,'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'warmups':1,'repeats':5,'configuration':cfg.to_dict(),'dataset_sha256':reports[0]['dataset_sha256'],'corpus_sha256':reports[0]['corpus_sha256'],'same_physical_snapshot':True,'measurement_boundary':'Each complete pair runs real policy/audit SQL in an identical outer test transaction then rolls back its audit/usage-only writes, retaining the exact same owned snapshot. Search-only perf_counter timing includes authorization/rank/calibration; identical wrapper both phases.','arms':{}}
 for arm in ('baseline','candidate'):
  values=[r['case_results'][i][arm]['latency_ms'] for r in reports for i in range(24)]
  result['arms'][arm]={'samples':len(values),'p50_ms':_percentile(values,.5),'p95_ms':_percentile(values,.95),'mean_ms':statistics.mean(values),'latencies_ms':values,'quality':[{k:r[arm][k] for k in ('ndcg_at_k','mrr','recall_at_k','refusal_accuracy','false_refusal_rate','acl_violations','implicit_model_calls','returned_hits')} for r in reports]}
 profile=cProfile.Profile();profile.enable();run();profile.disable();stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(45);(ART/f'profile-{phase}-{engine}.txt').write_text(stream.getvalue())
 assert actual_index_hash()==index_before
 result.update(index_sha256=index_before,protected_pool_sha256=digest(pools),protected_pool_calls=len(pools),ranking_source_sha256={name:__import__('hashlib').sha256(Path(name).read_bytes()).hexdigest() for name in ('src/knowledge_sdk/retrieval/hybrid.py','src/knowledge_sdk/retrieval/rerank.py','src/knowledge_sdk/retrieval/calibration.py')})
 output.write_text(json.dumps(result,indent=2)+'\n');print(engine,phase,{a:{k:v for k,v in x.items() if k not in ('quality','latencies_ms')} for a,x in result['arms'].items()})
finally:store.close()
