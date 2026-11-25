"""Bounded HTTP operational surfaces; no resource/tenant/query labels."""
from __future__ import annotations
from fastapi import Request
from fastapi.responses import JSONResponse
from ..exceptions import PermissionDeniedError


def mount_operations(app,client):
    import threading
    lock=threading.Lock()
    counts={k:0 for k in ('http_requests_total','http_responses_2xx_total','http_responses_3xx_total','http_responses_4xx_total','http_responses_5xx_total')}
    @app.middleware('http')
    async def aggregate(request,call_next):
        response=await call_next(request)
        with lock:
            counts['http_requests_total']+=1
            bucket='http_responses_'+str(response.status_code//100)+'xx_total'
            if bucket in counts:counts[bucket]+=1
        response.headers['Cache-Control']='no-store';response.headers['Pragma']='no-cache'
        return response
    @app.get('/v1/ready')
    async def ready():
        try:
            with client._lock,client.store.transaction():
                if client.store._execute('SELECT 1')!=[(1,)]:raise ValueError()
                query='SELECT COALESCE(MAX(version),0) FROM schema_migrations' if hasattr(client.store,'_pg') else 'PRAGMA user_version'
                if client.store._execute(query)!=[(5,)]:raise ValueError()
        except Exception:return JSONResponse({'status':'not_ready'},status_code=503,headers={'Cache-Control':'no-store'})
        return JSONResponse({'status':'ready'},headers={'Cache-Control':'no-store'})
    @app.get('/v1/metrics')
    async def metrics(request:Request):
        actor=request.state.actor
        with client._lock:
            client._check_principal(actor)
            client._org_agent(actor,request.state.agent,request.state.purpose)
            if 'metrics_admin' not in actor.org_roles:raise PermissionDeniedError('metrics_access_denied')
            with lock:result=dict(counts)
        return JSONResponse({'counters':result},headers={'Cache-Control':'no-store'})
