# Source gaps for Wave-V21-0 Team A

The official 10 standardized audit field names from section 7 of 《Master Architecture v2.1 — OpenBot 既有能力清单与 Knowledge SDK 边界规范》 are now known from the Owner-provided source document (SHA-256 `c5196ff1d050ac6477cc064390a708a4d10121cf7fe300bb24764a87a2a5b1c2`). The full architecture document is cited, not committed into this repository. The document's `signoff_status` remains `READY_FOR_OWNER_SIGNOFF_AND_STREAM_A_E_AUDIT_CLOSURE`. Owner providing the source document is not baseline signoff.

The previously used English proposed column names (`capability_name`, `authority_system_of_record`, `public_contract`, `source_evidence`, `persistence_or_execution_depth`, `identity_and_policy_generation`, `fail_closed_behavior`, `duplicate_build_status`, `test_evidence`, `residual_gap`) are retired. They were never official. The Stream D SDK-side table in the handoff is now mapped to the official section-7 names.

Remaining gaps:

1. Team B Stream A–D OpenBot audit reports, remapped to the official fields (Team B stated they will re-issue Stream A/B reports after VB-4).
2. Stream D extra: 「OpenBot 本地知识模块向 SDK 委派收口清单，与 Space Pre-v7 B2-2 124 项实审完全对齐」— Team B / OpenBot work; not produced by Team A.
3. Stream B extras (逐连接器区分生产可用驱动 vs Demo/Mock; 明确解锁 `knowledge-object-only` 所需的安全门禁) and Stream C extras (核实 AOR Stage 4 真实测试状态; 区分确定性探针 vs LLM-as-Judge 缺口) — Team B; not written here.
4. Formal baseline signoff is not granted.
5. Wave-V21-1 is not unlocked. This handoff is not formal Wave-V21-0 acceptance.
6. OpenBot-side CI gating for the Stream E contract pack is a Team B residual. knowledge-sdk CI already includes `validate.py` and job `v21-wave0-boundaries`.
