# Knowledge SDK 现状与能力基线审计报告（Phase 0）

> 文档路径：`docs/architecture/knowledge-sdk-alignment/00_CURRENT_STATE_AUDIT.md`
> 审计对象：`flykingvip-cloud/knowledge-sdk`（Team A 主仓）及对照仓 `flykingvip-cloud/openbot-vp`（Team B 只读核查）
> 审计日期：2026 年 11 月 24 日
> 审计状态：已完成代码实审与纯标准库测试实跑（注：本环境无 `knowledge-sdk` 远端写权限，文档已生成并待 Team A 提交入库）

---

## 一、审计范围、仓库基线与缺失前置文档声明

### 1.1 实际核查的 Git 基线

| 仓库 | 检出分支 | HEAD Commit | 工作区状态 | 关键远端基线与标签 |
|---|---|---|---|---|
| `knowledge-sdk` | `feat/q3-phase2-rerank-eval` | `d1532951b08c8ef950dc604aa3427ceb9eab5d75` | Clean（无未提交修改） | `origin/main`：`b953c99`；注释标签 `v2.0.0`：`4afc1d7`（指向 `b953c99`） |
| `openbot-vp` | `main` | `58287aa449fb499f49080c467df60b774b458222` | Clean（只读对照审计） | 公开主分支 `main` |

`knowledge-sdk` 当前远端存在完整的 Q1–Q3 分阶段研发分支轨迹，无其他未知开发人员遗留的脏提交或并行冲突分支：

- `origin/main`（`b953c99`）：Q2 收口基线与 Python 3.9 CI 修复，已打 `v2.0.0` 注释标签。
- `origin/feat/q1` 序列：`phase2-policy-engine`（`eecb025`）、`phase3-anchors-storage-v2`（`83f4a0d`）、`phase4-mcp-benchmark`（`9c6a64b`）。
- `origin/feat/q2` 序列：`q2-phase1-outbox-audit-impact`（`6fc5b19`）、`q2-phase2-postgres-pgvector`（`04b8c93`）、`q2-phase3-l2-governance-packs`（`adc3228`）、`q2-phase4-oidc-scim-connectors`（`a5d1432`）。
- `origin/feat/q3` 序列：`q3-phase1-agent-runtime`（`69b6c98`，已退出待合入）、`q3-phase2-rerank-eval`（`d153295`，最新开发头，待独立复核）。

### 1.2 实际检查的核心源码与文档范围

本次审计直接读取并核验了 `knowledge-sdk` 以下路径的真实源码与配置：

- 构建与发布：`pyproject.toml`、`.github/workflows/tests.yml`、`.github/workflows/q2-m4-l4.yml`。
- 领域契约：`src/knowledge_sdk/contracts/models.py`、`policy.py`、`identity.py`、`runtime.py`、`anchors.py`、`uri.py`、`events.py`、`governance.py`、`impact.py`、`issues.py`、`packs.py`、`src/knowledge_sdk/exceptions.py`。
- 存储与迁移：`src/knowledge_sdk/storage/sqlite_store.py`、`postgres_store.py`、`postgres_schema.sql`、`migrations.py`、`dr_drill.py`、`local_blob.py`。
- 权限与身份：`src/knowledge_sdk/permissions/engine.py`、`src/knowledge_sdk/server/auth.py`、`oidc.py`、`scim.py`。
- 摄取、检索与评测：`src/knowledge_sdk/ingestion/`（`fingerprint.py`、`parsers/`、`chunkers/`）、`src/knowledge_sdk/retrieval/hybrid.py`、`rerank.py`、`calibration.py`、`adapters/pgvector_index.py`。
- 客户端、服务端与工具：`src/knowledge_sdk/client/local.py`、`client/http_client.py`、`server/app.py`、`mcp/tools.py`、`connectors/`。
- 仓库文档：`docs/architecture.md`、`docs/api-contract.md`、`docs/agent-runtime.md`、`docs/enterprise-identity-connectors.md`、`docs/governance-packs.md`、`docs/mcp-integration.md`、`docs/postgres.md`、`docs/rerank-evaluation.md`、`docs/acceptance/v2.1-q3-phase2/Q3_PHASE2_HANDOFF_REPORT.md`。

### 1.3 前置文档缺失与未覆盖范围声明

按照“未实际读取不得假定存在”的原则，明确记录以下缺失项：

1. **未在两个仓库中检索到“统一架构方案”与“OpenBot 首轮审计报告”正式文档**：经遍历 `knowledge-sdk/docs/` 与 `openbot-vp/docs/`，仅在 `openbot-vp/docs/design/openbot-knowledge-rag-integration-plan-2026-06-14.md` 中发现 OpenBot 2026 年 6 月的历史设计稿（该文曾决定不移植 `@knowledge-sdk` 而改由 `src/retrieval/` + `src/gateway/knowledge/` 自研）。除本任务指令正文外，不存在可读取的跨仓“统一架构方案”或“OpenBot 首轮审计报告”文件，需在 Phase 2 评审前由架构 owner 补充归档路径或以本批次 Phase 0–2 产出作为正式基线。
2. **未在当前容器运行真实 PostgreSQL / Qdrant / OIDC 外部实例测试**：当前容器仅验证纯标准库路径（`python3 -S -W error::ResourceWarning`）；全依赖与真实 PostgreSQL+pgvector 的运行结论引用自 `feat/q3-phase2-rerank-eval@d153295` 对应 GitHub Actions 实跑记录（Run `45542279327`）及仓内归档证据，未在本机重复拉起 Postgres/Qdrant 容器。
3. **未审查生产集群配置与线上数据**：本仓库不含 `Dockerfile`、`docker-compose.yml`、Helm Chart 或生产 `.env`，生产部署拓扑与线上数据规模不在本次代码审计可见范围内。

---

## 二、测试、CI 与部署形态现状

### 2.1 当前测试与 CI 状态

| 检查维度 | 执行方式 / 证据来源 | 实际结果 | 说明 |
|---|---|---|---|
| 本次审计实跑（纯标准库） | `python3 -S -W error::ResourceWarning -m unittest discover -s tests -t .`（作用于 `d153295`） | **894 tests：617 passed，277 skipped，0 failed，0 ResourceWarning**（54.26s） | 277 项跳过均为可选依赖（`fastapi`、`psycopg`、`cryptography`、`pypdf`、在线 Qdrant） |
| GitHub Actions 四作业 CI | `feat/q3-phase2-rerank-eval@d153295`（Run `45542279327`） | **4/4 作业全绿**；全依赖测试 891 通过、3 项在线 Qdrant 跳过；双引擎黄金基准 **115/115**（SQLite & PostgreSQL+pgvector） | 已修复此前 Python 3.9 CI 夹具关闭问题 |
| 离线重排评测集（Q3-M2） | `docs/acceptance/v2.1-q3-phase2/pairwise-eval-*.json` | SQLite/PG NDCG@3 提升至 `1.0`、拒答 `24/24`、越权 `0` | 属固定离线小集增益，候选路径延迟明显上升，不代表生产效果 |
| 包版本号与依赖边界 | `pyproject.toml` | `version = "1.2.0"`；`dependencies = []`（零强依赖）；`requires-python = ">=3.9"` | 注意 Git 标签已推进至 `v2.0.0`，但 `pyproject.toml` 版本号仍停留在 `1.2.0`，存在版本元信息漂移 |

### 2.2 当前部署与运行形态

根据 `pyproject.toml [project.scripts]` 与 `src/knowledge_sdk/`，SDK 支持 4 种 CLI 入口与 3 种集成模式：

- `knowledge-sdk-server`（`knowledge_sdk.server.cli:main`）：基于 FastAPI + Uvicorn 的 HTTP API 服务（可选 extra `http`），同时可挂载静态管理台（`ui_prefix`）与 `/v1/mcp`。
- `knowledge-sdk-mcp`（`knowledge_sdk.mcp.server:main`）：独立可信 MCP 网关入口。
- `knowledge-sdk-migrate`（`knowledge_sdk.storage.migrations:main`）：SQLite / PostgreSQL Schema 迁移工具。
- `knowledge-sdk-governance`（`knowledge_sdk.governance.cli:main`）：治理运维 CLI。
- 缺失项：仓库根目录无 `Dockerfile`、无生产 compose/Helm 清单、无 `/metrics` Prometheus 暴露端点、无结构化 OpenTelemetry 链路追踪集成。

---

## 三、数据存储与 Schema v5 现状

### 3.1 双引擎表结构对比

`knowledge-sdk` 已实现 SQLite 与 PostgreSQL 双存储引擎（Schema Version 均为 `5`），并配套迁移与 DR 演练模块（`migrations.py`、`dr_drill.py`）：

- **SQLite（`src/knowledge_sdk/storage/sqlite_store.py`，`PRAGMA user_version = 5`，27 张业务表 + FTS5）**：
  `knowledge_bases`、`kb_members`、`documents`、`document_versions`、`document_acls`、`chunks`、`pending_indexes`、`consumer_bindings`、`evidence_anchors`、`policy_rules`、`evidence_issues`、`outbox_events`、`audit_events`、`usage_events`、`impact_alerts`、`webhook_subscriptions`、`webhook_deliveries`、`review_decisions`、`evidence_packs`、`connector_sync_state`、`identity_principals`、`scim_groups`、`scim_group_members`、`agent_profiles`、`task_contexts`、`context_snapshots`、`task_revocations`。
- **PostgreSQL（`src/knowledge_sdk/storage/postgres_schema.sql`，29 张表 + pgvector `chunk_embeddings`）**：
  在 SQLite 27 张表基础上额外包含 `resource_directory`（跨租户资源路由索引）与 `replay_nonces`（跨实例 HMAC 防重放表），并由 `PgVectorIndex`（`src/knowledge_sdk/retrieval/adapters/pgvector_index.py`）管理 `chunk_embeddings`。
- **PostgreSQL 行级安全（RLS）机制**：
  由 `src/knowledge_sdk/storage/migrations.py` 与 `pgvector_index.py` 对所有租户表执行 `ALTER TABLE <t> ENABLE/FORCE ROW LEVEL SECURITY`，并在 `postgres_store.py` 事务内通过 `set_config('app.current_org_id', org_id, true)` 绑定会话隔离上下文（`resource_directory` 与 `schema_migrations` 除外）。

### 3.2 存储模型的关键结构性观察

1. **租户键单一化**：全部 27+ 租户表均以 `org_id` 作为唯一隔离主键，未区分平台级 `tenant_id`、组织级 `organization_id` 与工作空间级 `workspace_id`。
2. **版本键为自增整数**：`document_versions.version` 为正整数 `1, 2, 3...`，与 OpenBot 的字符串型 `version_id` + `version_label` 不同。
3. **无软删除/回收站与异步摄取作业表**：文档仅有 `archived` 布尔标记与 `lifecycle_state`（`draft/in_review/approved/published/rejected/superseded/revoked`），缺少“从空间移入回收站 -> 恢复 -> 永久硬删除”以及“异步摄取/向量化任务队列表（IngestionJob）”。
4. **缺少知识资产子类型模型**：`documents` 表默认面向文件型文档，无 `asset_type` 字段区分普通文件、网页快照（Web Snapshot）、结构化数据集（Dataset Schema）、代码/文件夹同步项或 Agent 生成交付物。

---

## 四、API、身份权限、Python SDK 与 MCP 能力现状

### 4.1 HTTP API（v1）与 Python SDK

- **统一操作表**：`src/knowledge_sdk/client/http_client.py` 定义 `OPERATIONS` 映射，包含 **62 个 `/v1/*` 操作**，`server/app.py` 自动遍历 `OPERATIONS` 注册路由，并额外提供：
  - 系统与会话：`GET /v1/health`、`POST /v1/auth/session`、`POST /v1/auth/logout`、`POST /v1/mcp`、`POST /v1/outbox/drain`（兼容别名）。
  - REST 快捷路由：`GET /v1/documents/{doc_id}/versions/{version}`、`POST /v1/documents/{doc_id}/archive`、`POST /v1/documents/{doc_id}/restore`、`POST /v1/documents/{doc_id}/acl`。
  - SCIM 2.0 路由：`src/knowledge_sdk/server/scim.py` 通过 `mount_scim` 挂载 `/scim/v2/*`。
- **序列化协议风险（高关注）**：`docs/api-contract.md` 与 `http_client.py` 显示，当前 HTTP v1 采用 Python 强绑定的 `{"params": {...}}` 请求包裹与 `__type__` / `__mapping__` dataclass 类型标记直出响应，**并非标准 RESTful 风格或跨语言 JSON Schema 契约**。TypeScript/Node.js（OpenBot Gateway）直接调用时需处理 `__type__` 编解码，耦合度偏高。
- **错误模型偏粗**：`src/knowledge_sdk/exceptions.py` 仅有 6 个异常类（`KnowledgeSDKError`、`PermissionDeniedError`、`NotFoundError`、`ValidationError`、`TamperedExcerptError`、`ConflictError`），缺少机器可读的稳定 `error_code`（如 `IDENTITY_REVOKED`、`POLICY_GENERATION_STALE`、`TENANT_MISMATCH`、`QUOTA_EXCEEDED`、`VERSION_CONFLICT`）与 `request_id` 字段规范。
- **Python SDK**：`LocalKnowledgeClient` 与 `HttpKnowledgeClient` 保持方法签名一致，零外部依赖即可引入客户端（`http_client.py` 仅使用 `urllib` 与 HMAC 签名）。但目前尚无官方 TypeScript / Node.js Client SDK。

### 4.2 认证、身份与授权机制

- **认证通道**：
  1. 宿主 HMAC 签名头（`server/auth.py`）：校验 `X-KB-Actor`、`X-KB-Timestamp`、`X-KB-Nonce`、`X-KB-Signature` 及可选 `X-KB-Agent`、`X-KB-Purpose`，具备 `InMemoryReplayStore` / `SQLiteReplayStore` / `PostgresReplayStore` 防重放与多密钥轮换。
  2. 企业 OIDC Bearer JWT（`server/oidc.py`）：支持 JWKS 验签、`iss`/`aud`/`exp`/`nbf` 校验与本地会话签发。
  3. SCIM 2.0 目录同步（`server/scim.py`）：支持 `IdentityPrincipal` 与 `scim_groups` 同步，用户禁用或权限变更时递增 `policy_generation` 实现秒级撤权。
- **权威策略引擎（`permissions/engine.py`）**：
  `DefaultPolicyEngine` 严格执行多步骤评估：同组织强校验 -> 文档显式 Deny 优先（覆盖 Owner 与 Admin）-> 空间边界/成员校验 -> 空间与文档 Allow 交集 -> `ResourceRights`（四权分离）与 `Purpose` 约束 -> Agent 与 User 权限交集（`intersect_decisions`）-> Fail-Closed `RedactionRegistry` 脱敏。
- **待对齐缺口**：
  - `Actor` 与 `IdentityPrincipal` 缺少 `issuer`、`tenant_id` 与 `actor_type`（human/agent/service）显式分层字段。
  - `kb_members` 仅有 `grant_kb_member`，缺少 `list_kb_members` 与 `revoke_kb_member` 公开客户端方法。

### 4.3 检索、重排、证据链与 MCP

- **检索流水线（`retrieval/hybrid.py`）**：
  - `keyword` 模式：SQLite FTS5 / PostgreSQL CJK `tsvector`，按排名折算 RRF 分数 `1 / (60 + rank)`。
  - `vector` 模式：内存余弦 / `PgVectorIndex` / `QdrantVectorIndex`，按排名折算 `1 / (60 + rank)`。
  - `hybrid` 模式：固定采用 RRF 融合 `keyword_weight / (60 + kw_rank) + (1 - keyword_weight) / (60 + vec_rank)`（默认 `keyword_weight = 0.5`）。
  - Q3-M2 新增：可插拔 `Reranker`（内置零依赖 `DeterministicLexicalReranker`）、通道独立 `ScoreCalibrator`（输出 `[0, 1]` 的 `calibrated_score`）与低置信拒答阈值 `min_calibrated_score`。
- **证据链与 URI（`contracts/uri.py`、`anchors.py`、`packs.py`）**：
  - 版本化 URI v2：`kb://org/<org_id>/doc/<doc_id>@<version>[#chunk=<id>|#anchor=<id>]`（严格规范化百分号编码）。
  - 具备 `EvidenceAnchor`、三阶段确定性重锚、`MaterialReceipt` 篡改校验、`EvidenceIssue` 流内纠偏与 `EvidencePack`（JSON / RO-Crate 1.2 实时重验导出）。
- **MCP 工具（`mcp/tools.py`）**：
  已实现 4 个工具：`search_evidence`、`verify_citation`、`get_evidence_pack`、`report_evidence_issue`，内置 `_IntersectionEngine` 强制用户与 Agent 权限交集。

---

## 五、六类能力成熟度分类矩阵

严格区分实现与验证状态，不将占位代码或未验证功能计为完成：

| 分类 | 典型能力与代码证据 | 说明 |
|---|---|---|
| **1. 已实现且经过测试** | Schema v5 双引擎（SQLite + PG+pgvector + RLS）、8 步 `DefaultPolicyEngine` + `RedactionRegistry`、`EvidenceAnchor` + `kb://` URI v2、链式 `AuditEvent` + 事务 `OutboxEvent` + `ImpactRadar`、L2 审批状态机 + `EvidencePack`（RO-Crate 1.2）、OIDC/SCIM + `policy_generation` 秒级失效、Q3-M1 `AgentProfile`/`TaskContext`/`ContextSnapshot`/`MidTaskRevocation`、Q3-M2 `DeterministicLexicalReranker`/`ScoreCalibrator`/`PairwiseRetrievalEvaluator`、4 个 MCP 工具 | 纯 stdlib 894 项测试（617 通过/0 失败）与 CI Run `45542279327`（891 全依赖通过、双引擎 115/115 黄金基准）提供直接验证 |
| **2. 已实现但缺少完整验证** | `QdrantVectorIndex`（在线服务测试在 CI 长期跳过 3 项）；`DeterministicLexicalReranker` 在大规模真实语料上的生产延迟与效果；`parsers/office.py` 与 `parsers/layout.py` 对复杂多栏 PDF/扫描件/大表格的鲁棒性；高并发多租户场景下的 PostgreSQL 连接池与压测 | 需结合真实 OpenBot 语料与生产级压测补齐验证 |
| **3. 仅接口或模型、无完整实现** | 领域扩展协议（`Embedder`、`OCRHook`、`Reranker` 外部语义重排实现仅有 Protocol 无生产适配器）；`Connector` 仅有 `ControlledFilesystemConnector` 与 `WebhookSyncConnector` 两个标杆实现，尚无飞书/Notion/Confluence/Web 爬虫生产连接器 | 协议已稳定，生产适配器待按需接入 |
| **4. 仅设计文档、无代码实现** | `EvidenceGraph` / 正交 Claim 与关系表（仅在 Q3 协议规范中规划为 Schema v6）；创新药早研试点 `pack-pharma` / Ontology / 实体图谱（规划在 Q3-M4）；跨仓统一 OpenBot Adapter 方案 | 未落地代码，属于后续演进或待对齐范围 |
| **5. 当前完全缺失** | `update_kb` / `delete_kb`、KB 成员列表/移出/邀请态流转、`list_document_versions` / 版本回滚 / 回收站软删与硬删、异步摄取队列 `IngestionJob`、多资产类型（Web Snapshot / Dataset / Deliverable / Folder Sync）、标准 REST/JSON Schema HTTP v2 契约、官方 TypeScript SDK、Prometheus 指标与 OpenTelemetry、标准容器化部署清单 | 承接 OpenBot 现有 90 个 `knowledge.*` RPC 前必须明确哪些由 SDK 补齐、哪些留在 OpenBot |
| **6. 与 OpenBot 当前业务存在冲突** | 见下表 5.1 关键冲突项清单（共 8 项结构性冲突） | 需在 Phase 1 逐项映射并在 Phase 2 联合冻结契约 |

### 5.1 本轮审计确认的 8 项核心跨仓冲突摘要

1. **成员身份键冲突**：OpenBot `knowledge-base-members.ts` 与 `knowledge-base-permissions.ts`（`activeMemberRole`）以归一化 `email` 作为成员匹配键；SDK 以稳定 `user_id`（及 SCIM `external_id`）作为唯一主体键。
2. **Agent 越权绑定冲突（高危安全差异）**：OpenBot `knowledge-base-permissions.ts`（`canReadViaRobotBinding`）允许只要 `knowledgeBase.robotIds.includes(actor.agentId)` 且同租户即可读库，**即使调用用户本人不是该库成员**；SDK 强制执行 `EffectivePermission = User ∩ Agent`，绝不允许 Agent 放大用户权限。
3. **租户语义与别名漂移冲突**：OpenBot 通过 `src/gateway/tenant-canonicalization.ts` 维护历史租户别名（如 `upbeyond-91aeea3c -> 001`）且允许 `tenantId: null` 个人库；SDK 仅以强必填 `org_id` 做单层隔离。
4. **资产与空间生命周期冲突**：OpenBot 拥有完整的知识库修改/删除、文档脱离/回收站/恢复/硬删、个人文档版本对比、异步向量化队列；SDK 当前仅有 `create_kb`、`archive`/`restore` 与 `lifecycle_state`，缺少空间改删与回收站语义。
5. **版本标识模型冲突**：OpenBot `document_versions` 使用字符串 `version_id` + `version_label`；SDK 使用单调递增整数 `version: int`。
6. **检索分数与融合语义冲突**：OpenBot `kb-retrieve.ts` 采用 `vectorWeight=0.7`、`textWeight=0.3` 线性加权合并 `1 - dist` 与 BM25，再乘以 `governance/retrieval-scoring.ts` 的 `trust * freshness * verified * claimConflict` 因子；SDK 采用 RRF `w / (60 + rank)` 融合 + 独立 `ScoreCalibrator`（`calibrated_score ∈ [0, 1]`）。
7. **Citation URI 协议冲突**：OpenBot 使用 `ku://kb/<kbId>/doc/<docId>@<versionId>[#<section>]` 与 `ku://workspace/...`、`obj:doc:<docId>`；SDK 使用 `kb://org/<org_id>/doc/<doc_id>@<version>[#anchor=<id>|#chunk=<id>]`。
8. **HTTP 传输契约冲突**：SDK 当前 HTTP v1 使用 `{"params": ...}` + `__type__` dataclass 序列化；OpenBot Gateway 为 TypeScript/Node.js，需要语言无关、稳定版本化的标准 JSON 契约与机器可读错误码。

---

## 六、Phase 0 结论与进入 Phase 1 的建议

- **结论**：`knowledge-sdk` 在**权限权威判定、多租户 RLS 隔离、不可变证据锚点、防篡改审计账本、事务 Outbox、L2 受控发布、Agent Runtime 预算与中途撤权、可插拔重排校准**等 Knowledge Core 核心护城河上已经高度扎实（双引擎 115/115 黄金基准全绿）；但在**空间/文档完整 CRUD 生命周期、多资产类型建模、异步摄取作业、跨语言 HTTP 契约、租户/主体分层与 OpenBot 权限语义收敛**上存在明确差距。
- **下一步**：立即在 `01_OPENBOT_REQUIREMENTS_MAPPING.md`（Phase 1）中逐条拆解 OpenBot 90 个 `knowledge.*` RPC、检索编排与 Agent 工具调用路径，输出完整差距矩阵与调整优先级，再在 `02_DOMAIN_MODEL_ALIGNMENT.md` 与 `03_DOMAIN_CONTRACTS.md` 提交 Phase 2 契约冻结草案。
