# SDK-side adapter review assets — DRAFT, NOT A FREEZE

All C-01…C-09 contracts remain `draft-pending-m1-freeze`. These assets implement
no `/v2` route, no new database schema and no OpenBot integration. Team B and
architecture-owner review, seven joint decisions and M1 signatures remain pending.
Q3-M2 independent acceptance is not inferred from this branch baseline.

The `.yaml` is intentionally JSON syntax (a YAML 1.2 subset), so standard-library
readers can consume it without a new runtime dependency. `generate_assets.py`
reads the supplied immutable `03` examples and generates exact domain field names,
the TS DTOs, six fixtures and fixture-schema mapping. The source archive is not
rewritten. Re-generation is checked byte-for-byte in tests. `validate_assets.py`
resolves and checks all local schema references, object/array/scalar types,
required fields, strict unknown fields, enums, nullable values, finite numbers,
score bounds, URI syntax, timestamps, security requirements and cross-field
user/agent and URI-coordinate invariants, plus deliberate invalid inputs. Optional
development-only OpenAPI 3.1 / JSON Schema validators run additional standards
checks; TS compilation runs separately when the compiler is available.

Run `PYTHONPATH=src python -S .../contracts/validate_assets.py` or use the optional
dev environment for the official standards validators. Never interpret fixture
identity headers as untrusted caller authority. X-Request-Id is correlation only;
X-Tenant-Id is a trusted gateway's already-verified canonical mapping, bound to
OIDC / gateway authentication. Subject, agent profile and policy generations are
server-verified. A profile KB allowlist never grants a nonmember human access.

Draft consistency choices (subject to M1 review): spaces/none/documents/all scope
selectors extend C06's one spaces example consistently with existing SDK scopes;
member roles stay viewer/editor/admin (v5 has one separate intrinsic owner);
version-path parameter encoding, ingest bodies and evidence-verify request shape
are provisional examples because 03 does not specify their complete request
schemas. Nullable schema-ref/table-cell/error fields remain explicit. Only
calibrated scores are bounded [0,1]; diagnostic raw/rerank values stay finite but
are not assumed cross-channel comparable. Pagination/job lifecycle/purge remain
future contracts, not implemented operations. Future async job error_message must
be sanitized, never a raw exception.

The error envelope exactly nests code/message/retryable/request_id/details under
`error` as C09 specifies. All 17 listed stable error codes are enumerated. These
codes do not replace v1 errors in this wave.

`DualUriMapping` explicitly requires authoritative tenant/KB/document/integer
version/opaque version-ID coordinates. A kb:// string alone cannot recover kb_id
or version_id; a trusted lookup is necessary. The typed ku:// representation is
adapter-only and never rewrites the SDK's canonical runtime URI. No information-
losing bare-string round trip is claimed.

## Executable draft URI reference helper (Wave1p5)

uri-mapping.ts performs no I/O and adds zero external runtime dependencies. It
requires an authoritative explicit DualUriMapping table; no tenant/KB/version-ID
is guessed from a bare URI. Both bases must match all supplied coordinates.
Legacy section fragments and section_path metadata are supplied, not inferred
into SDK anchors; a missing/ambiguous lookup fails closed. No mapping authenticates
content or grants authority; SDK verification/policy checks are still mandatory.

Lossless conditions: exact full strings in a unique mapping, positive safe JS
integer version, canonical UTF-8 percent quoting (same quoting as Python safe=''),
non-control opaque IDs, and no dot path segments. Unicode/reserved characters
remain percent-encoded opaque values; percent text is decoded exactly once, never
double-decoded. Encoded slash inside a non-traversal opaque ID is not a filesystem
path. Traversal/control/malformed/alias/query/duplicate-selector inputs reject.
The stricter adapter subset does not change the SDK parser or canonical URIs.
section_path is cloned/frozen intact, not treated as a grant/selector derivation.

Development toolchain is locked in package-lock.json; npm ci installs TypeScript
for checks only. Run tsc --noEmit, then compile mapping/test to a disposable
output directory and node that test JS. These tests EXECUTE, not just typecheck.

Lookup tables must be one-to-one in BOTH directions; a unique canonical match
with an ambiguous legacy reverse lookup is rejected even on forward conversion.
When a legacy section fragment is supplied, its once-decoded segments must match
section_path exactly. A fragment-less whole-document legacy URI may still carry
explicit retained metadata; no anchor is inferred from it. Extra record/coordinate
fields fail closed instead of leaking undeclared data into the typed DTO.
