#!/usr/bin/env python3
"""Sandbox PRE-03 zero-PII automatic validator (Wave-V21-5 / W5A-2).

Implements all 12 official zero-PII automatic validation rules from
PRE03_ANONYMIZATION_SPEC_FOR_GATE4.md (official contract v1.0, SHA-256
66294adfb60d54d42c4307d5b19c8fda298828d7bd9b0f520c0a2958f1fb845e).

This module is pure Python standard library, has zero third-party
dependencies, performs no network or production-database I/O, and does
not write to disk. It is a sandbox checker only. It does not produce an
AUTH-V21-04 export, does not contact production data, and does not
authorize Schema v7 DDL. formal_t01_t27 remains NOT_RUN_NOT_ACCEPTED.

A checker used in this sandbox accepts only SYNTHETIC_EXAMPLE mocks
(official rule 12). Real production export remains lead/DBA-only under
Space Gate 4 = MET_FOR_CONTRACT_AND_SANDBOX. No official allocation
ruling is on file, so proposed_space_id and proposed_kb_id must stay JSON
null (official rule 8).
"""
from __future__ import annotations

import json
import re

OFFICIAL_CONTRACT_FILENAME = 'PRE03_ANONYMIZATION_SPEC_FOR_GATE4.md'
OFFICIAL_CONTRACT_SHA256 = (
    '66294adfb60d54d42c4307d5b19c8fda298828d7bd9b0f520c0a2958f1fb845e'
)
PRODUCT_A = 'A'
PRODUCT_B = 'B'
PRODUCT_UNKNOWN = 'unknown'
PRODUCT_B_FORMAT = 'candidate-pre03-v1'
PROVENANCE_SYNTHETIC = 'SYNTHETIC_EXAMPLE'
PROVENANCE_SANITIZED = 'SANITIZED_CANDIDATE'
ALLOWED_PROVENANCE = frozenset({PROVENANCE_SYNTHETIC, PROVENANCE_SANITIZED})
TOKEN_RE = re.compile(r'^syn_[A-Za-z0-9_-]{1,64}$')
EMAIL_RE = re.compile(
    r'(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    r'(?![A-Za-z0-9._%+-])'
)
TELEPHONE_RE = re.compile(
    r"""
    (?<![\dA-Za-z])
    (?:
        \+\d{1,3}(?:[\s./-]*\d){7,14}
        |
        \(0?\d{2,4}\)[\s./-]*\d{3,4}[\s./-]*\d{4}
        |
        \d{3}[\s./-]\d{3}[\s./-]\d{4}
        |
        \d{3}[\s./-]\d{4}[\s./-]\d{4}
    )
    (?![\dA-Za-z])
    """,
    re.VERBOSE,
)
HTML_VALUE_RE = re.compile(
    r'<(?:html|body|div|p|span|br|table|img|script|style|h[1-6]|a|section)\b',
    re.IGNORECASE,
)
MARKDOWN_VALUE_RE = re.compile(
    r'(?:^|\n)\s{0,3}#{1,6}\s+\S|(?:^|\n)\s{0,3}```|(?:^|\n)\[[^\]]+\]\([^)]+\)'
)
FILENAME_VALUE_RE = re.compile(
    r'(?i)(?<![\w./-])[\w.-]+\.(?:pdf|docx?|xlsx?|pptx?|png|jpe?g|gif|webp|'
    r'zip|tar|gz|bin|eml|html|md|markdown|csv)\b'
)
DATA_URI_RE = re.compile(r'(?i)data:[^;]+;base64,[A-Za-z0-9+/]{32,}')
CONNECTION_URI_RE = re.compile(
    r'(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqps?|kafka|'
    r'jdbc|odbc|sqlserver|mssql|sqlite)://[^\s]+'
)
CREDENTIAL_ASSIGN_RE = re.compile(
    r'(?i)(?:password|pwd|secret|api[_-]?key|access[_-]?token|private[_-]?key)'
    r'\s*[:=]\s*\S+'
)
USERINFO_HOST_RE = re.compile(r'(?i)\b[\w.-]+:[^@\s/]+@[\w.-]+(?::\d{2,5})?\b')
COMPLETE_SCAN_RE = re.compile(
    r'(?i)\b(?:scan[_\s-]?complete|complete scan|scan is complete)\b'
)
RAW_ID_KEY_RE = re.compile(
    r"""
    ^(?:
        [0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$
        | \d{3,}
        | (?:legacy[_-])?(?:tenant|kb|user|space|org|alias|name|document|team)[_:-][A-Za-z0-9_-]+
    )$
    """,
    re.VERBOSE | re.IGNORECASE,
)
MOCK_LABEL_RE = re.compile(
    r'(?i)\b(?:mock|synthetic_example|synthetic example|labelled as a mock|'
    r'labeled as a mock)\b'
)
FICTITIOUS_RE = re.compile(
    r'(?i)\b(?:syn_|synthetic_example|synthetic example|fictional|'
    r'lab-mock|obviously fake|placeholder zero|specification example)\b'
)
UUID_RE = re.compile(
    r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'
)

PRODUCT_A_ROOT_KEYS = frozenset({
    'generated_at',
    'scope_description',
    'tenant_count',
    'null_tenant_kb_count',
    'null_tenant_document_count',
    'null_tenant_version_count',
    'kb_count',
    'team_count',
    'collaboration_group_count',
    'favorites_estimate',
    'favorites_estimate_note',
    'legacy_alias_collision_count',
    'name_or_id_collision_count',
    'integrity',
})
PRODUCT_A_REQUIRED_INTEGERS = (
    'tenant_count',
    'null_tenant_kb_count',
    'null_tenant_document_count',
    'null_tenant_version_count',
    'kb_count',
    'team_count',
    'collaboration_group_count',
    'favorites_estimate',
    'legacy_alias_collision_count',
    'name_or_id_collision_count',
)
PRODUCT_A_INTEGRITY_KEYS = frozenset({
    'scan_complete',
    'paginated',
    'unclassifiable_row_count',
})
PRODUCT_B_ROOT_KEYS = frozenset({
    'format',
    'sanitized',
    'provenance',
    'rows',
})
PRODUCT_B_ROW_KEYS = frozenset({
    'legacy_kb_id',
    'tenant_id',
    'proposed_space_id',
    'proposed_kb_id',
    'alias_token',
    'name_token',
})
PRODUCT_B_IDENTIFIER_FIELDS = (
    'legacy_kb_id',
    'tenant_id',
    'proposed_space_id',
    'proposed_kb_id',
    'alias_token',
    'name_token',
)
PRODUCT_B_MAX_ROWS_UNSHARDED = 10000
CONTENT_KEY_EXACT = frozenset({
    'body',
    'content',
    'html',
    'markdown',
    'document_body',
    'document_text',
    'document_content',
    'version_text',
    'version_content',
    'html_content',
    'markdown_content',
    'content_html',
    'content_markdown',
    'raw_html',
    'raw_markdown',
    'attachment',
    'attachments',
    'filename',
    'filenames',
    'attachment_bytes',
    'attachment_filename',
    'attachment_filenames',
    'file_name',
    'file_bytes',
    'mime_bytes',
    'payload_bytes',
    'version_body',
})
SECRET_KEY_EXACT = frozenset({
    'password',
    'passwd',
    'pwd',
    'secret',
    'secrets',
    'api_key',
    'apikey',
    'access_token',
    'auth_token',
    'session_secret',
    'session_token',
    'encryption_key',
    'private_key',
    'secret_key',
    'salt',
    'salts',
    'connection_string',
    'connection_uri',
    'credentials',
    'credential',
    'mapping_table',
    'mapping_tables',
    'id_mapping',
    'id_mapping_table',
    'id_mapping_tables',
    'cluster_secret',
    'cluster_secrets',
    'dsn',
    'database_url',
    'db_password',
    'client_secret',
    'session_secrets',
    'encryption_keys',
})


def _norm_key(key):
    return str(key).replace('-', '_').lower()


def _is_int(value):
    return type(value) is int and not isinstance(value, bool)


def _is_bool(value):
    return type(value) is bool


def _walk(value, path=''):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = key if not path else path + '.' + str(key)
            for item in _walk(child, child_path):
                yield item
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = '[' + str(index) + ']' if not path else path + '[' + str(index) + ']'
            for item in _walk(child, child_path):
                yield item
    else:
        yield path, value


def _string_values(value):
    for path, item in _walk(value):
        if isinstance(item, str):
            yield path, item


def _looks_like_product_b(payload):
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in ('format', 'sanitized', 'provenance', 'rows'))


def _looks_like_product_a(payload):
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in PRODUCT_A_ROOT_KEYS)


class Finding(object):
    __slots__ = ('rule', 'code', 'message', 'review_required')

    def __init__(self, rule, code, message, review_required=False):
        self.rule = rule
        self.code = code
        self.message = message
        self.review_required = bool(review_required)

    def as_dict(self):
        return {
            'rule': self.rule,
            'code': self.code,
            'message': self.message,
            'review_required': self.review_required,
        }


class ValidationResult(object):
    __slots__ = ('accepted', 'product', 'findings', 'review_required')

    def __init__(self, product, findings):
        self.product = product
        self.findings = tuple(findings)
        self.review_required = any(item.review_required for item in self.findings)
        self.accepted = len(self.findings) == 0

    def as_dict(self):
        return {
            'accepted': self.accepted,
            'product': self.product,
            'review_required': self.review_required,
            'findings': [item.as_dict() for item in self.findings],
        }


def _add(findings, seen, rule, code, message, review_required=False):
    key = (rule, code, message)
    if key in seen:
        return
    seen.add(key)
    findings.append(Finding(rule, code, message, review_required=review_required))


def _rule1_content(payload, findings, seen):
    def walk_keys(obj):
        if isinstance(obj, dict):
            for key, child in obj.items():
                if _norm_key(key) in CONTENT_KEY_EXACT:
                    _add(
                        findings,
                        seen,
                        1,
                        'FORBIDDEN_CONTENT_FIELD',
                        'file contains a document body, HTML/Markdown content field, or attachment field that is not in the permitted field lists: ' + str(key),
                    )
                walk_keys(child)
        elif isinstance(obj, list):
            for child in obj:
                walk_keys(child)
    walk_keys(payload)
    for path, text in _string_values(payload):
        if HTML_VALUE_RE.search(text) or MARKDOWN_VALUE_RE.search(text):
            _add(
                findings,
                seen,
                1,
                'FORBIDDEN_CONTENT_VALUE',
                'file contains HTML or Markdown content that is not in the permitted field lists at ' + (path or '<root>'),
            )
        if DATA_URI_RE.search(text):
            _add(
                findings,
                seen,
                1,
                'FORBIDDEN_ATTACHMENT_BYTES',
                'file contains attachment bytes that are not in the permitted field lists at ' + (path or '<root>'),
            )
        if FILENAME_VALUE_RE.search(text):
            _add(
                findings,
                seen,
                1,
                'FORBIDDEN_ATTACHMENT_FILENAME',
                'file contains an attachment filename that is not in the permitted field lists at ' + (path or '<root>'),
            )


def _rule2_email_or_phone(payload, findings, seen):
    for path, text in _string_values(payload):
        if EMAIL_RE.search(text):
            _add(
                findings,
                seen,
                2,
                'EMAIL_PATTERN',
                'file contains an email address pattern in a string value at ' + (path or '<root>'),
            )
        if TELEPHONE_RE.search(text):
            _add(
                findings,
                seen,
                2,
                'TELEPHONE_PATTERN',
                'file contains a telephone-number pattern in a string value at ' + (path or '<root>'),
            )


def _rule9_secrets(payload, findings, seen, under_mapping=False):
    if isinstance(payload, dict):
        keys = list(payload.keys())
        mapping_here = under_mapping or any(_norm_key(key) in SECRET_KEY_EXACT and 'mapping' in _norm_key(key) for key in keys)
        # A dict that looks like a raw-id-to-token mapping table.
        if not mapping_here and len(keys) > 0 and all(isinstance(key, str) for key in keys):
            id_like = sum(1 for key in keys if RAW_ID_KEY_RE.match(str(key)) or (not str(key).startswith('syn_') and re.match(r'^[A-Za-z0-9_-]{3,}$', str(key)) and _norm_key(key) not in PRODUCT_A_ROOT_KEYS and _norm_key(key) not in PRODUCT_B_ROOT_KEYS and _norm_key(key) not in PRODUCT_B_ROW_KEYS and _norm_key(key) not in PRODUCT_A_INTEGRITY_KEYS))
            token_values = sum(1 for value in payload.values() if isinstance(value, str) and (TOKEN_RE.match(value) or value.startswith('syn_')))
            if id_like == len(keys) and token_values == len(keys) and len(keys) >= 1:
                _add(
                    findings,
                    seen,
                    9,
                    'MAPPING_TABLE',
                    'export includes a mapping table from identifiers to tokens',
                )
                mapping_here = True
        for key, child in payload.items():
            norm = _norm_key(key)
            if norm in SECRET_KEY_EXACT:
                if 'mapping' in norm:
                    code, label = 'MAPPING_TABLE', 'a mapping table'
                elif norm in {'salt', 'salts'}:
                    code, label = 'SALT', 'a salt'
                elif norm in {'connection_string', 'connection_uri', 'dsn', 'database_url'}:
                    code, label = 'CONNECTION_STRING', 'a connection string'
                elif 'credential' in norm or 'password' in norm or 'secret' in norm or 'token' in norm or 'key' in norm:
                    code, label = 'CREDENTIAL_OR_KEY', 'keys, credentials, or secrets'
                else:
                    code, label = 'CREDENTIAL_OR_KEY', 'keys, credentials, or secrets'
                _add(
                    findings,
                    seen,
                    9,
                    code,
                    'export includes ' + label + ' (field ' + str(key) + ')',
                )
            _rule9_secrets(child, findings, seen, under_mapping=mapping_here)
    elif isinstance(payload, list):
        for child in payload:
            _rule9_secrets(child, findings, seen, under_mapping=under_mapping)
    elif isinstance(payload, str):
        if CONNECTION_URI_RE.search(payload) or USERINFO_HOST_RE.search(payload):
            _add(
                findings,
                seen,
                9,
                'CONNECTION_STRING',
                'export includes a connection string or host credential',
            )
        elif CREDENTIAL_ASSIGN_RE.search(payload):
            _add(
                findings,
                seen,
                9,
                'CREDENTIAL_OR_KEY',
                'export includes keys, salts, or credentials in a string value',
            )


def _payload_is_labeled_mock(payload, provenance=None):
    if provenance == PROVENANCE_SYNTHETIC:
        return True
    if isinstance(payload, dict) and payload.get('provenance') == PROVENANCE_SYNTHETIC:
        return True
    for _path, text in _string_values(payload):
        if MOCK_LABEL_RE.search(text):
            return True
    return False


def _obviously_fictitious(text):
    if not isinstance(text, str):
        return True
    if TOKEN_RE.match(text):
        return True
    if text.startswith('syn_'):
        return True
    if FICTITIOUS_RE.search(text):
        return True
    # ISO-8601 timestamps and permitted enum / constant strings are not tenant/user samples.
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', text):
        return True
    if text in {PRODUCT_B_FORMAT, PROVENANCE_SYNTHETIC, PROVENANCE_SANITIZED}:
        return True
    return False


def _looks_like_real_sample(text):
    if not isinstance(text, str) or not text.strip():
        return False
    if _obviously_fictitious(text):
        return False
    if EMAIL_RE.search(text) or TELEPHONE_RE.search(text) or UUID_RE.search(text):
        return True
    if RAW_ID_KEY_RE.match(text):
        return True
    # Unprefixed identifier-like tokens or bare proper-name samples.
    if re.match(r'^(?:tenant|user|kb|space|org|alias|name)[_:-].+', text, re.I):
        return True
    if re.match(r'^[A-Za-z][A-Za-z0-9_-]{2,}$', text) and not text.isupper():
        return True
    return False


def _embedded_unprefixed_samples(text):
    found = []
    if not isinstance(text, str):
        return found
    for regex in (EMAIL_RE, TELEPHONE_RE, UUID_RE):
        for match in regex.finditer(text):
            token = match.group(0)
            if not token.startswith('syn_') and not TOKEN_RE.match(token):
                found.append(token)
    for match in re.finditer(
        r'\b(?:legacy[_-])?(?:tenant|kb|user|space|org|alias|name|document|team)[_:-][A-Za-z0-9_-]+\b',
        text,
        re.I,
    ):
        token = match.group(0)
        if not token.startswith('syn_') and not TOKEN_RE.match(token) and not FICTITIOUS_RE.search(token):
            found.append(token)
    return found


def _rule11_mock_samples(payload, findings, seen, labeled_mock=None):
    if labeled_mock is None:
        labeled_mock = _payload_is_labeled_mock(payload)
    if not labeled_mock:
        # Still inspect nested objects that carry their own mock label.
        if isinstance(payload, dict):
            for child in payload.values():
                _rule11_mock_samples(child, findings, seen)
        elif isinstance(payload, list):
            for child in payload:
                _rule11_mock_samples(child, findings, seen)
        return
    for path, text in _string_values(payload):
        if _looks_like_real_sample(text) or _embedded_unprefixed_samples(text):
            _add(
                findings,
                seen,
                11,
                'MOCK_NOT_SYNTHETIC',
                'a sample labeled as a mock is not prefixed syn_ / not obviously fictitious at ' + (path or '<root>'),
            )


def _scan_generic(payload, findings, seen, provenance=None):
    _rule1_content(payload, findings, seen)
    _rule2_email_or_phone(payload, findings, seen)
    _rule9_secrets(payload, findings, seen)
    _rule11_mock_samples(payload, findings, seen, labeled_mock=_payload_is_labeled_mock(payload, provenance=provenance))


def _readme_claims_complete(readme_text, readme_claims_complete_scan):
    if readme_claims_complete_scan is True:
        return True
    if readme_claims_complete_scan is False:
        return False
    if readme_text and COMPLETE_SCAN_RE.search(readme_text):
        return True
    return False


def validate_product_a(payload, readme_text=None, readme_claims_complete_scan=None):
    """Validate a Product A aggregate-only object against official rules 1-3, 9-11."""
    findings = []
    seen = set()
    if not isinstance(payload, dict):
        _add(findings, seen, 3, 'PRODUCT_A_NOT_OBJECT', 'Product A must be a single JSON object (no CSV of raw IDs)')
        return ValidationResult(PRODUCT_A, findings)
    _scan_generic(payload, findings, seen)
    for key in payload.keys():
        if key not in PRODUCT_A_ROOT_KEYS:
            if RAW_ID_KEY_RE.match(str(key)):
                _add(
                    findings,
                    seen,
                    3,
                    'RAW_IDENTIFIER_ROW_KEY',
                    'Product A contains a string that looks like a raw business identifier used as a row key: ' + str(key),
                )
            else:
                _add(
                    findings,
                    seen,
                    3,
                    'UNPERMITTED_PRODUCT_A_KEY',
                    'Product A contains an object key other than the permitted aggregate fields: ' + str(key),
                )
        child = payload[key]
        if isinstance(child, dict) and key != 'integrity':
            for inner_key in child.keys():
                if RAW_ID_KEY_RE.match(str(inner_key)) or (
                    not str(inner_key).startswith('syn_')
                    and re.match(r'^[A-Za-z0-9_-]{3,}$', str(inner_key))
                    and inner_key not in PRODUCT_A_INTEGRITY_KEYS
                ):
                    _add(
                        findings,
                        seen,
                        3,
                        'RAW_IDENTIFIER_ROW_KEY',
                        'Product A contains a string that looks like a raw business identifier used as a row key: ' + str(inner_key),
                    )
        if isinstance(child, dict) and key == 'integrity':
            for inner_key in child.keys():
                if inner_key not in PRODUCT_A_INTEGRITY_KEYS:
                    if RAW_ID_KEY_RE.match(str(inner_key)):
                        _add(
                            findings,
                            seen,
                            3,
                            'RAW_IDENTIFIER_ROW_KEY',
                            'Product A contains a string that looks like a raw business identifier used as a row key: ' + str(inner_key),
                        )
                    else:
                        _add(
                            findings,
                            seen,
                            3,
                            'UNPERMITTED_PRODUCT_A_KEY',
                            'Product A contains an object key other than the permitted aggregate fields: integrity.' + str(inner_key),
                        )
    complete = _readme_claims_complete(readme_text, readme_claims_complete_scan)
    missing_integers = [name for name in PRODUCT_A_REQUIRED_INTEGERS if name not in payload or not _is_int(payload.get(name))]
    integrity = payload.get('integrity')
    scan_complete = isinstance(integrity, dict) and integrity.get('scan_complete') is True
    if complete and missing_integers:
        _add(
            findings,
            seen,
            10,
            'MISSING_INTEGERS_ON_COMPLETE_SCAN',
            'Product A integer fields are missing while the README claims a complete scan: ' + ', '.join(missing_integers),
            review_required=True,
        )
    if isinstance(integrity, dict) and scan_complete:
        remainder = integrity.get('unclassifiable_row_count')
        if _is_int(remainder) and remainder != 0:
            _add(
                findings,
                seen,
                10,
                'UNEXPLAINED_UNCLASSIFIABLE_ROWS',
                'integrity.scan_complete is true while unclassifiable_row_count is unexplained and non-zero, contradicting completeness; flagged for human review',
                review_required=True,
            )
        elif remainder is None:
            # A claimed complete scan with no remainder field is also incomplete bookkeeping.
            if complete or scan_complete:
                _add(
                    findings,
                    seen,
                    10,
                    'MISSING_INTEGERS_ON_COMPLETE_SCAN',
                    'Product A integer fields are missing while the README claims a complete scan: integrity.unclassifiable_row_count',
                    review_required=True,
                )
    return ValidationResult(PRODUCT_A, findings)


def _has_accompanying_shard_docs(shard_manifest, cross_shard_collision_statement):
    if shard_manifest is None or cross_shard_collision_statement is None:
        return False
    if isinstance(cross_shard_collision_statement, str) and not cross_shard_collision_statement.strip():
        return False
    if isinstance(shard_manifest, (dict, list)) and len(shard_manifest) == 0:
        return False
    if isinstance(shard_manifest, str) and not shard_manifest.strip():
        return False
    return True


def validate_product_b(
    payload,
    shard_manifest=None,
    cross_shard_collision_statement=None,
):
    """Validate a Product B candidate-pre03-v1 object against official rules 1-2, 4-9, 11-12."""
    findings = []
    seen = set()
    if not isinstance(payload, dict):
        _add(findings, seen, 4, 'PRODUCT_B_NOT_OBJECT', 'Product B must be a JSON object with format=candidate-pre03-v1')
        return ValidationResult(PRODUCT_B, findings)
    provenance = payload.get('provenance')
    _scan_generic(payload, findings, seen, provenance=provenance)
    fmt = payload.get('format')
    sanitized = payload.get('sanitized')
    if fmt != PRODUCT_B_FORMAT or sanitized is not True or provenance not in ALLOWED_PROVENANCE:
        _add(
            findings,
            seen,
            4,
            'PRODUCT_B_HEADER_INVALID',
            'Product B format must be candidate-pre03-v1, sanitized must be true, and provenance must be SYNTHETIC_EXAMPLE or SANITIZED_CANDIDATE',
        )
    if provenance == PROVENANCE_SANITIZED:
        # Official rule 12: a checker used today must accept only SYNTHETIC_EXAMPLE mocks.
        _add(
            findings,
            seen,
            12,
            'SANITIZED_CANDIDATE_NOT_ACCEPTED',
            'provenance claims SANITIZED_CANDIDATE; a checker used today must accept only SYNTHETIC_EXAMPLE mocks',
        )
    extra_root = [key for key in payload.keys() if key not in PRODUCT_B_ROOT_KEYS]
    if extra_root:
        _add(
            findings,
            seen,
            6,
            'ADDITIONAL_PROPERTIES',
            'Product B contains additional properties at the root: ' + ', '.join(str(key) for key in extra_root),
        )
    rows = payload.get('rows')
    if not isinstance(rows, list):
        if 'rows' in payload:
            _add(findings, seen, 6, 'ROWS_NOT_ARRAY', 'Product B rows must be an array')
        rows = []
    elif len(rows) > PRODUCT_B_MAX_ROWS_UNSHARDED and not _has_accompanying_shard_docs(
        shard_manifest, cross_shard_collision_statement
    ):
        _add(
            findings,
            seen,
            7,
            'UNSHARDED_ROW_OVERFLOW',
            'Product B rows.length > 10000 without an accompanying shard manifest and cross-shard collision statement',
        )
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _add(findings, seen, 6, 'ROW_NOT_OBJECT', 'Product B row ' + str(index) + ' is not an object')
            continue
        extra_row = [key for key in row.keys() if key not in PRODUCT_B_ROW_KEYS]
        if extra_row:
            _add(
                findings,
                seen,
                6,
                'ADDITIONAL_PROPERTIES',
                'Product B contains additional properties at the row level (row ' + str(index) + '): ' + ', '.join(str(key) for key in extra_row),
            )
        for field in ('proposed_space_id', 'proposed_kb_id'):
            if field in row and row.get(field) is not None:
                _add(
                    findings,
                    seen,
                    8,
                    'PROPOSED_TARGET_NOT_NULL',
                    'Product B sets ' + field + ' to a non-null value without a later official allocation ruling on file (row ' + str(index) + ')',
                )
        for field in PRODUCT_B_IDENTIFIER_FIELDS:
            value = row.get(field)
            if field not in row:
                continue
            if value is None:
                continue
            if not isinstance(value, str) or not TOKEN_RE.match(value):
                _add(
                    findings,
                    seen,
                    5,
                    'IDENTIFIER_NOT_SYN_TOKEN',
                    'Product B identifier field ' + field + ' is a non-null value that does not match ^syn_[A-Za-z0-9_-]{1,64}$ (row ' + str(index) + ')',
                )
    return ValidationResult(PRODUCT_B, findings)


def detect_product(payload):
    if _looks_like_product_b(payload) and not (_looks_like_product_a(payload) and not _looks_like_product_b(payload)):
        if _looks_like_product_b(payload):
            return PRODUCT_B
    if _looks_like_product_a(payload) and not _looks_like_product_b(payload):
        return PRODUCT_A
    if _looks_like_product_b(payload):
        return PRODUCT_B
    if _looks_like_product_a(payload):
        return PRODUCT_A
    return PRODUCT_UNKNOWN


def validate(
    payload,
    product=None,
    readme_text=None,
    readme_claims_complete_scan=None,
    shard_manifest=None,
    cross_shard_collision_statement=None,
):
    """Validate a Product A or Product B candidate export object.

    ``product`` may be ``'A'``, ``'B'``, or omitted to auto-detect.
    Companion README / shard artifacts are passed as separate arguments so
    they are not stuffed into a Product B object (official rule 6).
    """
    if product is None:
        product = detect_product(payload)
    if product == PRODUCT_A:
        return validate_product_a(
            payload,
            readme_text=readme_text,
            readme_claims_complete_scan=readme_claims_complete_scan,
        )
    if product == PRODUCT_B:
        return validate_product_b(
            payload,
            shard_manifest=shard_manifest,
            cross_shard_collision_statement=cross_shard_collision_statement,
        )
    findings = []
    seen = set()
    if not isinstance(payload, dict):
        _add(findings, seen, 4, 'UNRECOGNIZED_EXPORT', 'candidate export is not a Product A aggregate object or a Product B candidate-pre03-v1 object')
        if isinstance(payload, str):
            _scan_generic(payload, findings, seen)
        return ValidationResult(PRODUCT_UNKNOWN, findings)
    _scan_generic(payload, findings, seen)
    _add(
        findings,
        seen,
        4,
        'UNRECOGNIZED_EXPORT',
        'candidate export is not a Product A aggregate object or a Product B candidate-pre03-v1 object',
    )
    return ValidationResult(PRODUCT_UNKNOWN, findings)


def validate_json_text(text, **kwargs):
    """Validate a UTF-8 JSON text object (in-memory only; no file I/O)."""
    try:
        payload = json.loads(text)
    except ValueError as exc:
        findings = [Finding(4, 'INVALID_JSON', 'candidate export is not valid JSON: ' + exc.__class__.__name__)]
        return ValidationResult(PRODUCT_UNKNOWN, findings)
    return validate(payload, **kwargs)


def official_product_a_mock():
    """Return the official Product A synthetic example from contract section 5.1."""
    return {
        'generated_at': '2026-11-28T16:00:00+08:00',
        'scope_description': 'SYNTHETIC_EXAMPLE: fictional non-production cluster name lab-mock-cluster (no connection string)',
        'tenant_count': 3,
        'null_tenant_kb_count': 1,
        'null_tenant_document_count': 2,
        'null_tenant_version_count': 2,
        'kb_count': 5,
        'team_count': 2,
        'collaboration_group_count': 1,
        'favorites_estimate': 0,
        'favorites_estimate_note': 'SYNTHETIC_EXAMPLE: favorites not counted from any server table; placeholder zero with explicit note',
        'legacy_alias_collision_count': 1,
        'name_or_id_collision_count': 0,
        'integrity': {
            'scan_complete': True,
            'paginated': False,
            'unclassifiable_row_count': 0,
        },
    }


def official_product_b_mock():
    """Return the official Product B synthetic example from contract section 5.2."""
    return {
        'format': 'candidate-pre03-v1',
        'sanitized': True,
        'provenance': 'SYNTHETIC_EXAMPLE',
        'rows': [
            {
                'legacy_kb_id': 'syn_kb_example_001',
                'tenant_id': 'syn_tenant_example_aaa',
                'proposed_space_id': None,
                'proposed_kb_id': None,
                'alias_token': 'syn_alias_example_alpha',
                'name_token': 'syn_name_example_alpha',
            },
            {
                'legacy_kb_id': 'syn_kb_example_002',
                'tenant_id': None,
                'proposed_space_id': None,
                'proposed_kb_id': None,
                'alias_token': 'syn_alias_example_alpha',
                'name_token': 'syn_name_example_beta',
            },
        ],
    }
