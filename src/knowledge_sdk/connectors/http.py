from __future__ import annotations
from fastapi import Request
from dataclasses import asdict
from .base import ConnectorSyncRunner
from .webhook_sync import WebhookSyncConnector
from ..exceptions import NotFoundError,ValidationError


def mount_connectors(app,client,connectors):
    runner=ConnectorSyncRunner(client)
    def configured(connector_id,actor):
        entry=connectors.get(connector_id)
        if entry is None:raise NotFoundError('Connector not found')
        connector,kb_id=entry
        if connector.org_id!=actor.org_id:raise NotFoundError('Connector not found')
        return connector,kb_id
    @app.post('/v1/connectors/{connector_id}/plan')
    async def plan(connector_id:str,request:Request):
        connector,kb_id=configured(connector_id,request.state.actor)
        return runner.plan_sync(request.state.actor,connector,org_id=request.state.actor.org_id,kb_id=kb_id,agent=request.state.agent,purpose=request.state.purpose)
    @app.post('/v1/connectors/{connector_id}/sync')
    async def sync(connector_id:str,request:Request):
        connector,kb_id=configured(connector_id,request.state.actor)
        return asdict(runner.run_once(request.state.actor,connector,org_id=request.state.actor.org_id,kb_id=kb_id))
    @app.post('/v1/connectors/{connector_id}/webhook')
    async def webhook(connector_id:str,request:Request):
        connector,kb_id=configured(connector_id,request.state.actor)
        if not isinstance(connector,WebhookSyncConnector):raise ValidationError('Connector does not accept webhooks')
        return asdict(runner.run_once(request.state.actor,connector,org_id=request.state.actor.org_id,kb_id=kb_id,webhook=(await request.body(),request.headers)))
