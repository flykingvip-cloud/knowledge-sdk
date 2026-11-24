# Authoritative t37u Phase4 evidence index

Generated 2026-11-24T21:10:11.894882+08:00 Asia/Shanghai. Exact tested implementation: `502cf6e87943dfca55f21eddd8a5e58759af9d07`.
Earlier parent-brief architecture/logs remain clearly SUPERSEDED under the historical subdirectory.

| Independently reported runner | Passed | Skipped | Discovery / notes |
|---|---:|---:|---|
| L1 python3 -S strict-warning unittest | 350 | 96 | 446 discovered |
| L2 full-dependency strict-warning unittest | 443 | 3 | 446 discovered |
| Independent pytest | 443 | 3 | 167 subtests separately reported, NOT added |
| Separate stdlib golden runner | 60 | 0 | 20/10/10/10/10 groups; not unittest method count |

L1: 92 optional HTTP methods +1 optional HTTP-wire method +3 opt-in live Qdrant methods skipped.
L2: only the3 unconfigured opt-in live Qdrant methods skipped. Skips are not passes.
One installed Starlette/httpx TestClient deprecation warning is disclosed, not suppressed.
No ResourceWarning/unraisable diagnostic and no obsolete-license build warning occurred.

Actual interpreter3.13.5. Python3.9 AST:57 src +4 tests/benchmark files; no local real3.9 runtime claim.
Core imports + four tools + real console-entrypoint stdio ran from an independently extracted wheel
under -S and a third-party import blocker. Fresh optional env contains no third-party MCP SDK.
METADATA: core zero dependencies, Python>=3.9, optional mcp exactly FastAPI/uvicorn, correct entrypoint;
UI assets and six MCP modules present; superseded handlers/transport modules absent.

Wheel binary not committed: `knowledge_sdk-1.2.0-py3-none-any.whl`.
SHA256: `68b73729a05382b2e6a0c978581da32bf787cb6036458584cddcceb1eaddcfc4`.

## Current raw/generated file SHA256

- `l1-stdlib-only.log`: `6870cc87dacb293b7394730ac5319a7f95a2e891320c3ea0c3741401a1e3e742`
- `l2-full-and-build.log`: `632be2e8844183cc22dc4560b91d51b3c5a1ad768ee6832e5e42d64b3d0bb184`
- `l3-local-http-stdio.log`: `0563dec9b86a119841ff7d7cbe1ff4ba550aa2afeee69bc8cd5d5fc818a02eeb`
- `benchmark-60-run.log`: `ec8f26457b81b36ef25b3e5e2d9ee512ab77d8d559d8b6ea21aa91bd1b5d9a07`
- `benchmark-60-report.json`: `b5593ef6bcbacfc2d5cd7ee0cd9e3a7605824612e974e8c8559f466d211fd39d`
- `benchmark-60-report.md`: `1782eb2074361914f23b8954cee06551ee7769d696745fa0067eca548edf0d37`
