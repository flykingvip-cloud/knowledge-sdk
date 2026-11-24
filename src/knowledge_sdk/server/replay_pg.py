"""Atomic shared TTL replay protection. All failures reject without driver detail."""
import math
import time
from ..storage.postgres_store import PostgresStore
from .auth import _valid_replay_input
from ..exceptions import ValidationError


class PostgresReplayStore:
    def __init__(self,dsn,*,max_entries=50000,enable_rls=True,migrate=True):
        if type(max_entries) is not int or max_entries<1:raise ValidationError('Invalid replay capacity')
        self.store=PostgresStore(dsn,enable_rls=enable_rls,migrate=migrate)
        self.max_entries=max_entries

    def check_and_record(self,*args,now=None,org_id=None):
        """ReplayStore(nonce, ttl, now=...) or (org_id, nonce, expires_at).

        Legacy two-arg callers use a dedicated auth namespace; HTTP auth uses the
        verified actor tenant via check_and_record_for_org, never an unsigned ID.
        """
        now=time.time() if now is None else now
        if len(args)==3:
            org,nonce,expiry=args
            from ..contracts.policy import parse_time
            try:expiry=parse_time(expiry).timestamp() if isinstance(expiry,str) else float(expiry)
            except (ValueError,TypeError,ValidationError):return False
            ttl=expiry-now
        elif len(args)==2:
            nonce,ttl=args;org=org_id or '__signed_auth__';expiry=now+ttl if type(ttl) in (int,float) else now
        else:return False
        if not isinstance(org,str) or not org or not isinstance(nonce,str) or not 0<len(nonce)<=1024:return False
        if type(now) not in (int,float) or not math.isfinite(now) or not math.isfinite(expiry) or expiry<=now:return False
        try:
            with self.store.tenant_scope(org):
                self.store._execute("SELECT pg_advisory_xact_lock(hashtext('replay:' || %s))",(org,))
                self.store._execute('DELETE FROM replay_nonces WHERE org_id=%s AND expires_at<=%s',(org,now))
                if self.store._execute('SELECT COUNT(*) FROM replay_nonces WHERE org_id=%s',(org,))[0][0]>=self.max_entries:return False
                return bool(self.store._execute('INSERT INTO replay_nonces VALUES(%s,%s,%s) ON CONFLICT(org_id,nonce) DO NOTHING RETURNING nonce',(org,nonce,expiry)))
        except Exception:return False

    def check_and_record_for_org(self,org_id,nonce,ttl_seconds,*,now=None):
        now=time.time() if now is None else now
        if not _valid_replay_input(nonce,ttl_seconds,now):return False
        return self.check_and_record(nonce,ttl_seconds,now=now,org_id=org_id)

    def close(self):self.store.close()
