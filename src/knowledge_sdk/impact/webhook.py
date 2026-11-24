"""HMAC Webhooks: no proxies/redirects; validate DNS and pin the connected IP."""
from __future__ import annotations
import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from ..contracts.events import WebhookDelivery
from ..exceptions import ValidationError


def validate_webhook_url(url, *, allow_insecure_local=False):
    if not isinstance(url,str) or any(ord(c)<33 or ord(c)==127 for c in url):
        raise ValidationError('Invalid webhook URL')
    try:
        parsed=urlsplit(url);host=parsed.hostname;port=parsed.port
        if not host or parsed.username is not None or parsed.password is not None or parsed.fragment or '%' in host:
            raise ValueError()
        if parsed.scheme not in ('https','http'):raise ValueError()
        port=port if port is not None else (443 if parsed.scheme=='https' else 80)
        if not 1<=port<=65535:raise ValueError()
        # Resolve ALL addresses, reject a mixed public/private DNS answer, and
        # return numeric addresses so connection never re-resolves the hostname.
        answers=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
        addresses=tuple(dict.fromkeys(item[4][0] for item in answers))
        if not addresses:raise ValueError()
        all_loopback=True
        for address in addresses:
            ip=ipaddress.ip_address(address)
            if getattr(ip,'ipv4_mapped',None) is not None:ip=ip.ipv4_mapped
            if ip.version==6 and (getattr(ip,'is_site_local',False) or any(ip in ipaddress.ip_network(net) for net in ('64:ff9b::/96','64:ff9b:1::/48','2002::/16','2001::/32'))):
                raise ValueError()
            all_loopback=all_loopback and ip.is_loopback
            if ip.is_loopback and allow_insecure_local:continue
            if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                raise ValueError()
        if parsed.scheme!='https' and not (allow_insecure_local and all_loopback):raise ValueError()
        return parsed,addresses,port
    except (ValueError,OSError) as exc:
        raise ValidationError('Unsafe webhook destination') from exc


def sign_webhook(secret,body,webhook_id,event_id,timestamp):
    prefix=(str(timestamp)+'.'+webhook_id+'.'+event_id+'.').encode('utf-8')
    return 'sha256='+hmac.new(secret.encode('utf-8'),prefix+body,hashlib.sha256).hexdigest()


def verify_webhook_signature(secret,body,webhook_id,event_id,timestamp,signature,*,now=None,tolerance=300):
    try:
        if abs((time.time() if now is None else now)-int(timestamp))>tolerance:return False
        expected=sign_webhook(secret,body,webhook_id,event_id,timestamp)
        return isinstance(signature,str) and hmac.compare_digest(expected,signature)
    except (TypeError,ValueError,OverflowError):return False


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,port,address,timeout):
        super().__init__(host,port,timeout=timeout,context=ssl.create_default_context())
        self.address=address
    def connect(self):
        sock=socket.create_connection((self.address,self.port),self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:sock.close();raise


def deliver_http(url,body,headers,*,allow_insecure_local=False,timeout=5):
    parsed,addresses,port=validate_webhook_url(url,allow_insecure_local=allow_insecure_local)
    # One validated numeric endpoint per attempt. Never follow redirects and
    # never use HTTP(S)_PROXY or a second unvalidated DNS lookup.
    if parsed.scheme=='https':
        connection=_PinnedHTTPS(parsed.hostname,port,addresses[0],timeout)
    else:connection=http.client.HTTPConnection(addresses[0],port,timeout=timeout)
    path=parsed.path or '/'
    if parsed.query:path+='?'+parsed.query
    headers=dict(headers);headers['Host']=parsed.netloc
    try:
        connection.request('POST',path,body=body,headers=headers)
        response=connection.getresponse()
        try:return response.status
        finally:response.close()
    finally:connection.close()


class WebhookDispatcher:
    def __init__(self,store,*,allow_insecure_local_webhook=False,transport=None):
        self.store=store;self.allow_insecure_local_webhook=allow_insecure_local_webhook
        self.transport=transport or deliver_http

    def dispatch(self,event):
        failed=False
        for sub in self.store.list_webhook_subscriptions(event.org_id):
            if event.event_type not in sub.event_types or self.store.has_webhook_delivery(sub.subscription_id,event.event_id):continue
            delivery_id=str(uuid.uuid5(uuid.NAMESPACE_URL,sub.subscription_id+':'+event.event_id))
            from dataclasses import replace
            alerts=[replace(a,status='open').to_dict() for a in self.store.list_impact_alerts(event.org_id,doc_id=event.payload.get('doc_id')) if a.source_event_id==event.event_id]
            body=json.dumps({'event_id':event.event_id,'org_id':event.org_id,
                             'event_type':event.event_type,'payload':dict(event.payload),'impact_alerts':alerts},
                            sort_keys=True,separators=(',',':')).encode('utf-8')
            stamp=str(int(time.time()))
            headers={'Content-Type':'application/json','X-KB-Webhook-Id':delivery_id,
                     'X-KB-Event-Id':event.event_id,'X-KB-Webhook-Timestamp':stamp,
                     'X-KB-Webhook-Signature':sign_webhook(sub.secret,body,delivery_id,event.event_id,stamp)}
            code=0;reason='delivery_failed'
            try:
                allow=sub.allow_insecure_local and self.allow_insecure_local_webhook
                # Validate even with an injected transport. No test transport can
                # quietly turn a production metadata/internal URL into a valid sub.
                validate_webhook_url(sub.url,allow_insecure_local=allow)
                code=self.transport(sub.url,body,headers,allow_insecure_local=allow)
                success=200<=code<300
                if not success:raise OSError('Webhook rejected')
            except Exception:
                self.store.record_webhook_delivery(WebhookDelivery(delivery_id,event.org_id,sub.subscription_id,event.event_id,
                    'dead_letter' if event.attempts>=5 else 'failed',code,datetime.now(timezone.utc).isoformat(),reason))
                # Never persist response bodies, URLs, exceptions or secrets.
                failed=True
                continue
            self.store.record_webhook_delivery(WebhookDelivery(delivery_id,event.org_id,sub.subscription_id,event.event_id,
                'delivered',code,datetime.now(timezone.utc).isoformat(),'ok'))
        if failed:raise OSError('Webhook delivery failed')
