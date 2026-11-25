"""Strict JWT bearer boundary. Cryptography is lazy and never a core dependency.

JWKS URLs are operator configuration, never token jku/x5u. DNS addresses are
validated AND pinned; redirects, proxies and private/metadata targets are denied.
HS256 keys are explicitly separate from public JWKS material.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import http.client
import json
import math
import threading
import time
from ..contracts.models import Actor
from ..exceptions import ValidationError
from ..impact.webhook import validate_webhook_url, _PinnedHTTPS
from .auth import InMemoryReplayStore


def _fail():raise ValidationError('Invalid OIDC authentication')


def _b64(value):
    if not isinstance(value,str) or not value or len(value)>65536 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in value):_fail()
    try:return base64.urlsafe_b64decode(value+'='*(-len(value)%4))
    except (ValueError,TypeError):_fail()


def _object(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:_fail()
            d[k]=v
        return d
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:_fail())
        if not isinstance(value,dict):_fail()
        return value
    except (ValueError,TypeError,UnicodeError):_fail()


class JWKSProvider:
    def __init__(self,jwks_uri,*,ttl_seconds=300,cooldown_seconds=30,allow_insecure_local=False,clock=time.time):
        if not 1<=ttl_seconds<=86400 or not 1<=cooldown_seconds<=3600:raise ValidationError('Invalid JWKS cache limits')
        validate_webhook_url(jwks_uri,allow_insecure_local=allow_insecure_local)
        self.uri=jwks_uri;self.ttl=ttl_seconds;self.cooldown=cooldown_seconds;self.allow_local=allow_insecure_local;self.clock=clock
        self._keys={};self._expires=0;self._refreshed=-float('inf');self._lock=threading.Lock()
    def _fetch(self):
        parsed,addresses,port=validate_webhook_url(self.uri,allow_insecure_local=self.allow_local)
        conn=_PinnedHTTPS(parsed.hostname,port,addresses[0],5) if parsed.scheme=='https' else http.client.HTTPConnection(addresses[0],port,timeout=5)
        try:
            conn.request('GET',(parsed.path or '/')+('?' + parsed.query if parsed.query else ''),headers={'Host':parsed.netloc,'Accept':'application/json'})
            r=conn.getresponse()
            try:
                raw=r.read(1024*1024+1)
                if r.status!=200 or len(raw)>1024*1024:_fail()
                return _object(raw)
            finally:r.close()
        except (OSError,http.client.HTTPException):_fail()
        finally:conn.close()
    def get_key(self,kid):
        with self._lock:
            now=self.clock()
            if now<self._expires and kid in self._keys:return dict(self._keys[kid])
            if now-self._refreshed<self.cooldown:_fail()
            self._refreshed=now  # failed refreshes also cool down
            data=self._fetch();keys=data.get('keys')
            if not isinstance(keys,list) or len(keys)>100:_fail()
            fresh={}
            for key in keys:
                if not isinstance(key,dict) or not isinstance(key.get('kid'),str) or not key['kid'] or key['kid'] in fresh:_fail()
                if key.get('kty') not in ('RSA','EC'):continue
                if any(k in key for k in ('d','p','q','k')):_fail()
                fresh[key['kid']]=dict(key)
            self._keys=fresh;self._expires=now+self.ttl
            if kid not in fresh:_fail()
            return dict(fresh[kid])


class OIDCAuthenticator:
    def __init__(self,issuer,audience,jwks_provider=None,*,algorithms=('RS256','ES256'),hs256_keys=None,replay_store=None,leeway_seconds=0,clock=time.time,require_jti=True):
        self.algorithms=frozenset(algorithms)
        if not self.algorithms or not self.algorithms<={'RS256','ES256','HS256'} or type(leeway_seconds) is not int or not 0<=leeway_seconds<=120:raise ValidationError('Invalid OIDC configuration')
        if not isinstance(issuer,str) or not issuer or not isinstance(audience,str) or not audience:raise ValidationError('Issuer/audience required')
        self.issuer=issuer;self.audience=audience;self.provider=jwks_provider;self.hs=dict(hs256_keys or {})
        if 'HS256' in self.algorithms and (not self.hs or any(not isinstance(k,bytes) or len(k)<32 or b'-----BEGIN' in k for k in self.hs.values())):raise ValidationError('Dedicated HS256 keys required')
        if self.algorithms & {'RS256','ES256'} and jwks_provider is None:raise ValidationError('JWKS provider required')
        self.replay_store=replay_store if replay_store is not None else InMemoryReplayStore();self.leeway=leeway_seconds;self.clock=clock;self.require_jti=require_jti
    def _verify(self,header,message,signature):
        alg=header.get('alg');kid=header.get('kid')
        if alg not in self.algorithms or not isinstance(kid,str) or not kid or len(kid)>256 or header.get('crit') or any(k in header for k in ('jku','x5u','jwk')):_fail()
        if alg=='HS256':
            key=self.hs.get(kid)
            if key is None or not hmac.compare_digest(hmac.new(key,message,hashlib.sha256).digest(),signature):_fail()
            return
        key=self.provider.get_key(kid)
        if not isinstance(key,dict) or key.get('use','sig')!='sig' or key.get('alg',alg)!=alg or 'key_ops' in key and 'verify' not in key['key_ops']:_fail()
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa,ec,padding,utils
            if alg=='RS256':
                if key.get('kty')!='RSA':_fail()
                n=int.from_bytes(_b64(key['n']),'big');e=int.from_bytes(_b64(key['e']),'big')
                if n.bit_length()<2048 or e<3:_fail()
                public=rsa.RSAPublicNumbers(e,n).public_key()
                public.verify(signature,message,padding.PKCS1v15(),hashes.SHA256())
            else:
                if key.get('kty')!='EC' or key.get('crv')!='P-256' or len(signature)!=64:_fail()
                public=ec.EllipticCurvePublicNumbers(int.from_bytes(_b64(key['x']),'big'),int.from_bytes(_b64(key['y']),'big'),ec.SECP256R1()).public_key()
                public.verify(utils.encode_dss_signature(int.from_bytes(signature[:32],'big'),int.from_bytes(signature[32:],'big')),message,ec.ECDSA(hashes.SHA256()))
        except (ImportError,KeyError,ValueError,TypeError):_fail()
        except Exception:_fail()
    def authenticate(self,token,*,consume_replay=True):
        return self.authenticate_with_claims(token,consume_replay=consume_replay)[0]
    def authenticate_with_claims(self,token,*,consume_replay=True):
        if not isinstance(token,str) or len(token)>65536:_fail()
        parts=token.split('.')
        if len(parts)!=3:_fail()
        h,p,s=parts;header=_object(_b64(h));claims=_object(_b64(p))
        self._verify(header,(h+'.'+p).encode('ascii'),_b64(s))
        now=self.clock()
        for name in ('exp','nbf','iat'):
            if name not in claims:
                if name in ('exp','nbf'):_fail()
                continue
            if type(claims[name]) is not int or claims[name]<=0:_fail()
        if claims['exp']<=now-self.leeway or claims['nbf']>now+self.leeway or claims['nbf']>=claims['exp'] or claims.get('iat',0)>now+self.leeway:_fail()
        audience=claims.get('aud')
        if not isinstance(audience,(str,list)) or isinstance(audience,list) and any(not isinstance(a,str) for a in audience):_fail()
        if claims.get('iss')!=self.issuer or self.audience not in ([audience] if isinstance(audience,str) else audience):_fail()
        for name in ('sub','org_id','clearance_level'):
            value=claims.get(name)
            if not isinstance(value,str) or name!='clearance_level' and not value or any(ord(c)<32 or ord(c)==127 for c in value):_fail()
        for name in ('roles','department_ids'):
            if not isinstance(claims.get(name),list) or any(not isinstance(v,str) or not v or any(ord(c)<32 for c in v) for v in claims[name]):_fail()
        generation=claims.get('policy_generation')
        if type(generation) not in (str,int) or isinstance(generation,bool) or not str(generation).isdigit():_fail()
        if self.require_jti or 'jti' in claims:
            jti=claims.get('jti')
            if not isinstance(jti,str) or not jti or len(jti)>512:_fail()
            nonce='oidc:'+hashlib.sha256((self.issuer+'\0'+claims['org_id']+'\0'+jti).encode()).hexdigest()
            if consume_replay and not self.replay_store.check_and_record(nonce,max(1,math.ceil(claims['exp']+self.leeway-now)),now=now):_fail()
        kwargs={name:claims[name] for name in ('roles','department_ids','clearance_level')}
        for name in ('org_roles','clearance_tags','managed_department_ids','ancestor_department_ids'):
            if name in claims:
                if not isinstance(claims[name],list):_fail()
                kwargs[name]=claims[name]
        return Actor(claims['sub'],claims['org_id'],policy_generation=str(generation),session_id=claims.get('jti',''),**kwargs),claims
