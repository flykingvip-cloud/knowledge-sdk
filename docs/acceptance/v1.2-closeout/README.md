# Q1-M2 Task 0 — Phase 1 closeout

Base: 602373fce3b40ba87b7d94894a5b85cc634e5ac9, feature branch only.

Deterministic SQLite replay connection closure (including replay/capacity/error
returns), bool rejection, case-insensitive extension headers with duplicate
rejection, dynamic health version, restored routes.__doc__, SPDX MIT license.
Build-only setuptools floor raised from 61 to 77.0.3 for PEP 639 SPDX support;
no new core runtime dependency. Version remains 1.2.0.

Raw independent final evidence:
- L1: 215 passed, 68 skipped (283 unittest methods).
- L2: 280 passed, 3 skipped (283 unittest methods), run with
  `-W error::ResourceWarning`; no ResourceWarning/unraisable output.
- Independent pytest: 280 passed, 3 skipped; do not add to unittest counts.
- Build successful, no deprecated license-table warning. An existing test-client
  httpx deprecation is unrelated and not addressed by adding dependencies.

The first L2 attempt detected two test-owned, not store-owned, unclosed SQLite
connections when the new regression ran gc.collect(). Both original Phase 1
test connections now also use contextlib.closing. The initial complete output is
preserved as l2-initial-resource-warnings.log, not claimed warning-clean; the
final l2-full-and-build.log is the strict rerun after the fix.

Original docs/acceptance/v1.2/ logs and gaps remain historical and unchanged.
No actual online semantic/proxy or browser validation added by this closeout.
