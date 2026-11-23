from __future__ import annotations
import base64
import hashlib
import hmac
import json
import secrets
import time
from ..contracts.models import Actor
from dataclasses import asdict, fields
from ..exceptions import ValidationError

def _actor_data(actor):
    return asdict(actor)
def signed_headers(actor,secret,method,path,body=b"",timestamp=None,nonce=None):
    if not secret or len(secret)<32: raise ValidationError("Auth secret must contain at least 32 characters")
    payload=base64.urlsafe_b64encode(json.dumps(_actor_data(actor),sort_keys=True,separators=(",",":")).encode()).decode()
    timestamp=str(int(time.time()) if timestamp is None else timestamp); nonce=nonce or secrets.token_hex(16)
    message="\n".join((method.upper(),path,payload,timestamp,nonce,hashlib.sha256(body).hexdigest()))
    signature=hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()
    return {"X-KB-Actor":payload,"X-KB-Timestamp":timestamp,"X-KB-Nonce":nonce,"X-KB-Signature":signature}

def verify_headers(headers,secret,method,path,body=b"",dev_insecure=False,max_age=300,seen=None):
    try:
        payload=headers.get("x-kb-actor","")
        if len(payload)>16384: raise ValueError()
        raw=json.loads(base64.b64decode(payload,altchars=b"-_",validate=True))
        if not isinstance(raw,dict) or not {"user_id","org_id"}.issubset(raw) or set(raw) - {f.name for f in fields(Actor)}: raise ValueError()
        if not all(isinstance(raw[k],str) for k in ("user_id","org_id")): raise ValueError()
        if not all(isinstance(raw[k],list) and all(isinstance(x,str) for x in raw[k]) for k in ("roles","department_ids","ancestor_department_ids","org_roles","clearance_tags","managed_department_ids") if k in raw): raise ValueError()
        actor=Actor(**raw)
        if dev_insecure: return actor
        stamp=headers.get("x-kb-timestamp",""); nonce=headers.get("x-kb-nonce","")
        now=time.time()
        if abs(now-int(stamp))>max_age or not 16<=len(nonce)<=128: raise ValueError()
        message="\n".join((method.upper(),path,payload,stamp,nonce,hashlib.sha256(body).hexdigest()))
        expected=hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,headers.get("x-kb-signature","")): raise ValueError()
        if seen is not None:
            for key,expiry in list(seen.items()):
                if expiry<now: del seen[key]
            if nonce in seen or len(seen)>=50000: raise ValueError()
            seen[nonce]=now+max_age*2
        return actor
    except (ValueError,TypeError,KeyError,ValidationError) as exc:
        raise ValidationError("Invalid request authentication") from exc
