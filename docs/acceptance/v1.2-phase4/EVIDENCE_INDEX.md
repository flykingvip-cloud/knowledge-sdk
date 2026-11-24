# Authoritative t37u Phase4 evidence index

Generated 2026-11-24T21:10:11.894882+08:00 Asia/Shanghai. Exact tested implementation: `cf30cf2bd250e15c8e575fd65e3880207034b598`.
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
SHA256: `c8fb0eeeffeb79bd898cfa2df16fc2f9e9809313f9e6adf821d9f85d6f5663a2`.

## Current raw/generated file SHA256

- `l1-stdlib-only.log`: `e2f8cd19f2389c27b9332a7c3d3287048485811cbbfa38e453859a5916ae9890`
- `l2-full-and-build.log`: `76aea160666f3201f8a99a506035de998af2aa70176ad333f1ad174cd74d82ab`
- `l3-local-http-stdio.log`: `463a2e97e87c4c64ef850abd18a3e792ee625e89a166936599f8759f17070e1e`
- `benchmark-60-run.log`: `93890f4531d5d1dd89878fc3b53270914d4ea29d145b6e14a23bf5e99a8ab1e2`
- `benchmark-60-report.json`: `fc98ed75481ca1796b5aa18d86711eb162b4a1ac718b0ee554fcfa69cb1a5c96`
- `benchmark-60-report.md`: `6a3ea18a02582613f6926d4ef4ea0d5333929f6d8d7ba8d797a8726633e1d185`
