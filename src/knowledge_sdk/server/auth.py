"""Dependency-free request signatures and atomic bounded replay protection."""
from __future__ import annotations
from contextlib import closing
import base64
import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import threading
import time
from dataclasses import asdict, fields
from typing import Optional, Protocol, Sequence
from ..contracts.models import Actor
from ..contracts.policy import Purpose
from ..exceptions import ValidationError


class ReplayStore(Protocol):
    def check_and_record(self, nonce: str, ttl_seconds: int, *, now: Optional[float] = None) -> bool:
        """Atomically consume a nonce. False means replay, capacity or failure."""
        ...


class InMemoryReplayStore:
    def __init__(self, max_entries=50000):
        if type(max_entries) is not int or max_entries < 1:
            raise ValidationError("Invalid replay capacity")
        self.max_entries = max_entries
        self._entries = {}
        self._lock = threading.Lock()

    def check_and_record(self, nonce, ttl_seconds, *, now=None):
        now = time.time() if now is None else now
        if not _valid_replay_input(nonce, ttl_seconds, now):
            return False
        with self._lock:
            self._entries = {k: v for k, v in self._entries.items() if v > now}
            if nonce in self._entries or len(self._entries) >= self.max_entries:
                return False
            self._entries[nonce] = now + ttl_seconds
            return True


def _valid_replay_input(nonce, ttl, now):
    return (isinstance(nonce, str) and bool(nonce) and type(ttl) is int
            and ttl > 0 and type(now) in (int, float) and math.isfinite(now))


class SQLiteReplayStore:
    """Separate replay database; per-call connections are thread/process safe.

    BEGIN IMMEDIATE serializes check+insert across workers. Every write clears
    expired entries; the bounded table fails closed (also on SQLite errors).
    Do not point this at a business database or place it on a network filesystem.
    """
    def __init__(self, path: str, max_entries=50000):
        if not isinstance(path, str) or not path or path == ":memory:" or path.startswith("file:"):
            raise ValidationError("Replay store requires a separate on-disk database")
        if type(max_entries) is not int or max_entries < 1:
            raise ValidationError("Invalid replay capacity")
        self.path, self.max_entries = path, max_entries
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as conn, conn:
                # Refuse existing business databases rather than adding tables.
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if tables - {"auth_replay"}:
                    raise ValidationError("Replay store must use a dedicated database")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("CREATE TABLE IF NOT EXISTS auth_replay (nonce TEXT PRIMARY KEY, expires REAL NOT NULL)")
                conn.execute("CREATE INDEX IF NOT EXISTS auth_replay_expiry ON auth_replay(expires)")
        except sqlite3.Error as exc:
            raise ValidationError("Unable to initialize replay store") from exc

    def check_and_record(self, nonce, ttl_seconds, *, now=None):
        now = time.time() if now is None else now
        if not _valid_replay_input(nonce, ttl_seconds, now):
            return False
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM auth_replay WHERE expires <= ?", (now,))
                if conn.execute("SELECT 1 FROM auth_replay WHERE nonce=?", (nonce,)).fetchone():
                    return False
                if conn.execute("SELECT COUNT(*) FROM auth_replay").fetchone()[0] >= self.max_entries:
                    return False
                conn.execute("INSERT INTO auth_replay VALUES (?,?)", (nonce, now + ttl_seconds))
            return True
        except sqlite3.Error:
            return False


PURPOSES = frozenset(p.value for p in Purpose)


def _actor_data(actor):
    data = asdict(actor)
    # Preserve v1.1 default Actor bytes, not just the six-line message layout.
    if data["policy_generation"] == "0":
        del data["policy_generation"]
    if data["session_id"] == "":
        del data["session_id"]
    return data


def _decode_object(payload, limit):
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > limit:
        raise ValueError()
    # Strict URL-safe alphabet (padding optional); no standard '+' or '/'.
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for c in payload):
        raise ValueError()
    raw = base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True)
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError()
    return value


def _normalize_headers(headers):
    items = [(k.lower(), v) for k, v in headers.items()]
    names = [k for k, _ in items if k.startswith("x-kb-")]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate authentication header")
    return dict(items)


def extension_claims(headers, actor):
    """Validate optional signed context without introducing a policy engine."""
    headers = _normalize_headers(headers)
    agent_payload = headers.get("x-kb-agent")
    purpose = headers.get("x-kb-purpose")
    agent = None
    if agent_payload is not None:
        agent = _decode_object(agent_payload, 8192)
        if not all(isinstance(agent.get(k), str) and agent[k].strip() for k in ("agent_id", "org_id")):
            raise ValueError()
        if agent["org_id"] != actor.org_id:
            raise ValueError()
    if purpose is not None and purpose not in PURPOSES:
        raise ValueError()
    return agent, purpose if purpose is not None else "read"


def _message(method, path, payload, stamp, nonce, body, agent_payload=None, purpose=None):
    parts = [method.upper(), path, payload, stamp, nonce, hashlib.sha256(body).hexdigest()]
    if agent_payload is not None or purpose is not None:
        parts.extend((agent_payload if agent_payload is not None else "", purpose if purpose is not None else ""))
    return "\n".join(parts).encode()


def _validate_secrets(secret, fallback_secrets=()):
    if isinstance(fallback_secrets, (str, bytes)):
        raise ValidationError("Fallback secrets must be a sequence")
    values = (secret, *fallback_secrets)
    if any(not isinstance(v, str) or len(v) < 32 for v in values):
        raise ValidationError("Auth secrets must contain at least 32 characters")
    return values


def signed_headers(actor, secret, method, path, body=b"", timestamp=None, nonce=None, *, agent=None, purpose=None):
    _validate_secrets(secret)
    payload = base64.urlsafe_b64encode(json.dumps(_actor_data(actor), sort_keys=True, separators=(",", ":")).encode()).decode()
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_hex(16)
    agent_payload = (base64.urlsafe_b64encode(json.dumps(agent, sort_keys=True, separators=(",", ":")).encode()).decode()
                     if isinstance(agent, dict) else agent)
    headers = {"X-KB-Actor": payload, "X-KB-Timestamp": stamp, "X-KB-Nonce": nonce}
    if agent_payload is not None:
        headers["X-KB-Agent"] = agent_payload
    if purpose is not None:
        headers["X-KB-Purpose"] = purpose
    try:
        extension_claims({k.lower(): v for k, v in headers.items()}, actor)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValidationError("Invalid request context") from exc
    message = _message(method, path, payload, stamp, nonce, body, agent_payload, purpose)
    headers["X-KB-Signature"] = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return headers


def verify_headers(headers, secret, method, path, body=b"", dev_insecure=False, max_age=300, seen=None,
                   replay_store=None, fallback_secrets: Sequence[str] = ()):
    try:
        headers = _normalize_headers(headers)
        payload = headers.get("x-kb-actor", "")
        raw = _decode_object(payload, 16384)
        if not {"user_id", "org_id"}.issubset(raw) or set(raw) - {f.name for f in fields(Actor)}:
            raise ValueError()
        if not all(isinstance(raw[k], list) and all(isinstance(x, str) for x in raw[k]) for k in
                   ("roles", "department_ids", "ancestor_department_ids", "org_roles", "clearance_tags", "managed_department_ids") if k in raw):
            raise ValueError()
        actor = Actor(**raw)
        extension_claims(headers, actor)
        if dev_insecure:
            return actor
        keys = _validate_secrets(secret, fallback_secrets)
        stamp, nonce = headers.get("x-kb-timestamp", ""), headers.get("x-kb-nonce", "")
        now = time.time()
        if abs(now - int(stamp)) > max_age or not 16 <= len(nonce) <= 128:
            raise ValueError()
        message = _message(method, path, payload, stamp, nonce, body, headers.get("x-kb-agent"), headers.get("x-kb-purpose"))
        valid = False
        for key in keys:
            valid = hmac.compare_digest(hmac.new(key.encode(), message, hashlib.sha256).hexdigest(), headers.get("x-kb-signature", "")) | valid
        if not valid:
            raise ValueError()
        # Retain through the latest acceptable future-stamped request, including
        # integer timestamp boundary: a full 2*window+1 seconds after first use.
        ttl = max_age * 2 + 1
        if replay_store is not None:
            recorded=(replay_store.check_and_record_for_org(actor.org_id,nonce,ttl,now=now)
                      if hasattr(replay_store,'check_and_record_for_org') else replay_store.check_and_record(nonce,ttl,now=now))
            if not recorded:
                raise ValueError()
        elif seen is not None:
            for key, expiry in list(seen.items()):
                if expiry <= now:
                    del seen[key]
            if nonce in seen or len(seen) >= 50000:
                raise ValueError()
            seen[nonce] = now + ttl
        return actor
    except (ValueError, TypeError, KeyError, UnicodeError, ValidationError) as exc:
        raise ValidationError("Invalid request authentication") from exc
