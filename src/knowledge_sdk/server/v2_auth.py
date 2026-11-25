"""Opt-in trusted-gateway IdentityContext over the unchanged six-line HMAC.

Source08 section2.2 explicitly permits this channel for v2. v1 Actor bytes and
legacy string generation are untouched. Tenant/request headers must equal the
SIGNED IdentityContext; raw caller headers are never independent authority.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import replace
from ..contracts.v2_json import loads,validate
from ..contracts.models import Actor
from ..contracts.policy import AgentIdentity,Purpose,PolicyContext
from ..exceptions import ValidationError,PermissionDeniedError,NotFoundError
from .auth import _message,_validate_secrets


class WireError(Exception):
    def __init__(self,status,code):self.status=status;self.code=code


def signed_v2_headers(context,secret,method,target,body=b'',*,timestamp=None,nonce=None):
    _validate_secrets(secret)
    payload=base64.urlsafe_b64encode(json.dumps(context,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).decode()
    stamp=str(int(time.time()) if timestamp is None else timestamp);nonce=nonce or secrets.token_hex(16)
    return {'X-KB-Actor':payload,'X-KB-Timestamp':stamp,'X-KB-Nonce':nonce,
            'X-KB-Signature':hmac.new(secret.encode(),_message(method,target,payload,stamp,nonce,body),hashlib.sha256).hexdigest(),
            'X-Tenant-Id':context.get('tenant_id',''),'X-Request-Id':context.get('request_id','')}


def authenticate(request,body,secret,fallback_secrets,replay_store,issuer):
    headers=request.headers
    names=[k.lower() for k,v in headers.items() if k.lower().startswith('x-kb-') or k.lower() in ('x-tenant-id','x-request-id','idempotency-key','authorization')]
    if len(names)!=len(set(names)) or any(headers.get(k) for k in ('authorization','x-kb-agent','x-kb-purpose')):
        raise WireError(401,'UNAUTHENTICATED')
    payload=headers.get('x-kb-actor','');stamp=headers.get('x-kb-timestamp','');nonce=headers.get('x-kb-nonce','')
    try:
        if len(payload)>32768 or len(nonce)<16 or len(nonce)>128 or abs(time.time()-int(stamp))>300:raise ValueError()
        target=request.scope.get('raw_path',request.url.path.encode()).decode('ascii')+('?' + request.url.query if request.url.query else '')
        message=_message(request.method,target,payload,stamp,nonce,body)
        valid=False
        for key in _validate_secrets(secret,fallback_secrets):
            valid=hmac.compare_digest(hmac.new(key.encode(),message,hashlib.sha256).hexdigest(),headers.get('x-kb-signature','')) | valid
        if not valid:raise ValueError()
        if any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=' for c in payload):raise ValueError()
        raw=base64.b64decode(payload+'='*(-len(payload)%4),altchars=b'-_',validate=True)
    except (ValueError,TypeError,UnicodeError):raise WireError(401,'SIGNATURE_INVALID') from None
    context=validate('IdentityContext',loads(raw))
    tenant=context['tenant_id'];actor=context['actor']
    if not tenant or tenant!=tenant.strip() or any(ord(c)<32 for c in tenant) or tenant!=headers.get('x-tenant-id'):
        raise WireError(403,'PERMISSION_DENIED')
    if not context['request_id'] or context['request_id']!=headers.get('x-request-id'):raise WireError(400,'VALIDATION_ERROR')
    if actor['actor_type']=='service' or actor['issuer']!=issuer or not actor['subject_id']:raise WireError(403,'PERMISSION_DENIED')
    now=time.time()
    recorded=(replay_store.check_and_record_for_org(tenant,nonce,601,now=now) if hasattr(replay_store,'check_and_record_for_org') else replay_store.check_and_record(nonce,601,now=now))
    if not recorded:raise WireError(401,'REPLAY_DETECTED')
    return context


def current_identity(client,context):
    tenant=context['tenant_id'];claim=context['actor'];purpose=Purpose(context['purpose'])
    principal=client.store.get_principal(tenant,claim['subject_id'])
    if principal is None or not principal.active:raise WireError(403,'IDENTITY_REVOKED')
    if claim['policy_generation']<principal.policy_generation:raise WireError(403,'POLICY_GENERATION_STALE')
    # Claims can narrow authoritative current identity, never widen it. The effective
    # internal string generation is current, after numeric v2 validation, not coercion
    # of invalid input. This also honors the frozen max-safe >= current fixture.
    intersect=lambda field:tuple(x for x in claim[field] if x in getattr(principal,field))
    actor=Actor(principal.user_id,tenant,roles=intersect('roles'),department_ids=intersect('department_ids'),
                org_roles=intersect('org_roles'),managed_department_ids=tuple(x for x in claim['department_ids'] if x in principal.department_ids) if set(intersect('org_roles')) & {'admin','manage_org'} else (),clearance_level=principal.clearance_level if principal.clearance_level==claim['clearance_level'] else '',
                clearance_tags=intersect('clearance_tags'),policy_generation=str(principal.policy_generation),session_id=claim['session_id'])
    agent=None;policy_context=None;space_types=();task_scope=None
    if 'agent' in context:
        bound=context['agent']
        try:profile=client.store.get_agent_profile(tenant,bound['agent_id'])
        except NotFoundError:raise WireError(403,'PERMISSION_DENIED') from None
        if not profile.active or profile.profile_generation!=bound['profile_generation'] or purpose not in profile.allowed_purposes:raise WireError(403,'PERMISSION_DENIED')
        agent=AgentIdentity(profile.agent_id,tenant,allowed_purposes=profile.allowed_purposes,allowed_kb_ids=profile.allowed_kb_ids,
                            max_clearance_level=profile.max_clearance_level,profile_version=str(profile.profile_generation))
        space_types=profile.allowed_space_types
        if bound['task_id']:
            task,_=client._runtime_validate(actor,bound['task_id'])
            if task.agent_id!=agent.agent_id or task.purpose!=purpose:raise WireError(403,'PERMISSION_DENIED')
            policy_context=PolicyContext(task_id=task.task_id)
            task_scope=task.scope
    if claim['actor_type']=='agent' and agent is None:raise WireError(403,'PERMISSION_DENIED')
    return actor,dict(agent=agent,purpose=purpose,policy_context=policy_context),space_types,task_scope
