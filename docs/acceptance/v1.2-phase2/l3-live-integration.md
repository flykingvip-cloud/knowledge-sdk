# L3 — Q1-M2 actual HTTP integration

Local isolated real loopback HTTP: PASS. Raw transcript: l3-local-http.log.

Command:
`PYTHONPATH=src .venv-http/bin/python docs/acceptance/v1.2-phase2/live_http_probe.py`

Actual run used temporary port 53287, in-memory business storage, a dedicated
SQLite replay database in a temporary directory, a random signing secret (never
logged), production-default disabled demo signer, and /kb/ui. Process stopped;
its dedicated replay files were removed. No persistent service was left running.

Actual transport exercised HttpKnowledgeClient and HMAC headers over sockets:
- Unsigned business API 401; UI/config/i18n 200/no-store; signer paths both 404.
- Signed external purpose denied with default rights (403), then permitted after
  an explicit authorized rights update. Retrieval itself invoked no generator.
- Signed typed agent restricted to kb-a: kb-b read 403, search empty.
- Registered regex redaction: search excerpt and hash match delivered masked
  content; retrieve/version/inspection contain no synthetic source token;
  masked reference/receipt consistent.
- Explicit ask delivers only masked evidence to an offline local stub.
- Missing hook: search empty, retrieve 403, ask refused without invoking stub.
- Signed body purpose/agent/policy_context injection 400; invalid typed agent 401.

No actual external generator/embedding/vector provider was configured or called.
The probe's real_model_calls=0 field records that construction, not an independent
network-egress audit or proof of a remote model integration. It is not a semantic
retrieval benchmark and makes no claim about arbitrary plugins/providers.

Real online Qdrant / embedding / semantic-synonym tests: **SKIPPED — not configured**
(3 existing live methods skipped explicitly in L1/L2). No existing collection or
Mac Qdrant instance was contacted. Real reverse proxy: **NOT_RUN**; previous ASGI
root_path tests in L2 are not a live gateway deployment or proxy acceptance.
Prior Phase 1 online-semantic/proxy/browser gaps remain historical gaps.
