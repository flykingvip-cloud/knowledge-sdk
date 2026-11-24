"""Transactional-outbox worker; all handlers are idempotent on event_id."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from contextlib import nullcontext
import threading
from ..contracts.events import DispatchSummary
from ..contracts.policy import parse_time
from ..exceptions import ValidationError


class OutboxDispatcher:
    def __init__(self,store,*,radar=None,webhook=None,max_attempts=5):
        if type(max_attempts) is not int or not 1<=max_attempts<=100:raise ValidationError('Invalid max_attempts')
        self.store=store;self.radar=radar;self.webhook=webhook;self.max_attempts=max_attempts
        self._stop=threading.Event();self._thread=None

    def drain_outbox(self,limit=50,now=None,*,org_id=None):
        # Match LocalKnowledgeClient's lock order before taking the store lock,
        # including background workers, to avoid client/store lock inversion.
        client=getattr(self.radar,'client',None)
        with client._lock if client is not None else nullcontext():
            return self._drain_outbox(limit,now,org_id=org_id)

    def _drain_outbox(self,limit=50,now=None,*,org_id=None):
        when=datetime.now(timezone.utc) if now is None else parse_time(now) if isinstance(now,str) else now
        if not isinstance(when,datetime) or when.tzinfo is None:raise ValidationError('Expected timezone-aware now')
        events=self.store.claim_outbox_batch(when.isoformat(),limit,org_id=org_id)
        done=failed=dead=0
        for event in events:
            # The SQLite writer lock fences stale workers across the handlers and
            # final status update. An expired batch claim may have been reclaimed
            # before we obtained the lock; its attempt number is then rejected.
            with self.store._write_scope():
                current=self.store._execute("SELECT 1 FROM outbox_events WHERE event_id=? AND status='processing' AND attempts=?",(event.event_id,event.attempts))
                if not current:continue
                if event.attempts>self.max_attempts:
                    self.store.mark_outbox_failed(event.event_id,when.isoformat(),self.max_attempts)
                    dead+=1
                    continue
                try:
                    if self.radar is not None:self.radar.process(event)
                    if self.webhook is not None:self.webhook.dispatch(event)
                except Exception:
                    retry=(when+timedelta(seconds=min(3600,2**min(event.attempts,12)))).isoformat()
                    self.store.mark_outbox_failed(event.event_id,retry,self.max_attempts)
                    if event.attempts>=self.max_attempts:dead+=1
                    else:failed+=1
                else:
                    self.store.mark_outbox_dispatched(event.event_id,when.isoformat());done+=1
        return DispatchSummary(len(events),done,failed,dead)

    def start(self,interval=1):
        if not isinstance(interval,(int,float)) or not 0<interval<=30:raise ValidationError('Invalid dispatcher interval')
        if self._thread is not None and self._thread.is_alive():return
        self._stop.clear()
        def run():
            while not self._stop.is_set():
                try:self.drain_outbox()
                except Exception:pass  # Durable events remain available; no payload logging.
                self._stop.wait(interval)
        self._thread=threading.Thread(target=run,name='kb-outbox',daemon=True);self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread is not None:self._thread.join()
