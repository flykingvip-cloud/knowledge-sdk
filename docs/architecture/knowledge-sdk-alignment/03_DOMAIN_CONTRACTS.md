# Knowledge SDK 统一领域契约冻结提案（Phase 2B · 待评审）

> 文档路径：`docs/architecture/knowledge-sdk-alignment/03_DOMAIN_CONTRACTS.md`
> 契约状态：**待评审（Freeze Proposal v0.1）** — 未经 Team A、Team B 及架构 owner 联合批准前，本文件中的所有新增字段、新端点与安全切换规则均视为提案，不得单方锁定为不可逆破坏性变更。
> 兼容性红线：现有 `knowledge-sdk` `/v1/*` 62 个操作、Python `LocalKnowledgeClient`/`HttpKnowledgeClient` 签名、SQLite/PostgreSQL Schema v5 及 115 条黄金基准必须保持向后兼容。

---

## 一、契约冻结清单总览与评审状态

| 编号 | 契约名称 | 当前 SDK 对应源码 | 目标变更层级 | 冻结状态 |
|---|---|---|---|---|
| **C-01** | 统一身份与调用上下文（Identity & Context） | `contracts/models.py`、`contracts/identity.py`、`server/auth.py`、`server/oidc.py` | Layer 1 + Layer 2（废除邮箱键与绕权） | **待评审** |
| **C-02** | 租户与知识空间（Tenant & Space） | `contracts/models.py`、`client/local.py`、`storage/postgres_schema.sql` | Layer 1 + Layer 2（租户策略） | **待评审** |
| **C-03** | 知识资产与回收站（Asset & Lifecycle） | `contracts/models.py`、`client/local.py` | Layer 1 + Layer 2（受控硬删） | **待评审** |
| **C-04** | 版本与不可变历史（Version & Rollback） | `contracts/models.py`、`contracts/governance.py` | Layer 1 + Layer 2（新增 `version_id` 列） | **待评审** |
| **C-05** | 证据链、锚点与双轨 URI（Evidence & Citation） | `contracts/uri.py`、`contracts/anchors.py`、`contracts/packs.py` | Layer 1（Adapter 双轨映射） | **待评审** |
| **C-06** | 检索、重排与校准（Retrieval & Scoring） | `retrieval/hybrid.py`、`rerank.py`、`calibration.py` | Layer 1 | **待评审** |
| **C-07** | 同步与异步摄取作业（Ingestion & Job） | `ingestion/`、`storage/sqlite_store.py` | Layer 2（新增作业表与端点） | **待评审** |
| **C-08** | 外部连接器同步协议（Connector Plan/Commit） | `connectors/`、`contracts/identity.py` | Layer 1 | **待评审** |
| **C-09** | 跨语言 HTTP 传输、错误码与版本策略（HTTP Contract） | `server/app.py`、`client/http_client.py`、`exceptions.py` | Layer 2（标准 JSON 契约） | **待评审** |

---

## 二、核心领域契约草案（JSON Schema 语义定义）

### C-01 统一身份与调用上下文契约（待评审）

所有经过 OpenBot Gateway 或外部业务系统发往 Knowledge SDK 的请求，必须携带经可信网关验签或 OIDC 校验后的统一上下文：

```json
{
  "request_id": "req_01JXYZ...",
  "tenant_id": "001",
  "actor": {
    "issuer": "https://idp.example.com",
    "subject_id": "usr_9f82a1c4",
    "actor_type": "human",
    "roles": ["member", "rd_researcher"],
    "department_ids": ["dept_oncology"],
    "ancestor_department_ids": ["dept_rd", "dept_root"],
    "org_roles": ["employee"],
    "clearance_level": "confidential",
    "clearance_tags": ["project_alpha"],
    "policy_generation": 12,
    "session_id": "sess_abc123"
  },
  "agent": {
    "agent_id": "agent_lit_reviewer",
    "profile_generation": 3,
    "task_id": "task_01JXYZ..."
  },
  "purpose": "ground_internal_llm"
}
```

**强制安全不变量（冻结后不可违背）**：
1. `subject_id` 为唯一持久化授权主键；`email` 不得参与任何权限判定或成员查找。
2. 当 `agent` 存在且 `actor.actor_type == "human"` 时，授权结果恒等于 `Policy(actor) ∩ Policy(agent_profile)`；**严禁因 `agent_id` 绑定某空间而跳过 `actor` 的空间/文档 ACL 校验**。
3. 当后端目录（SCIM/OIDC）中主体的 `active == false` 或 `stored.policy_generation > actor.policy_generation` 时，立即返回 `403 POLICY_GENERATION_STALE` / `IDENTITY_REVOKED`。
4. `tenant_id` 必须已由调用方网关规范化（SDK 映射至 `org_id` 并注入 PostgreSQL `app.current_org_id` RLS 会话变量）。

### C-02 租户与知识空间契约（待评审）

```json
{
  "kb_id": "kb_01JXYZ...",
  "tenant_id": "001",
  "name": "肿瘤早研文献库",
  "description": "面向肿瘤研发团队的受控知识空间",
  "space_type": "department",
  "visibility": "team",
  "governance_tier": "l2_controlled",
  "owner_user_id": "usr_9f82a1c4",
  "owner_department_id": "dept_oncology",
  "tags": ["oncology", "literature"],
  "status": "active",
  "metadata": {},
  "created_at": "2026-11-24T00:00:00Z",
  "updated_at": "2026-11-24T00:00:00Z"
}
```

**拟增接口契约**：
- `get_kb(kb_id)` -> `KnowledgeBase`
- `update_kb(kb_id, {name?, description?, visibility?, tags?, metadata?, governance_tier?})` -> `KnowledgeBase`（变更 `visibility`/`governance_tier` 须写审计日志）
- `archive_kb(kb_id)` / `restore_kb(kb_id)` -> `KnowledgeBase`（软归档，禁止默认物理级联删库）
- `list_kb_members(kb_id, cursor?, limit?)` -> `{items: KBMember[], next_cursor}`（`KBMember` 仅含 `user_id`、`role`、`granted_by`、`granted_at`）
- `revoke_kb_member(kb_id, user_id)` -> `null`

### C-03 知识资产与生命周期契约（待评审）

```json
{
  "doc_id": "doc_01JXYZ...",
  "tenant_id": "001",
  "kb_id": "kb_01JXYZ...",
  "owner_id": "usr_9f82a1c4",
  "title": "KRAS G12C 临床前综述.pdf",
  "asset_type": "document",
  "source_kind": "upload",
  "source_ref": "upload://sha256/...",
  "visibility": "team",
  "current_version": 3,
  "current_version_id": "ver_01JXYZ...",
  "lifecycle_state": "published",
  "archived": false,
  "archived_at": null,
  "tags": ["kras", "preclinical"],
  "metadata": {},
  "domain_metadata": {
    "schema_ref": null,
    "payload": {}
  },
  "valid_from": null,
  "valid_to": null
}
```

**生命周期操作语义对齐**：
- 正常写入 -> `archived = false`，`lifecycle_state = "published"`（L1）或 `"draft"`（L2）。
- 移入回收站 -> `archive(doc_id)`，置 `archived = true`，立即从所有普通检索和消费中隐藏。
- 查看回收站 -> `list_documents(kb_id=..., archived_only=True)`。
- 回收站恢复 -> `restore(doc_id)`，恢复可见性并触发索引校验。
- 永久删除（Layer 2，需审批后实施） -> `purge_document(doc_id, reason)`：仅允许空间 Admin 执行，先校验不存在冻结证据包引用冲突，随后写入不可变 `AuditEvent` 与 `TombstoneRecord`，清理 Blob、Chunks 与向量索引。

### C-04 版本与安全回滚契约（待评审）

```json
{
  "doc_id": "doc_01JXYZ...",
  "version": 3,
  "version_id": "ver_01JXYZ...",
  "version_label": "v3",
  "filename": "KRAS_G12C_review.pdf",
  "raw_hash": "sha256:...",
  "semantic_hash": "sha256:...",
  "lifecycle_state": "published",
  "author_id": "usr_9f82a1c4",
  "reviewer_id": "usr_reviewer01",
  "publisher_id": "usr_publisher01",
  "source_issue_id": "",
  "rollback_from_version": null,
  "created_at": "2026-11-24T00:00:00Z",
  "published_at": "2026-11-24T00:05:00Z"
}
```

**版本不变量**：
1. 历史版本永远不可变（append-only）。
2. `rollback_document(doc_id, target_version)` 始终生成新版本 `current_version + 1` 并记录 `rollback_from_version = target_version`，保证历史引用与审计链永不断裂。
3. 补齐 `list_document_versions(doc_id, limit?, cursor?)` 与 `diff_document_versions(doc_id, from_version, to_version)`。

### C-05 证据链与双轨 Citation 契约（待评审）

```json
{
  "evidence_id": "ev_01JXYZ...",
  "tenant_id": "001",
  "kb_id": "kb_01JXYZ...",
  "doc_id": "doc_01JXYZ...",
  "version": 3,
  "version_id": "ver_01JXYZ...",
  "chunk_id": "chk_00012",
  "anchor_id": "anc_p4_t2",
  "title": "KRAS G12C 临床前综述.pdf",
  "section_path": ["2. 药效学数据", "2.1 细胞活性"],
  "excerpt": "在 NCI-H358 细胞系中测得 IC50 为 14 nM...",
  "excerpt_hash": "sha256:...",
  "canonical_uri": "kb://org/001/doc/doc_01JXYZ...@3#anchor=anc_p4_t2",
  "locator": {
    "page": 4,
    "char_start": 1820,
    "char_end": 1956,
    "table_cell": null
  },
  "masking_summary": "",
  "verification_status": "verified"
}
```

**双轨映射规则（在 OpenBot Adapter 层执行）**：
- `SDK -> OpenBot`：对外透出 `canonical_uri`（`kb://...`）作为权威引用；若旧 UI 依赖 `ku://`，由 Adapter 通过 `kb_id`、`doc_id`、`version_id`、`section_path` 生成兼容字段 `legacy_ku_uri`。
- `OpenBot -> SDK`：存量 `ku://kb/<kbId>/doc/<docId>@<versionId>` 由 Adapter 查询版本号后转换为 `KnowledgeRef` 调用 SDK `verify_ref` / `consume` / `verify_receipt`。

### C-06 检索、重排与校准契约（待评审）

```json
{
  "request": {
    "query": "KRAS G12C IC50 数据",
    "mode": "hybrid",
    "limit": 10,
    "scope": {
      "mode": "spaces",
      "kb_ids": ["kb_01JXYZ..."]
    },
    "filters": {
      "asset_types": ["document", "web_snapshot"],
      "tags": ["kras"],
      "lifecycle_states": ["published"]
    },
    "rerank": {
      "enabled": true,
      "reranker_id": "default",
      "top_k": 40
    },
    "calibration": {
      "enabled": true,
      "min_calibrated_score": 0.35
    }
  },
  "response": {
    "mode": "hybrid",
    "reranker_id": "deterministic_lexical_v1",
    "calibrator_id": "default_channel_calibrator_v1",
    "calibration_applied": true,
    "candidate_budget_exhausted": false,
    "filtered_below_threshold": 2,
    "hits": [
      {
        "doc_id": "doc_01JXYZ...",
        "kb_id": "kb_01JXYZ...",
        "version": 3,
        "version_id": "ver_01JXYZ...",
        "chunk_id": "chk_00012",
        "title": "KRAS G12C 临床前综述.pdf",
        "score": 0.84,
        "raw_score": 0.0312,
        "rerank_score": 0.84,
        "calibrated_score": 0.86,
        "excerpt": "...",
        "excerpt_hash": "sha256:...",
        "source_uri": "kb://org/001/doc/doc_01JXYZ...@3#chunk=chk_00012",
        "truncated": false,
        "masking_summary": "",
        "score_breakdown": {
          "keyword_rank": 1,
          "vector_rank": 2,
          "fusion_method": "rrf_k60"
        }
      }
    ]
  }
}
```

**检索不变量**：
1. 权限过滤与 Fail-Closed 脱敏必须在进入 `Reranker` 与返回 `SearchHit` 之前完成，绝不对无权片段打分或返回计数侧信道。
2. OpenBot `RetrievalService` 联邦排序统一消费 `calibrated_score`（范围 `[0.0, 1.0]`）；禁止将未校准的 RRF 分数直接与 `1 - dist` 混排。

### C-07 异步摄取作业契约（待评审）

```json
{
  "job_id": "job_01JXYZ...",
  "tenant_id": "001",
  "kb_id": "kb_01JXYZ...",
  "doc_id": "doc_01JXYZ...",
  "version": 4,
  "idempotency_key": "idem_upload_98123",
  "asset_type": "document",
  "status": "indexing",
  "progress_pct": 70,
  "stats": {
    "chunks_total": 42,
    "chunks_indexed": 30,
    "anchors_created": 18
  },
  "error_code": null,
  "error_message": null,
  "created_at": "2026-11-24T00:00:00Z",
  "updated_at": "2026-11-24T00:00:12Z"
}
```

- 支持幂等提交（同一 `tenant_id + idempotency_key` 重试返回同一 `job_id`，避免重复建版本）。
- 既有同步 `ingest()` 保持完全兼容，适合小文本即时入库与单测。

### C-08 外部连接器 Plan / Commit 同步契约（待评审）

```json
{
  "connector_id": "conn_fs_01",
  "kb_id": "kb_01JXYZ...",
  "cursor_in": "cur_20261124_001",
  "plan": {
    "to_upsert": [
      {"external_id": "path:/sop/assay-v2.md", "content_hash": "sha256:...", "asset_type": "document"}
    ],
    "to_tombstone": [
      {"external_id": "path:/sop/deprecated.md", "reason": "deleted_at_source"}
    ],
    "unchanged_count": 128
  },
  "commit_result": {
    "cursor_out": "cur_20261124_002",
    "upserted_doc_ids": ["doc_01JXYZ..."],
    "revoked_doc_ids": ["doc_01OLD..."],
    "failed_items": []
  }
}
```

- 撤权一致性：收到 `TombstoneRecord` 后，SDK 在事务内撤权/归档对应文档并触发 `MidTaskRevocation` 与 `ImpactAlert`，保障源端删权后正在运行的 Agent 立即失效。

---

## 三、跨语言 HTTP 契约演进与标准错误码体系（C-09 · 待评审）

### 3.1 HTTP API 版本化演进路线（二选一，待联合评审）

| 候选方案 | 描述 | 优点 | 权衡 |
|---|---|---|---|
| **方案 A（推荐）：并行引入标准 JSON `/v2/*` 端点** | 完整保留现有 `/v1/*`（62 个 `{"params": ...}` + `__type__` 端点）供既有 Python `HttpKnowledgeClient` 零破坏运行；新增 RESTful `/v2/*`（纯 JSON Schema、无 `__type__` 标记、自动生成 OpenAPI 3.1 文档），供 OpenBot Gateway TypeScript SDK 与外部系统对接 | 100% 保护存量 v1 与 115 条黄金回归；跨语言契约干净规范；易于独立版本演进与文档生成 | 服务端需维护轻量 `/v2/*` 路由适配层（复用同一 `LocalKnowledgeClient` 内核，无重复业务逻辑） |
| **方案 B：在 `/v1/*` 上通过协商头切换纯 JSON** | 沿用 `/v1/*` 路径，新增 `Accept: application/vnd.knowledge.v2+json` 去除 `__type__` 标记 | 路由数量不翻倍 | RPC 风格路径与 REST 风格混杂，OpenAPI 文档生成与客户端代码生成复杂度高 |

### 3.2 统一错误响应信封与稳定错误码（推荐冻结）

所有 `/v2/*` 错误响应统一采用结构化信封（含 `request_id` 便于跨 OpenBot/SDK 链路排障，严禁在报错体中泄漏无权文档的存在性或正文内容）：

```json
{
  "error": {
    "code": "POLICY_GENERATION_STALE",
    "message": "Principal policy generation is stale; re-authentication required.",
    "retryable": false,
    "request_id": "req_01JXYZ...",
    "details": {}
  }
}
```

| HTTP 状态码 | 稳定 `error.code` | 对应 SDK 异常 | 说明 |
|---|---|---|---|
| `400` | `VALIDATION_ERROR` | `ValidationError` | 参数校验失败、非法 URI 编码或范围冲突 |
| `401` | `UNAUTHENTICATED` / `SIGNATURE_INVALID` / `REPLAY_DETECTED` | `ValidationError` | 缺失凭证、HMAC 验签失败、OIDC Token 失效或 Nonce 重放 |
| `403` | `PERMISSION_DENIED` | `PermissionDeniedError` | 跨租户、无空间/文档读权、命中显式 Deny 或不满足 `User ∩ Agent` |
| `403` | `IDENTITY_REVOKED` / `POLICY_GENERATION_STALE` | `PermissionDeniedError` | SCIM 禁用主体或策略代次过期，客户端须刷新会话 |
| `403` | `REDACTION_FAIL_CLOSED` | `PermissionDeniedError` | 脱敏钩子异常触发 Fail-Closed 拒放 |
| `404` | `RESOURCE_NOT_FOUND` | `NotFoundError` | 资源不存在（或因防存在性泄漏策略对无权用户统一伪装返回） |
| `409` | `CONFLICT` / `IDEMPOTENCY_CONFLICT` / `LIFECYCLE_CONFLICT` | `ConflictError` | 并发版本冲突、幂等键载荷不一致或 L2 审批状态非法跃迁 |
| `422` | `TAMPERED_EXCERPT` / `ANCHOR_UNRESOLVABLE` | `TamperedExcerptError` | 证据摘录哈希校验失败或引用不可验证 |
| `429` | `RATE_LIMITED` / `CONTEXT_BUDGET_EXCEEDED` | `ValidationError` | 触发限流或超过 Agent `ContextBudget` 上限 |
| `503` | `BACKEND_UNAVAILABLE` | `KnowledgeSDKError` | 存储、向量索引或外部依赖暂不可用（`retryable: true`） |

---

## 四、Phase 2 评审签认检查表（等待联合确认）

在进入 Phase 3 编码落地之前，请 Team A、Team B 与架构 owner 确认以下 6 项冻结决策：

1. **安全红线签认**：确认 OpenBot 废除 `canReadViaRobotBinding` 越权路径，全面执行 `User ∩ Agent` 权限交集，并将 `robotIds` 迁移为 `AgentProfile.allowed_kb_ids`。
2. **主体主键签认**：确认成员与 ACL 主键全面收敛至稳定 `user_id`（`issuer + sub`），邮箱仅留作 OpenBot 产品层邀请属性。
3. **个人空间租户策略签认**：在 §2.2 方案 A（企业用户个人空间归属主租户 `space_type=personal`）与方案 B（全部独立个人租户）中拍板。
4. **版本双标识签认**：确认保留整数 `version` 主序并新增不可变 `version_id` 与 `version_label`。
5. **HTTP 演进路线签认**：在 §3.1 方案 A（并行新增标准 JSON `/v2/*`）与方案 B（`/v1/*` 内容协商）中拍板。
6. **既有 Q3-M2 分支处理签认**：确认 `feat/q3-phase2-rerank-eval@d153295` 独立验收及合入基线的先后顺序，避免与 Phase 3 对齐改造分支产生冲突。
