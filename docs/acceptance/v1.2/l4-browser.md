# L4 — real browser

**NOT_RUN — no real browser was operated in this execution environment.**
No screenshot, visual pass, DOM equivalence, or browser-network evidence claimed.
The dependency-free VM DOM/localization harness belongs to L1/L2 only.

## Reproducible handoff (not started/left running)

Existing checkout: `/workspace/knowledge-sdk`, branch `feat/phase1-v1.2-baseline`.
Choose an unused loopback port outside 3000/3001/8000/8002/8090/8091. Example
18765 is illustrative; verify it is free before starting, never kill its owner.

For isolated demonstration (random HMAC key generated server-side, no external
models or vector backend):

```bash
cd /workspace/knowledge-sdk
work=$(mktemp -d)
PYTHONPATH=src .venv-http/bin/python -m knowledge_sdk.server \
  --host 127.0.0.1 --port 18765 --demo-seed \
  --replay-db "$work/replay.sqlite3" --ui-prefix /kb/ui
```

Open `http://127.0.0.1:18765/kb/ui` on the box's own desktop. Stop with Ctrl-C and
remove only that newly created temporary directory after the process exits.
Do not load or modify the owner's Mac service at 8091.

Breakpoints/checklist:
1. Network tab: only same-origin assets/config/business requests. No inline-CSP
   errors, third-party fonts/CDN, automatic ask/search, or external model calls.
2. Default Chinese; switch English; refresh preserves language; return Chinese.
   Layout/nav/identity no mixed interface text. User titles, text, excerpts and
   metadata retain original language and exact content across switching.
3. Open all four views, inspect document versions/ACL, keyword retrieval,
   explicit-only ask/refusal, references/receipts. Preserve arbitrary raw JSON.
4. Verify base URL `/kb/ui` and trailing `/kb/ui/`; assets and i18n load correctly.
5. Production gate: stop demo server; restart same isolated setup **without**
   --demo-seed, passing freshly generated secret via env, never browser or logs:
   `KNOWLEDGE_AUTH_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"`
   then same CLI command minus --demo-seed. Identity form must start disabled;
   POST `/kb/ui/demo/sign` and `/ui/demo/sign` return 404 with any demo headers;
   unsigned business operations return 401. No host session gateway implemented.
6. Optional real reverse-proxy stage must separately validate a trusted root_path
   and exact upstream raw signed targets (including query/percent escapes).

Record actual browser/version, screenshots, URLs, network observations and any
failures here only after performing them. L4 remains NOT_RUN until then.
