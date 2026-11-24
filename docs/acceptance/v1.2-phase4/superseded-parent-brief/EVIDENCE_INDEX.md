# Phase4 evidence index

Generated 2026-11-24T20:49:26.308341+08:00 Asia/Shanghai. Tested implementation: `24c4be242edf765020d295d413091ec12e6b0a52`.

| Independent result | Passed | Skipped | Evidence |
|---|---:|---:|---|
| L1 stdlib-only unittest | 337 | 92 | l1-stdlib-only.log; 429 discovered |
| L2 full-dependency unittest | 426 | 3 | l2-full-and-build.log; 429 discovered |
| Independent pytest | 426 | 3 | l2-full-and-build.log; 148 subtests reported separately, NOT added |
| Golden CLI cases (not methods/subtests) | 60 | 0 | benchmark-raw.log / benchmark-metrics.json / benchmark-report.md |

L1 skips: 88 optional HTTP methods, 1 optional official-wire method, 3 opt-in live Qdrant methods.
L2 skips: the same3 unconfigured live Qdrant methods.
L2 has one installed Starlette/httpx TestClient deprecation warning, disclosed rather than suppressed.
No ResourceWarning/unraisable diagnostic and no deprecated-license build warning occurred.

Actual Python3.13.5; all55 src files pass Python3.9 AST, not a real3.9 runtime claim.
The extracted wheel ran all four handlers under `-S` with a third-party-import blocker.
Core METADATA has no runtime dependencies; optional SDK requires Python>=3.10.
Wheel (not committed): `knowledge_sdk-1.2.0-py3-none-any.whl`.
SHA256: `73c768a25039af546303aeeaf40539e04cc88f43297f93c64ffaf9e7a69b917d`.

## Raw/generated evidence SHA256

- `l1-stdlib-only.log`: `5c2423c4d2025bbaccf7a353eecf3f885bcd53fca8ebea4acb0b9dc9dbb58cac`
- `l2-full-and-build.log`: `feb2eb3e5d3ebf887d01f69140b57bbc389659ffc02a124ad651208446c0d4a8`
- `l3-local-mcp-wire.log`: `43c60ddfb032c9e502fb3f4bebf2cb8577dbc2effa0a0ff15b567ae5adf62fee`
- `benchmark-raw.log`: `77eea7df3dda65ed7cfba01e4dcf70395151d88f2b978b892445a18023db869f`
- `benchmark-metrics.json`: `a2830ac8f2e0bb9e465ac1e9ebfcfd6316ff90e1e340dfdb81cdd0721d49844c`
- `benchmark-report.md`: `f64837bf04501376c3cc38f12c8b83fb2abe5fd9f8825be476aa3329f02769d1`
