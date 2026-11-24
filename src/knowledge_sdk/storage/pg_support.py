"""Lazy driver and deliberately detail-free database errors (including causes)."""
from __future__ import annotations
import re
from ..exceptions import ValidationError


def redact_dsn(value):
    # Hide the entire authority userinfo, including malformed/raw @ characters.
    value = re.sub(r'(?i)(postgres(?:ql)?://)[^/\s]+@', r'\1***@', str(value))
    # libpq values may quote whitespace and escape quotes/backslashes.
    return re.sub(r"(?i)(password\s*=\s*)(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|(?:\\.|[^\s])+)", r'\1***', value)


def driver():
    try:
        import psycopg
    except ImportError:
        raise ValidationError('Install pip install knowledge-sdk[postgres]') from None
    return psycopg


def connect(dsn):
    pg = driver()
    try:
        return pg.connect(dsn, autocommit=True, connect_timeout=10)
    except Exception:
        raise ValidationError('PostgreSQL connection failed (connection details withheld)') from None
