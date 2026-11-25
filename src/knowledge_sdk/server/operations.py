"""Bounded operational surfaces: fixed labels and allowlisted JSON logs only."""
from __future__ import annotations
import threading
import time
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from ..exceptions import PermissionDeniedError

from ..audit.telemetry import emit_operation


def mount_operations(app, client):
    lock = threading.Lock()
    # Preserve the exact public v1 JSON counter contract.
    counts = {k: 0 for k in ('http_requests_total', 'http_responses_2xx_total',
        'http_responses_3xx_total', 'http_responses_4xx_total', 'http_responses_5xx_total')}
    extra = dict(permission_denials_total=0, revocation_denials_total=0,
                 search_latency_seconds_count=0, search_latency_seconds_sum=0.0)

    @app.middleware('http')
    async def aggregate(request, call_next):
        start = time.monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Pragma'] = 'no-cache'
            return response
        finally:
            elapsed = time.monotonic() - start
            route = getattr(request.scope.get('route'), 'path', '')
            # Only registered route names, never request URL/query/resource IDs.
            operation = route if route in {r.path for r in app.routes if hasattr(r, 'path')} else 'unmatched'
            actor = getattr(request.state, 'actor', None)
            org = getattr(actor, 'org_id', None)
            error = getattr(request.state, 'operation_error', None)
            with lock:
                counts['http_requests_total'] += 1
                bucket = 'http_responses_' + str(status//100) + 'xx_total'
                if bucket in counts: counts[bucket] += 1
                if status in (401, 403): extra['permission_denials_total'] += 1
                if getattr(request.state, 'revocation_denied', False): extra['revocation_denials_total'] += 1
                if route in ('/v1/search', '/v1/retrieve'):
                    extra['search_latency_seconds_count'] += 1
                    extra['search_latency_seconds_sum'] += elapsed
            emit_operation(operation, org, status, elapsed*1000,
                error or ('REQUEST_DENIED' if status in (401, 403) else 'HTTP_ERROR' if status >= 400 else None))

    @app.get('/v1/ready')
    async def ready():
        try:
            with client._lock, client.store.transaction():
                if client.store._execute('SELECT 1') != [(1,)]: raise ValueError()
                query = 'SELECT COALESCE(MAX(version),0) FROM schema_migrations' if hasattr(client.store, '_pg') else 'PRAGMA user_version'
                if client.store._execute(query) != [(5,)]: raise ValueError()
        except Exception:
            return JSONResponse({'status': 'not_ready'}, status_code=503, headers={'Cache-Control': 'no-store'})
        return JSONResponse({'status': 'ready'}, headers={'Cache-Control': 'no-store'})

    def authorized_metrics(request):
        actor = request.state.actor
        with client._lock:
            client._check_principal(actor)
            client._org_agent(actor, request.state.agent, request.state.purpose)
            if 'metrics_admin' not in actor.org_roles: raise PermissionDeniedError('metrics_access_denied')
        with lock: return dict(counts), dict(extra)

    @app.get('/v1/metrics')
    async def metrics(request: Request):
        counters, _ = authorized_metrics(request)
        return JSONResponse({'counters': counters}, headers={'Cache-Control': 'no-store'})

    @app.get('/metrics')
    async def prometheus(request: Request):
        counters, other = authorized_metrics(request)
        text = ''.join('knowledge_sdk_' + k + ' ' + str(v) + '\n' for k, v in sorted({**counters, **other}.items()))
        return Response(text, media_type='text/plain; version=0.0.4', headers={'Cache-Control': 'no-store'})
