"""Operational telemetry is not the audit ledger: never serialize caller values."""
import hashlib
import json
import logging
import secrets

_LOG = logging.getLogger('knowledge_sdk.operations')


def emit_operation(operation, org_id, status_code, latency_ms, error_code=None):
    if not _LOG.isEnabledFor(logging.INFO): return
    tenant = hashlib.sha256(org_id.encode('utf-8')).hexdigest() if isinstance(org_id, str) else None
    _LOG.info(json.dumps(dict(request_id=secrets.token_hex(16), tenant_id=tenant,
        operation=operation, status_code=status_code, latency_ms=round(latency_ms, 3),
        error_code=error_code), separators=(',', ':'), allow_nan=False))
