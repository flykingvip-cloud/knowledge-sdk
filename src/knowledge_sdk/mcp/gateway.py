"""HMAC gateway claims are independent of all model-controlled arguments."""
from __future__ import annotations
from dataclasses import dataclass
from ..contracts.models import Actor
from ..contracts.policy import AgentIdentity,Purpose,enum_value
from ..exceptions import ValidationError
from ..server.auth import (verify_headers,extension_claims,InMemoryReplayStore,
                           _normalize_headers,_validate_secrets)


@dataclass(frozen=True)
class GatewayContext:
    actor: Actor
    agent: AgentIdentity
    purpose: Purpose = Purpose.GROUND_EXTERNAL_LLM
    def __post_init__(self):
        if not isinstance(self.actor,Actor) or not isinstance(self.agent,AgentIdentity) or self.actor.org_id!=self.agent.org_id:
            raise ValidationError('Invalid gateway context')
        value=enum_value(Purpose,self.purpose)
        if value not in (Purpose.GROUND_EXTERNAL_LLM,Purpose.GROUND_INTERNAL_LLM):raise ValidationError('Invalid gateway purpose')
        object.__setattr__(self,'purpose',value)


class GatewayAuthenticator:
    def __init__(self,secret,*,replay_store=None,fallback_secrets=(),bound_purpose=Purpose.GROUND_EXTERNAL_LLM):
        _validate_secrets(secret,fallback_secrets)
        self.secret=secret;self.fallback_secrets=tuple(fallback_secrets)
        self.replay_store=replay_store if replay_store is not None else InMemoryReplayStore()
        self.bound_purpose=enum_value(Purpose,bound_purpose)
        if self.bound_purpose not in (Purpose.GROUND_EXTERNAL_LLM,Purpose.GROUND_INTERNAL_LLM):raise ValidationError('Invalid gateway purpose')
    def authenticate(self,headers,method,path,body=b''):
        try:
            normalized=_normalize_headers(headers)
            # Typed preflight before consuming a valid nonce. No authentication
            # result escapes until the full HMAC verification succeeds below.
            actor=verify_headers(normalized,self.secret,method,path,body,dev_insecure=True)
            raw,purpose=extension_claims(normalized,actor)
            if raw is None:raise ValidationError('Agent required')
            agent=AgentIdentity.from_dict(raw)
            if 'x-kb-purpose' in normalized and Purpose(purpose)!=self.bound_purpose:raise ValidationError('Purpose binding mismatch')
            verified=verify_headers(normalized,self.secret,method,path,body,replay_store=self.replay_store,fallback_secrets=self.fallback_secrets)
            return GatewayContext(verified,agent,self.bound_purpose)
        except (ValidationError,ValueError,TypeError,UnicodeError):
            raise ValidationError('Invalid gateway authentication') from None
