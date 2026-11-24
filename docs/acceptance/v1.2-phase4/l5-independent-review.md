# L5 — independent architecture acceptance

**PENDING_EXTERNAL — 待独立验收架构师复核（Q1-M4 / B06 / Q1 退出门禁）。**

The owner's approval to enter Phase4 is not acceptance of this implementation.
Local tests, official MCP wire checks and offline goldens are executor self-tests.
They do not establish design-partner adoption, an external enterprise client's <=10min
integration, online semantic quality, production rollout readiness or real PDF/OCR extraction.

| Q1 exit item | Engineering / self-test state | External acceptance |
|---|---|---|
| Optional official MCP transport + four thin tools | COMPLETED / SELF_TESTED locally | Pending independent B06 review |
| Trusted HMAC Actor/Agent, bound external purpose, replay/rotation, no model identity | COMPLETED / SELF_TESTED | Pending host-gateway/security review |
| Queue-only evidence feedback, formal knowledge unchanged | COMPLETED / SELF_TESTED | Pending reviewer workflow acceptance; no new UI |
| Existing KnowledgeScope SQL prefilter + authority / hard500 budget | COMPLETED / SELF_TESTED | No online semantic performance claim |
| Exactly60 offline deterministic golden hard gate | COMPLETED / SELF_TESTED 60/60 | Dataset coverage and Q1 exit signoff pending |
| Core stdlib / schema2 / wheel / Python3.9 syntax compatibility | SELF_TESTED; actual runtime3.13.5 | Real3.9 runtime not locally exercised; remote CI not observed |
| Actual official MCP client / loopback two-worker wire | SELF_TESTED | Not an external customer/client deployment |
| External design partner / enterprise integration <=10min | PENDING_EXTERNAL / NOT_RUN | Required external evidence absent |
| Online Qdrant / embeddings / external model | SKIPPED / NOT_RUN | No credentials/configuration or authorization to existing collections |
| Production proxy, host login/CSRF, deployment | NOT_RUN / NOT_DEPLOYED | Separate operational approval required |
| Browser/visual | NOT_RUN; unchanged frontend | No L4 claim |
| Real PDF/OCR | NOT_RUN; offline host layout fixture only | No real PDF coordinate-parser claim |

No automatic closure of all Q1 exit conditions is claimed. No Q2 governance,
immutable commercial EvidencePack, Outbox/Postgres, model training, unified source UI,
production deployment, main merge, tag or release is authorized or performed.
