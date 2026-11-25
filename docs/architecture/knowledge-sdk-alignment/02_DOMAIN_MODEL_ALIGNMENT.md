# Knowledge SDK 与 OpenBot 统一领域模型对齐方案（Phase 2A · 评审草案）

> 文档路径：`docs/architecture/knowledge-sdk-alignment/02_DOMAIN_MODEL_ALIGNMENT.md`
> 契约状态：**待评审（Proposal）** — 本文为 Team A 提交的 Phase 2 领域模型对齐提案，在 Team A、Team B 与架构 owner 联合评审冻结前，**不构成不可逆的跨仓破坏性变更**。
> 设计约束：保护 `knowledge-sdk` 既有核心契约、零运行时强依赖（`dependencies = []`）及 Schema v5 向后兼容；不引入 OpenBot 私有业务依赖。

---

## 一、对齐总原则与分层演进策略

为兼顾“统一知识核心”与“零停机渐进演进”，所有模型调整严格划分为两层：

| 变更层级 | 定义 | 执行前提 | 典型内容 |
|---|---|---|---|
| **Layer 1（兼容增量扩展）** | 向后兼容的字段扩展、新增查询/管理方法、新增独立表或可选参数，不改变已有 v1 语义与 115 条黄金用例 | 遵循 SDK 既有规范，经常规 CR 与双引擎测试即可推进 | `get_kb`、`update_kb`、`list_kb_members`、`revoke_kb_member`、`list_document_versions`、`asset_type` 可选扩展、可选 `description`/`metadata` |
| **Layer 2（跨仓冻结与破坏性/敏感变更）** | 涉及跨仓契约冻结、安全授权语义变更、Schema 结构升级（v5 -> v6+）、历史数据迁移、生产检索/URI 切换或新增 `/v2/*` 契约 | **必须经 Team A + Team B + 架构 owner 联合评审签认，并附可回滚迁移方案后方可实施** | 废除 OpenBot `canReadViaRobotBinding` 绕权、邮箱成员迁移至稳定 `user_id`、`tenant_id` 规范化落地、HTTP v2 标准 JSON 契约、双轨 URI 切换、`IngestionJob` 与受控 `purge_document` |

---

## 二、八大核心领域模型对齐设计

### 2.1 身份与主体模型（Identity）· 状态：待评审

**当前差异**：
- `knowledge-sdk` 使用 `Actor(user_id, org_id, roles, department_ids, org_roles, clearance_level, clearance_tags, policy_generation, session_id)` 与 `IdentityPrincipal`，未显式区分 `issuer` 与 `actor_type`。
- `openbot-vp` 通过 Gateway 解析 `userId`/`email`/`tenantId`/`agentId`，且成员表以 `email` 作为匹配主键。

**统一对齐方案（推荐）**：
1. **全局稳定主体标识**：采用 `(issuer, subject_id)` 组合语义（在单租户内部继续映射至稳定 `user_id`，禁止使用可变 `email` 作为 ACL 或成员表主键）。`email` 仅作为展示属性或 OpenBot 产品层邀请媒介，一旦用户接受邀请须解析为稳定 `subject_id` 后再写入 SDK。
2. **主体类型显式分层（`actor_type`）**：
   - `human`：终端人类用户，具备组织、部门、角色、密级与 `policy_generation`。
   - `agent`：代用户执行的 AI Agent，必须同时携带 `delegating_user`（被代理人类主体）与 `agent_id`，权限强制满足 **`Effective = User ∩ AgentProfile`**。
   - `service`：独立后台服务或经明确审批的公域机器人主体，具备独立服务账号与显式空间授权，严禁冒充无权人类用户或通过空间 `robotIds` 绕过 ACL。
3. **兼容过渡（Layer 1）**：SDK `Actor` 保留全部现有字段不变，新增可选字段 `issuer: str = ""`、`actor_type: str = "human"`、`tenant_id: str = ""`（未填时默认等价于 `org_id`），确保历史调用方零破坏。

### 2.2 租户、组织与知识空间模型（Tenant & Space）· 状态：待评审

**当前差异**：
- `knowledge-sdk` 以单层 `org_id` 驱动全部表与 PostgreSQL `FORCE RLS`（`app.current_org_id`），支持 `space_type`（`enterprise_public` / `department` / `personal`）与 `governance_tier`（`l1_agile` / `l2_controlled`）。
- `openbot-vp` 区分 `tenantId`（可能为 `null`）与 `visibility`（`private` / `team` / `enterprise`），并维护历史别名映射 `tenant-canonicalization.ts`。

**统一对齐方案（推荐）**：
1. **租户唯一权威键**：SDK 内部继续以规范化 `tenant_id`（物理列兼容 `org_id`，PostgreSQL RLS 策略维持 `app.current_org_id` 零破坏）作为硬隔离边界。OpenBot Gateway 在反腐败层（Adapter）完成历史租户别名收敛，**SDK 严禁硬编码业务租户别名**。
2. **个人空间租户归属策略（需联合评审二选一）**：
   - **方案 A（推荐）**：企业用户的个人空间仍归属其主租户 `tenant_id`（`org_id = user.tenant_id`），通过 `space_type = "personal"` + `owner_user_id = user.user_id` 实现个人私密隔离；真正无企业归属的独立个人用户使用确定性个人租户 `personal:<user_id>`。优势：支持同一用户在企业租户下统一审计、跨空间联合检索与离职合规回收。
   - **方案 B**：所有个人空间独立划分至 `personal:<user_id>` 租户。劣势：企业用户在一次检索中同时查“个人库 + 部门库 + 企业库”需跨租户联邦，破坏单租户事务与 RLS 简洁性。
3. **空间能力补齐（Layer 1）**：
   - 保留 `visibility` 与 `space_type` 的既有兼容映射（`enterprise -> enterprise_public`、`team -> department`、`private -> personal`）。
   - 为 `KnowledgeBase` 扩展可选元数据 `description: str = ""`、`tags: Tuple[str, ...] = ()`、`metadata: Dict[str, Any]`、`status: str = "active"`（支持 `active` / `archived`）。
   - 补齐 `get_kb`、`update_kb`、`archive_kb`、`restore_kb`、`list_kb_members`、`revoke_kb_member`。
   - OpenBot 的 `robotIds` **不进入 `KnowledgeBase` 核心表**，而是映射至 SDK 既有的 `AgentProfile.allowed_kb_ids`，保持“空间归空间、Agent 授权归策略引擎”的清晰解耦。

### 2.3 知识资产模型（Asset）· 状态：待评审

**当前差异**：
- `knowledge-sdk` 核心对象为 `Document`，默认以文档文件为抽象。
- `openbot-vp` 在同一知识空间下承载普通文件、网页快照（`web_source_snapshots`）、结构化数据集（`dataset_schemas`）、代码/本地同步文档以及 Agent 生成交付物（`agent_generated_knowledge` / `deliverables`）。

**统一对齐方案（推荐）**：
1. **保持 `Document` 为统一资产基类（Layer 1 兼容扩展）**：不破坏现有 `documents` 表与 `Document` dataclass，新增可选扩展字段：
   - `asset_type`：`document`（默认） | `web_snapshot` | `dataset` | `deliverable` | `structured_record` | `code_artifact`。
   - `source_kind`：`upload` | `connector` | `web_crawl` | `agent_generated` | `api_sync`。
   - `source_ref`：可选外部来源标识（如外部 URL、Connector 外部 ID、交付物追踪 ID），供幂等更新与去重。
   - `tags` 与 `domain_metadata`：通用标签及未来垂类扩展槽位（如创新药研发的靶点/适应症/管线阶段/文献 DOI 元数据，SDK 核心不写死垂类字段，通过 Schema Registry / Extension Pack 校验）。
2. **空间归属与回收站语义**：
   - 每个 `Document` 拥有唯一权威主空间 `kb_id`（保障 ACL 边界与 RLS 清晰）；若 OpenBot 需“一个文档在多处引用”，优先以 `KnowledgeRef` / 空间引用视图实现，不引入多主写冲突。
   - 回收站映射：OpenBot 的 `detach`（移入回收站）对应 SDK `archive(doc_id)`；`recycle.list` 对应扩展后的 `list_documents(kb_id=..., archived_only=True)`；`restore` 对应 SDK `restore(doc_id)`；`delete`（永久删除）对应新增的受控 `purge_document(doc_id)`（需管理员权限、记录审计与 Tombstone、异步/事务清理 Chunk 与向量）。

### 2.4 版本与生命周期模型（Version & Lifecycle）· 状态：待评审

**当前差异**：
- `knowledge-sdk`：`DocumentVersion.version` 为正整数（`1, 2, 3...`），附带 `raw_hash`、`semantic_hash`、`lifecycle_state`（`draft/in_review/approved/published/rejected/superseded/revoked`）及 L2 三分离审批元数据。
- `openbot-vp`：`document_versions` 使用字符串 `version_id` 与 `version_label`（如 `v1`、`v2`），支持版本列表与版本内容对比。

**统一对齐方案（推荐）**：
1. **双标识兼容模型**：
   - 保留 `version: int`（逻辑语义为单调递增版本号 `version_no`，保证 SDK 既有 `kb://...@<int>` 100% 兼容）。
   - 新增稳定不可变 `version_id: str`（如确定性或 ULID 格式 `ver_<id>`，存量历史记录按确定性规则回填）与可选展示字段 `version_label: str`（默认 `v{version}`）。
2. **双哈希去重一致性**：双方均已采用 `raw_hash` + `semantic_hash`，统一冻结哈希算法规范（SHA-256 归一化文本），避免重复摄取产生无意义空版本。
3. **版本操作补齐**：新增 `list_document_versions(doc_id)`、`diff_document_versions(doc_id, from_version, to_version)`（可按 Chunk/段落输出结构化差异）及安全回滚 `rollback_document(doc_id, target_version)`（**绝不覆写历史版本**，而是基于目标历史版本内容创建新的递增版本并写入审计账本）。

### 2.5 证据链、锚点与 Citation 模型（Evidence & Citation）· 状态：待评审

**当前差异**：
- `knowledge-sdk`：`kb://org/<org_id>/doc/<doc_id>@<version>[#anchor=<id>|#chunk=<id>]`，配套 `EvidenceAnchor`、三阶段确定性重锚、`excerpt_hash`、`MaterialReceipt` 与不可变 `EvidencePack`（RO-Crate 1.2）。
- `openbot-vp`：`ku://kb/<kbId>/doc/<docId>@<versionId>[#<section>]`，缺少原文哈希校验与重锚。

**统一对齐方案（推荐）**：
1. **SDK 为权威证据链来源**：所有从 SDK 检索或消费的证据均返回标准 `EvidenceRecord`，同时携带结构化坐标（`tenant_id`、`kb_id`、`doc_id`、`version`、`version_id`、`chunk_id`、`anchor_id`、`section_path`、`excerpt`、`excerpt_hash`、`canonical_uri`）。
2. **URI 双轨兼容策略（无损过渡）**：
   - SDK 内部规范 URI 维持 `kb://org/<org_id>/doc/<doc_id>@<version>[#anchor=<id>|#chunk=<id>]`（严禁破坏 `contracts/uri.py` 既有规范编码测试）。
   - OpenBot Adapter 在边界提供确定性双向映射函数：
     - `SDK -> OpenBot UI`：优先保留 `canonical_uri`（`kb://...`）作为权威引用，同时在过渡期提供兼容字段 `legacy_ku_uri = ku://kb/<kb_id>/doc/<doc_id>@<version_id>[#<section>]` 供存量前端组件平滑渲染。
     - `OpenBot 历史引用 -> SDK`：Adapter 解析存量 `ku://kb/<kbId>/doc/<docId>@<versionId>` 并查询 SDK 文档/版本映射表，无缝验证并升级为 `kb://` 引用。

### 2.6 混合检索、重排与分数语义模型（Retrieval）· 状态：待评审

**当前差异**：
- `knowledge-sdk`：采用 RRF（`w / (60 + rank)`）融合全文与向量，并由 Q3-M2 引入可插拔 `Reranker` 与通道独立 `ScoreCalibrator`（输出 `[0, 1]` 的 `calibrated_score` 与低置信拒答 `min_calibrated_score`）。
- `openbot-vp`：采用 `0.7 * (1 - dist) + 0.3 * bm25` 并乘以治理加权因子，最终由 `RetrievalService` 跨 `knowledge`/`artifact`/`memory` 按分数降序联邦合并。

**统一对齐方案（推荐）**：
1. **分数语义严格解耦（禁止混用未校准原始分）**：
   - `raw_score`：底层召回通道原始融合分（如 RRF 分或余弦分，仅用于诊断）。
   - `rerank_score`：重排器原始输出分（如确定性词法重排或外部 Cross-Encoder 分数）。
   - `calibrated_score`：经通道独立校准器映射到 `[0.0, 1.0]` 的可比置信分，**作为 OpenBot 联邦检索合并与低置信拒答的唯一标准分**。
2. **治理信号扩展位（面向未来平滑承接 OpenBot 治理加权）**：
   - 保持 `DefaultPolicyEngine` 权限过滤与 `archived/suppressed` 硬拦截在排序**之前**执行（防止未授权或被抑制内容进入候选集产生分数侧信道泄漏）。
   - 在 `SearchHit` 扩展可选只读字段 `governance_state`（`published`/`in_review`/`disputed`）与 `score_breakdown`（记录 `keyword_rank`、`vector_rank`、`rerank_score`、`calibrated_score`、`freshness_hint`），使 OpenBot 既透明可控又无需在外部重写排序核心。

### 2.7 摄取与异步作业模型（Ingestion）· 状态：待评审

**当前差异**：
- `knowledge-sdk` 当前 `ingest()` 为同步调用，直接完成解析、切块、锚点生成与可选向量入库。
- `openbot-vp` 具备 `knowledge_vectorize_queue` 异步队列，支撑大文件上传、文件夹批量上传与 Web 刷新时的非阻塞体验。

**统一对齐方案（推荐）**：
- **双模式并存**：
  1. 保留现有同步 `ingest()`，适用于中小文档、测试与强一致即时写入场景。
  2. 新增标准异步作业契约 `IngestionJob`（状态机：`queued -> parsing -> chunking -> indexing -> completed | failed | cancelled`），支持 `idempotency_key` 幂等提交、进度查询、失败错误码与安全重试，底层依托 SDK 既有事务性 `OutboxEvent` / `pending_indexes` 推进，保持零强制外部 MQ 依赖（同时允许生产环境挂载外部 Worker）。

### 2.8 连接器与外部数据源模型（Connector）· 状态：待评审

**当前差异**：
- `knowledge-sdk` 已具备 `BaseConnector`、`ConnectorSyncRunner`、`ConnectorCursor`、`TombstoneRecord`、`ControlledFilesystemConnector`、`WebhookSyncConnector`。
- `openbot-vp` 具备 `knowledge.connector.*`（`providers/bind/unbind/status/sync.plan/sync.commit`）与 `local-folder.*`、`web.setRefreshPolicy`。

**统一对齐方案（推荐）**：
- **Plan / Commit 两阶段同步协议对齐**：在 SDK 既有 `ConnectorSyncRunner` 之上补齐标准化的 `plan_sync`（预演变更集：新增/更新/撤权 Tombstone 清单）与 `commit_sync`（提交并持久化 `ConnectorCursor`），天然承接 OpenBot 的 `sync.plan` / `sync.commit` 交互模式。
- **执行位置分层**：企业级服务端连接器（Wiki/Drive/对象存储/Webhook/研发文献库）运行于 SDK Connector Worker；用户本机桌面文件夹同步（`local-folder.*`）由 OpenBot 边缘客户端负责本地文件扫描与变更检测，通过标准 Connector Push/Sync API 将增量与 Tombstone 推送给 SDK。

---

## 三、面向未来垂类扩展的预留架构（创新药研发 / Ontology / 知识图谱）

在对齐 OpenBot 的同时，SDK 必须保持“通用知识底座 + 垂类扩展槽位”的演进空间，避免为当前产品写死模型：

1. **Asset Extension Envelope**：`Document.domain_metadata` 支持挂载版本化扩展 Schema（如 `schema_ref: "pharma.assay.v1"`），由可选验证插件校验，SDK 核心表无需为单一行业频繁改表。
2. **Claim 与 EvidenceGraph 衔接（Schema v6 规划）**：保持正交关系表设计（`claims` / `evidence_edges` 全部挂接 `org_id` + `doc_id` + `version` + `anchor_id` 与 PostgreSQL RLS），确保图谱遍历与实体检索严格受控于同一权限引擎，避免度数/边存在性 Oracle 泄漏。
3. **可插拔语义组件**：维持 `Parser`、`Chunker`、`Embedder`、`VectorIndex`、`Reranker`、`OCRHook`、`BaseConnector`、`KnowledgePolicyEngine` 全协议化设计，便于未来接入生物医药文献解析器、化学结构抽取器与专业领域重排模型。

---

## 四、推荐分阶段演进路线（供评审确认）

| 阶段 | 目标范围 | 依赖前提 | 核心产出 |
|---|---|---|---|
| **Phase 2（当前草案评审）** | 联合评审并冻结 8 大领域契约、安全红线（`User ∩ Agent`、稳定 `user_id`）及 HTTP 演进策略 | Team A + Team B + 架构 owner 签认 | 冻结版 `02_DOMAIN_MODEL_ALIGNMENT.md` 与 `03_DOMAIN_CONTRACTS.md` |
| **Phase 3（SDK Layer-1 兼容补齐）** | 补齐空间 CRUD、成员列举/撤销、版本列举/安全回滚、`asset_type`、回收站筛选与双引擎测试 | Phase 2 契约冻结 | 新增方法 100% 兼容现有 115 条黄金用例并扩展双引擎契约测试 |
| **Phase 4（跨语言 HTTP 契约与异步摄取）** | 落地语言无关 JSON HTTP 契约（标准错误码 + `request_id` + `idempotency_key`）、`IngestionJob` 与轻量化 TypeScript Client | Phase 3 完成 | OpenAPI 3.1 规范、契约一致性测试套件、TypeScript SDK |
| **Phase 5（OpenBot Adapter 影子灰度与切换）** | OpenBot 引入 `KnowledgeSdkAdapter`（反腐败层实现 `kb:// <-> ku://`、租户规范化、成员 `user_id` 迁移），先双写影子比对，再按租户灰度切流 | Phase 4 + 专项迁移审批与回滚预案 | 灰度对比报告、权限零越权验收、`FINAL_ALIGNMENT_REPORT.md` |
