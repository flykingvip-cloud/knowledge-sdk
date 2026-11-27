"""Wave-V21-1 protocol-level adapter clients. Stdlib only, injectable, no implicit network.

Default transports are in-process loopbacks. Hosts may inject a transport; this
module never opens sockets, loads credentials, or calls paid providers.
"""
from __future__ import annotations
import hashlib, sys
from pathlib import Path

from sandbox.v21_reuse_v1.revocation import FourChannelRevocation, CHANNELS

TRACE_KEYS = (
    'tenant_id', 'user_id', 'agent_id', 'trace_id', 'run_id', 'plan_id', 'policy_generation',
)
FORBIDDEN_TRANSPORT_MODULES = frozenset({
    'socket', 'ssl', 'http', 'http.client', 'http.server', 'urllib', 'urllib.request',
    'urllib.client', 'requests', 'aiohttp', 'httpx',
})
class AdapterError(ValueError):
    def __init__(self, code, message='request_rejected'):
        self.code = code
        self.message = message
        super().__init__(code)


def contract_validator():
    root = str(Path(__file__).resolve().parents[2] / 'contracts' / 'v21-reuse-v1')
    if root not in sys.path:
        sys.path.insert(0, root)
    import validate
    return validate


def _schema(name):
    validate = contract_validator()
    return validate.load_schema(Path(__file__).resolve().parents[2] / 'contracts' / 'v21-reuse-v1' / name)


def validate_contract(schema_file, schema_name, payload):
    validate = contract_validator()
    try:
        validate.validate_payload(_schema(schema_file), schema_name, payload)
    except validate.ContractError as exc:
        raise AdapterError(exc.code) from exc
    return payload


def _reject_implicit_network(payload):
    text = str(payload).lower()
    if any(token in text for token in ('https://', 'http://', 'wss://', 'ftp://')):
        raise AdapterError('CREDENTIAL_FORBIDDEN')


def _require_injected_or_loopback(transport):
    module = getattr(transport, '__module__', '') or ''
    if module in FORBIDDEN_TRANSPORT_MODULES:
        raise AdapterError('CREDENTIAL_FORBIDDEN')


class LoopbackModelTransport(object):
    """Deterministic in-process model stub. No network I/O."""

    def invoke(self, request):
        text = 'syn loopback: ' + request['messages'][-1]['text']
        usage = dict(
            input_tokens=sum(len(item['text']) for item in request['messages']),
            output_tokens=len(text),
        )
        return dict(
            tenant_id=request['tenant_id'],
            trace_id=request['trace_id'],
            run_id=request['run_id'],
            provider=request['provider'],
            text=text[:8000],
            fallback_used=request['provider']['track'] == 'openbot_fallback',
            usage=usage,
        )


class LoopbackEmbeddingRerankTransport(object):
    """Deterministic hash embeddings and lexical rerank. No network I/O."""

    dim = 8

    def embed(self, request):
        vectors = [self._vector(item) for item in request['inputs']]
        return dict(tenant_id=request['tenant_id'], provider=request['provider'], vectors=vectors, dim=self.dim)

    def rerank(self, request):
        query_tokens = set(request['query'].lower().split())
        ranked = []
        for candidate in request['candidates']:
            tokens = set(candidate['text'].lower().split())
            score = 0.0 if not query_tokens else len(query_tokens & tokens) / float(len(query_tokens))
            ranked.append(dict(candidate_id=candidate['candidate_id'], score=score))
        ranked.sort(key=lambda item: item['score'], reverse=True)
        return dict(tenant_id=request['tenant_id'], provider=request['provider'], rankings=ranked)

    def _vector(self, text):
        digest = hashlib.sha256(text.encode('utf-8')).digest()
        return [digest[index] / 255.0 for index in range(self.dim)]


class LoopbackDataBridgeTransport(object):
    """Allowlisted in-memory query execution. Never runs SQL."""

    def __init__(self):
        self.snapshots = {
            'syn_snap_1': dict(snapshot_id='syn_snap_1', rows=(dict(object_id='syn_obj_1', tenant_id='syn_org'),)),
        }
        self.objects = {
            'syn_org': dict(object_id='syn_obj_1', tenant_id='syn_org'),
        }

    def execute(self, declaration, query=None):
        query = query or {}
        if declaration.get('tombstone', {}).get('active') is True:
            raise AdapterError('UNAUTHORIZED')
        mode = declaration['mode']
        if mode == 'A':
            return dict(mode='A', tenant_id=declaration['tenant_id'], item=self.objects.get(declaration['tenant_id']), query_kind=declaration['query_kind'])
        if mode == 'B':
            predicate = declaration['row_level_predicate']
            rows = [row for row in self.snapshots['syn_snap_1']['rows'] if self._matches(row, predicate)]
            return dict(mode='B', tenant_id=declaration['tenant_id'], rows=tuple(rows), query_kind='structured_select')
        if mode == 'C':
            snapshot = self.snapshots.get(declaration['snapshot_id'])
            if snapshot is None:
                raise AdapterError('VALIDATION_ERROR')
            return dict(mode='C', tenant_id=declaration['tenant_id'], snapshot=snapshot, query_kind='snapshot_read')
        raise AdapterError('MODE_UNMATCHED')

    def _matches(self, row, predicate):
        actual = row.get(predicate['field'])
        if predicate['op'] == 'eq':
            return actual == predicate['value']
        if predicate['op'] == 'in':
            return actual in predicate['value'].split(',')
        return False


class ModelAdapterClient(object):
    def __init__(self, transport=None):
        self.transport = transport or LoopbackModelTransport()
        _require_injected_or_loopback(self.transport)

    def invoke(self, payload, trace=None):
        if not isinstance(payload, dict):
            raise AdapterError('VALIDATION_ERROR')
        _reject_implicit_network(payload)
        if trace is not None:
            payload = trace.bind_payload(payload)
        validate_contract('model-adapter.schema.json', 'LLMInvokeRequest', payload)
        response = self.transport.invoke(payload)
        validate_contract('model-adapter.schema.json', 'LLMInvokeResponse', response)
        return response


class EmbeddingRerankAdapterClient(object):
    def __init__(self, transport=None):
        self.transport = transport or LoopbackEmbeddingRerankTransport()
        _require_injected_or_loopback(self.transport)

    def embed(self, payload):
        if not isinstance(payload, dict):
            raise AdapterError('VALIDATION_ERROR')
        _reject_implicit_network(payload)
        validate_contract('model-adapter.schema.json', 'EmbedRequest', payload)
        response = self.transport.embed(payload)
        if len(response.get('vectors') or ()) != len(payload['inputs']) or response.get('dim') != len(response['vectors'][0]):
            raise AdapterError('VALIDATION_ERROR')
        validate_contract('model-adapter.schema.json', 'EmbedResponse', response)
        return response

    def rerank(self, payload):
        if not isinstance(payload, dict):
            raise AdapterError('VALIDATION_ERROR')
        _reject_implicit_network(payload)
        validate_contract('model-adapter.schema.json', 'RerankRequest', payload)
        response = self.transport.rerank(payload)
        validate_contract('model-adapter.schema.json', 'RerankResponse', response)
        return response


class ControlledDataBridgeClient(object):
    def __init__(self, transport=None):
        self.transport = transport or LoopbackDataBridgeTransport()
        _require_injected_or_loopback(self.transport)

    def execute(self, declaration, query=None):
        if not isinstance(declaration, dict):
            raise AdapterError('VALIDATION_ERROR')
        _reject_implicit_network(dict(declaration=declaration, query=query or {}))
        if (query or {}).get('sql') or (query or {}).get('text_to_sql') or declaration.get('query_kind') == 'text_to_sql':
            raise AdapterError('TEXT_TO_SQL_FORBIDDEN')
        if declaration.get('mode') not in ('A', 'B', 'C'):
            raise AdapterError('MODE_UNMATCHED')
        schema_name = {'A': 'ModeADeclaration', 'B': 'ModeBDeclaration', 'C': 'ModeCDeclaration'}[declaration['mode']]
        validate_contract('controlled-data-bridge.schema.json', schema_name, declaration)
        if declaration['mode'] == 'B' and not declaration.get('row_level_predicate'):
            raise AdapterError('MODE_UNMATCHED')
        return self.transport.execute(declaration, query)


class CogniWeaveMemoryBridgeClient(object):
    def __init__(self, catalog=None, verifier=None):
        self.catalog = catalog if catalog is not None else {}
        self.verifier = verifier or FourChannelRevocation()

    def discover(self, payload):
        if not isinstance(payload, dict):
            raise AdapterError('VALIDATION_ERROR')
        _reject_implicit_network(payload)
        validate_contract('memory-resource-bridge.schema.json', 'MemoryDiscoveryMetadata', payload)
        if payload['resource_type'] != 'agent_memory':
            raise AdapterError('VALIDATION_ERROR')
        self.catalog[payload['memory_resource_id']] = dict(payload)
        return dict(payload, stored=True)

    def invalidate(self, notice):
        validate_contract('memory-resource-bridge.schema.json', 'Channel4InvalidationNotice', notice)
        record = self.catalog.get(notice['memory_resource_id'])
        if record is not None:
            record['discoverable'] = False
            record['invalidation'] = dict(notice)
        return dict(notice, applied=True)

    def apply_purge(self, receipt):
        return self.validate_receipt(receipt)

    def validate_receipt(self, receipt):
        if not isinstance(receipt, dict):
            raise AdapterError('VALIDATION_ERROR')
        validate_contract('memory-resource-bridge.schema.json', 'RevocationPurgeReceipt', receipt)
        names = [item.get('channel') for item in receipt.get('channels') or []]
        if names != list(CHANNELS):
            raise AdapterError('CHANNEL_INCOMPLETE')
        if receipt.get('purged') is True and not all(item.get('status') == 'success' for item in receipt['channels']):
            raise AdapterError('CHANNEL_INCOMPLETE')
        if not self.verifier.verify(receipt):
            raise AdapterError('VALIDATION_ERROR')
        if receipt.get('purged') is True:
            subject = receipt['subject_id']
            if subject in self.catalog:
                self.catalog[subject]['discoverable'] = False
                self.catalog[subject]['purged'] = True
        return dict(receipt, accepted=True)


class AIExecutionTraceContext(object):
    """Official seven-key propagation plus required cost_attribution envelope."""

    def __init__(self, payload):
        if not isinstance(payload, dict):
            raise AdapterError('VALIDATION_ERROR')
        for key in TRACE_KEYS:
            if key not in payload:
                raise AdapterError('VALIDATION_ERROR')
        validate_contract('ai-execution-trace.schema.json', 'AIExecutionTrace', payload)
        self.payload = dict(payload)

    @classmethod
    def from_payload(cls, payload):
        return cls(payload)

    def as_dict(self):
        return dict(self.payload)

    def seven_keys(self):
        return {key: self.payload[key] for key in TRACE_KEYS}

    def headers(self):
        mapping = {
            'tenant_id': 'X-V21-Tenant-Id',
            'user_id': 'X-V21-User-Id',
            'agent_id': 'X-V21-Agent-Id',
            'trace_id': 'X-V21-Trace-Id',
            'run_id': 'X-V21-Run-Id',
            'plan_id': 'X-V21-Plan-Id',
            'policy_generation': 'X-V21-Policy-Generation',
        }
        return {header: str(self.payload[key]) for key, header in mapping.items()}

    def bind_payload(self, payload):
        bound = dict(payload)
        for key in TRACE_KEYS:
            if key in bound and bound[key] != self.payload[key]:
                raise AdapterError('VALIDATION_ERROR')
            bound[key] = self.payload[key]
        return bound

    def propagate(self, payload=None):
        target = dict(payload or {})
        target.update(self.seven_keys())
        target['cost_attribution'] = dict(self.payload['cost_attribution'])
        return target
