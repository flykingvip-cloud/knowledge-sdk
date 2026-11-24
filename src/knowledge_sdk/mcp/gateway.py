"""HMAC gateway claims are independent of all model-controlled arguments."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from ..contracts.models import Actor
from ..contracts.policy import AgentIdentity,Purpose,enum_value
from ..exceptions import ValidationError
from ..server.auth import (verify_headers,extension_claims,InMemoryReplayStore,
                           _normalize_headers,_validate_secrets)


@dataclass(frozen=True)
class GatewayContext:
    actor: Actor
    agent: Optional[AgentIdentity] = None
    purpose: Purpose = Purpose.GROUND_INTERNAL_LLM
    def __post_init__(self):
        if not isinstance(self.actor,Actor) or self.agent is not None and (not isinstance(self.agent,AgentIdentity) or self.actor.org_id!=self.agent.org_id):
            raise ValidationError('Invalid gateway context')
        value=enum_value(Purpose,self.purpose)
        object.__setattr__(self,'purpose',value)


class GatewayAuthenticator:
    def __init__(self,secret,*,replay_store=None,fallback_secrets=(),bound_purpose=Purpose.GROUND_INTERNAL_LLM):
        _validate_secrets(secret,fallback_secrets)
        self.secret=secret;self.fallback_secrets=tuple(fallback_secrets)
        self.replay_store=replay_store if replay_store is not None else InMemoryReplayStore()
        self.bound_purpose=enum_value(Purpose,bound_purpose)
    def authorize_http(self,headers,method,path,body=b''):
        """Production transport adapter: status derives only from real HMAC verification."""
        try:return self.authenticate(headers,method,path,body),200
        except ValidationError:return None,401
    def authenticate(self,headers,method,path,body=b''):
        try:
            items=list(headers) if isinstance(headers,(list,tuple)) else list(headers.items())
            if any(not isinstance(item,(list,tuple)) or len(item)!=2 or not all(isinstance(v,str) for v in item) for item in items):
                raise ValidationError('Invalid headers')
            class Pairs:
                def items(self):return items
            normalized=_normalize_headers(Pairs())
            # Typed preflight before consuming a valid nonce. No authentication
            # result escapes until the full HMAC verification succeeds below.
            actor=verify_headers(normalized,self.secret,method,path,body,dev_insecure=True)
            raw,purpose=extension_claims(normalized,actor)
            agent=AgentIdentity.from_dict(raw) if raw is not None else None
            applied=Purpose(purpose) if 'x-kb-purpose' in normalized else self.bound_purpose
            verified=verify_headers(normalized,self.secret,method,path,body,replay_store=self.replay_store,fallback_secrets=self.fallback_secrets)
            return GatewayContext(verified,agent,applied)
        except (ValidationError,ValueError,TypeError,UnicodeError,AttributeError):
            raise ValidationError('Invalid gateway authentication') from None
