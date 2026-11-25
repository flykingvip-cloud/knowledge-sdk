"""Measured local microbenchmarks, never a production SLA or enterprise approval."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
import json,os,statistics,tempfile,time
from knowledge_sdk import Actor,LocalKnowledgeClient,SQLiteStore
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.storage.postgres_store import PostgresStore
from knowledge_sdk.governance.workflow import now


def summary(values):
    ordered=sorted(values)
    return {'n':len(values),'unit':'milliseconds','mean':statistics.mean(values),'p50':statistics.median(values),'p95':ordered[min(len(values)-1,int(len(values)*.95))],'max':max(values)}

def run(engine):
    from tests.pg_helpers import PgSandbox
    with ExitStack() as stack:
        directory=stack.enter_context(tempfile.TemporaryDirectory());pg=None
        if engine=='postgres':pg=PgSandbox();stack.callback(pg.close);s=PostgresStore(pg.dsn)
        else:s=SQLiteStore(Path(directory)/'db')
        stack.callback(s.close);c=LocalKnowledgeClient(s);a=Actor('admin','perf',org_roles=('admin',));c.create_kb(a,'bench','enterprise',kb_id='kb')
        ingest=[]
        for i in range(80):
            start=time.perf_counter();c.ingest(a,'kb','alpha local benchmark evidence source number '+str(i),doc_id='d'+str(i));ingest.append((time.perf_counter()-start)*1000)
        searches=[]
        for i in range(40):
            start=time.perf_counter();response=c.search(a,'alpha',limit=5);assert len(response.hits)==5;searches.append((time.perf_counter()-start)*1000)
        s.upsert_principal(IdentityPrincipal('perf','user'))
        workers=[]
        for _ in range(4):
            worker=PostgresStore(pg.dsn,migrate=False) if pg else SQLiteStore(Path(directory)/'db');stack.callback(worker.close);workers.append(worker)
        def bump(store):
            return [store.bump_policy_generation('perf','user').policy_generation for _ in range(10)]
        start=time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:generations=sum(pool.map(bump,workers),[])
        generation_ms=(time.perf_counter()-start)*1000;assert sorted(generations)==list(range(2,42))
        def claim(store):
            claimed=[]
            while True:
                events=store.claim_outbox_batch(now(),5,org_id='perf')
                if not events:break
                for event in events:claimed.append(event.event_id);store.mark_outbox_dispatched(event.event_id,now())
            return claimed
        start=time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:claims=sum(pool.map(claim,workers),[])
        drain_ms=(time.perf_counter()-start)*1000;assert len(claims)==80 and len(set(claims))==80
        return {'engine':engine,'ingest':summary(ingest),'authorized_search_top5':summary(searches),'four_connections_generation_bumps':40,'unique_generations':len(set(generations)),'generation_wall_ms':generation_ms,'four_workers_outbox_events':len(claims),'duplicate_claims':len(claims)-len(set(claims)),'outbox_wall_ms':drain_ms,'outbox_claim_strategy':'FOR UPDATE SKIP LOCKED' if pg else 'BEGIN IMMEDIATE','implicit_model_calls':0,'boundary':'Local 80 short documents, 40 queries, non-vector keyword microbenchmark; not production capacity/SLA'}

if __name__=='__main__':print(json.dumps([run(e) for e in ('sqlite','postgres')],indent=2))
