# OpenBot 知识业务需求逆向映射与差距分析（Phase 1）

> 文档路径：`docs/architecture/knowledge-sdk-alignment/01_OPENBOT_REQUIREMENTS_MAPPING.md`
> 对照基线：`openbot-vp@main (58287aa4)` vs `knowledge-sdk@feat/q3-phase2-rerank-eval (d153295)`
> 审计原则：严格按“SDK 负责通用知识核心、OpenBot 保留产品/Agent/组织/工作流/UI”的架构边界划分承接与归属，不把 OpenBot 私有业务写入 SDK

---

## 一、OpenBot 现有知识体系全貌逆向梳理

通过对 `openbot-vp` 源码实查，其当前“Knowledge Universe”完全内嵌在 TypeScript/Node.js Gateway 中（`src/gateway/knowledge/` 含 211 个非测试 TS 文件、`src/retrieval/` 为检索编排层、`ui/src/ui/views/knowledge-universe-*.ts` 含 95 个前端文件），**当前对 `knowledge-sdk`、`kb://`、`pgvector`、`qdrant` 均为零引用**。

### 1.1 Gateway RPC 接口版图（共 90 个方法）

| 入口文件 | RPC 数量 | 覆盖业务域 | 架构归属判定 |
|---|---|---|---|
| `src/gateway/server-methods/knowledge.ts` | 77 | 空间 CRUD、成员邀请、文档上传/预览/保存/版本/回收站、Web 采集刷新、Dataset 导入、本地文件夹同步、检索/引用/认知包、交付物归档、访问申请、最近访问/推荐/时间线/Feed | **核心拆分点**：空间/文档/版本/检索/证据/连接器同步下沉 SDK；最近访问/推荐/Feed/交付物工作流/访问申请审批单留在 OpenBot |
| `src/gateway/server-methods/knowledge-governance.ts` | 7 | 治理总览、治理任务列表与图谱、Claims 列表、专家权威度读写 | **中期对齐点**：审核/状态机/纠偏接入 SDK L2 与后续 Schema v6 EvidenceGraph；专家画像/任务运营 UI 留在 OpenBot |
| `src/gateway/server-methods/knowledge-connector.ts` | 6 | 连接器提供方列表、绑定/解绑、状态、Sync Plan/Commit | **直接对齐点**：对接 SDK `BaseConnector` + `ConnectorSyncRunner` + Tombstone 撤权 |

### 1.2 OpenBot 四大核心业务链路深潜

#### 1. 知识库与文档生命周期链路

- **存储现状**：空间元数据存储在本地 JSON 文件 `bases.json`（`knowledge-base-store.ts`），成员存储在 `base-members.json`（`knowledge-base-members.ts`），索引与分块存储在 `node:sqlite` + FTS5 + `sqlite-vec (vec0)`（`kb-index-schema.ts`，含 `documents`、`document_versions`、`chunks`、`chunk_meta`、`chunks_vec`、`chunks_fts`、`knowledge_lineage`、`web_source_snapshots`、`dataset_schemas`、`knowledge_vectorize_queue`、`chunk_governance`、`claims` 等 20+ 张表）。
- **核心动作**：支持空间创建/列表/详情/修改/删除；文档上传/文件夹上传/保存编辑/版本历史/版本对比；文档与空间挂载（`attach`）、移入回收站（`detach` -> `recycledDocumentIds`）、恢复（`restore`）、永久删除（`delete`）；异步向量化队列（`knowledge_vectorize_queue`）。
- **核心问题**：JSON 文件 + 本地 SQLite 无法横向扩展，缺少数据库级租户隔离（无 RLS），且元信息与索引跨文件更新缺乏强事务一致性。

#### 2. 组织、租户、用户与成员身份链路

- **租户规范化**：`src/gateway/tenant-canonicalization.ts` 硬编码了历史租户别名映射（`upbeyond-91aeea3c -> 001`），且个人空间允许 `tenantId = null` 仅凭 `ownerId` 归属。
- **成员按邮箱匹配（高危缺陷）**：`knowledge-base-members.ts` 的 `KnowledgeBaseMemberRecord` 仅保存 `email`（无稳定 `userId`），`knowledge-base-permissions.ts` 中的 `activeMemberRole()` 直接比对 `normalizeEmail(actor.email)`。一旦企业用户改邮箱、跨 IdP 登录或邮箱复用，将导致权限丢失或越权。
- **权限层级单一**：`src/retrieval/types.ts` 注释明确写道 *“Only knowledge-base-level scoping is enforced in the current phase; finer scopes are schema-reserved”*，OpenBot 尚未真正落地文档级 ACL、显式 Deny、密级（Clearance）和脱敏策略。

#### 3. Agent 调用与授权链路（最高优先级安全冲突）

- **工具调用入口**：`src/agents/tools/knowledge-consume-tool.ts` 与 `knowledge-consume-scope.ts` 接收 `KnowledgeConsumeRef`（`knowledge-base` / `knowledge-file` / `deliverable` / `folder`），提取 `kbIds` 和 `docIds` 构造检索范围，并经 `resolve/source-selector.ts` 在 `personal`/`enterprise`/`data` 三类源之间做策略路由。
- **越权漏洞（`canReadViaRobotBinding`）**：在 `src/gateway/knowledge/knowledge-base-permissions.ts` 中：
  - `canReadKnowledgeBase` 的判断顺序为：`owner` -> `canReadViaRobotBinding` -> `activeMemberRole` -> `visibility`。
  - 只要 `knowledgeBase.robotIds.includes(actor.agentId)` 且调用方与知识库处于同一租户，**即便当前人类用户既非 Owner 也非成员、且库为 `private`，也会直接放行读取！**
  - 这与 Knowledge SDK 的核心安全宪法（**Agent 绝不能放大人类用户的权限，必须满足 `Effective = User ∩ Agent`**）直接冲突。OpenBot 现有的 `robotIds` 绑定只能作为“Agent 可见范围白名单（上限收缩）”，绝不能作为绕过用户 ACL 的“提权旁路”。

#### 4. 混合检索、治理加权与 Citation 证据链路

- **联邦检索编排**：`src/retrieval/retrieval-service.ts` 将 `knowledge`、`artifact`（交付物）、`memory`、`web`、`database` 抽象为 `RetrievalSource`，并行检索后按 `score` 降序合并。
- **知识库内部打分**：`src/gateway/knowledge/kb-retrieve.ts` 执行 FTS5 BM25（`bm25RankToScore`）与 `vec0` 向量距离（`1 - dist`），默认以 `vectorWeight = 0.7`、`textWeight = 0.3` 合并，随后调用 `governance/retrieval-scoring.ts` 的 `applyGovernanceMultiplier` 乘以 `trustScore[0.5..1.2] * freshnessScore[0.5..1.0] * verifiedWeight(confirmed=1.1, conflict=0.7, suppressed/archived=0)` 及 `claimConflict` 惩罚。
- **引用协议**：`src/gateway/knowledge/ke/cite.ts` 定义 `ku://kb/<kbId>/doc/<docId>@<versionId>[#<section>]`，与 SDK 的 `kb://org/<org_id>/doc/<doc_id>@<version>[#anchor=<id>|#chunk=<id>]` 不兼容，且缺少 `excerpt_hash` 篡改校验与确定性重锚。

---

## 二、OpenBot 到 Knowledge SDK 完整业务映射与差距矩阵

> 优先级定义：**P0**（阻塞统一底座对接或存在安全/数据模型冲突，必须先冻结契约并落地）、**P1**（承接 OpenBot 核心产品闭环所必需的兼容扩展）、**P2**（中期演进或领域增强）、**Stay-in-OpenBot**（属产品/UI/工作流层，不进入 SDK）。

| OpenBot 业务能力 | OpenBot 当前实现 | SDK 当前实现 | 差距 | 调整要求 | 优先级 |
|---|---|---|---|---|---|
| 知识空间创建与列表 | `knowledge.base.create` / `list` / `get`（`bases.json`，含 `title`/`description`/`visibility`/`robotIds`/`tags`） | `create_kb` / `list_kbs`（`knowledge_bases`，含 `name`/`visibility`/`space_type`/`governance_tier`） | SDK 缺少 `get_kb`、`description`、`tags` 空间元数据及分页过滤 | SDK 兼容扩展 `get_kb` 与空间可选 `description`/`metadata`（不写入 OpenBot 专属 `robotIds`，由 `AgentProfile.allowed_kb_ids` 承接） | P0 |
| 知识空间更新与删除 | `knowledge.base.update` / `knowledge.base.delete`（修改标题、描述、可见性、标签；删除空/非空库） | **完全缺失** | SDK 无法修改空间元信息或软删/归档空间 | SDK 新增 `update_kb`、`archive_kb`（软删优先，严禁默认物理级联清空历史资产）并记录审计事件 | P0 |
| 知识空间成员管理 | `knowledge.base.members.list` / `invite`（`base-members.json`，以 `email` 匹配，`pending`/`active` 状态） | `grant_kb_member(kb_id, user_id, role)`（仅写接口，按稳定 `user_id`） | 1. 身份键冲突（email vs user_id）；2. SDK 缺少成员列表与撤销接口；3. 邀请工作流属产品层 | SDK 新增 `list_kb_members`、`revoke_kb_member`；强制统一以稳定 `user_id`（`issuer + sub`）授权；OpenBot 的邮箱邀请态留在产品层，接受邀请后解析出稳定 `user_id` 再写入 SDK | P0 |
| 租户与组织隔离 | `tenantId`（可为 `null`）+ `tenant-canonicalization.ts` 别名映射 | 强必填 `org_id` + PG `FORCE RLS`（`app.current_org_id`） | 缺少 `tenant_id` 与 `org_id` 语义对齐；OpenBot 个人库 `tenantId=null` 无直接映射 | Phase 2 冻结统一多租户模型：要求所有请求具备规范化 `tenant_id`（个人用户归属默认个人租户或明确租户 ID），OpenBot Gateway 负责在边界完成历史别名规范化，SDK 不硬编码任何租户别名 | P0 |
| 身份认证与主体传递 | Gateway 会话解析 `userId`/`email`/`tenantId`/`departmentId`/`roleCode`/`agentId` | HMAC 签名头（`X-KB-Actor`/`X-KB-Agent`/`X-KB-Purpose`）+ OIDC JWT + SCIM `IdentityPrincipal` | SDK `Actor` 缺少 `issuer`、`actor_type` 显式字段；尚无 OpenBot Gateway 服务间可信凭证规范 | Phase 2 冻结统一 Identity 契约（`issuer` + `subject_id` + `tenant_id` + `actor_type` + `policy_generation`）；OpenBot Gateway 作为受信任调用方通过 OIDC/签名网关透传用户与 Agent 双重身份 | P0 |
| Agent 授权与空间绑定 | `knowledgeBase.robotIds` + `canReadViaRobotBinding()`（同租户即放行，绕过用户成员校验） | `AgentProfile` + `DefaultPolicyEngine` 强制 `User ∩ Agent` 权限交集与预算约束 | **严重安全语义冲突**：OpenBot 将 Agent 绑定当作授权放行，SDK 将其视为权限上限收缩 | 冻结“最小权限交集铁律”：任何 Agent 代调用必须同时通过用户 ACL 与 `AgentProfile` 边界；OpenBot `robotIds` 迁移映射为 SDK `AgentProfile.allowed_kb_ids`；若存在“服务机器人代查公域库”需求，须显式声明 `actor_type=service` 与独立服务主体授权，禁止借用无权用户绕过 | P0 |
| 文档摄取与多格式解析 | `knowledge.personal.upload` / `uploadFolder` / `document.save`（PDF/MD/Text，同步入库 + 异步 `knowledge_vectorize_queue`） | `ingest()`（同步解析 TXT/MD/CSV/HTML/Office/PDF + 分块 + 锚点 + 可选即时向量化） | SDK 缺少异步摄取作业契约（`IngestionJob` 状态/进度/失败重试/取消）与大文件流式/对象存储直传语义 | SDK 新增可选异步 `IngestionJob` 协议（保留现有同步 `ingest()` 兼容），补齐状态查询与重试幂等键（`idempotency_key`） | P1 |
| 文档版本管理与对比 | `knowledge.personal.versions` / `compareVersions`（`version_id` 字符串 + `version_label`） | `DocumentVersion`（整数 `version: int`、`raw_hash`、`semantic_hash`、`get_document(version)`） | SDK 缺少 `list_document_versions` 与版本差异对比/回滚发布能力；版本 ID 类型不一致 | SDK 保留 `version_no: int` 作为单调主序，扩展稳定 `version_id`（ULID/UUID）与可选 `version_label`，新增 `list_document_versions` 与受审计的“基于历史版本生成新版本（安全回滚）” | P0 |
| 文档移除、回收站与永久删除 | `knowledge.base.documents.detach`（进 `recycledDocumentIds`）/ `restore` / `delete` / `recycle.list` | `archive(doc_id)` / `restore(doc_id)`（布尔 `archived`，默认检索隐藏） | 1. SDK 无多空间挂载/解绑（文档单归属 `kb_id`）；2. SDK 缺少“回收站列表”显式过滤与受控物理删除（含向量/Blob/Tombstone 清理） | Phase 2 明确文档归属模型（单主空间 + 可选跨空间引用，或显式回收站状态）；SDK 扩展 `list_documents(archived_only=True)` 与受审计/需审批的 `purge_document`（触发 Tombstone 与索引清理） | P1 |
| 文档级细粒度 ACL 与脱敏 | `RetrievalContext.accessibleScopes` 仅预留未实现；无文档级 Deny 与脱敏 | 完整 8 步策略引擎、文档显式 Deny、密级 Clearance、四权分离、Fail-Closed `RedactionRegistry` | OpenBot 缺失、SDK 领先 | 直接复用 SDK 权威策略引擎；OpenBot Gateway 与 UI 逐步暴露文档级 ACL 配置，不再在 OpenBot 侧重造策略引擎 | P1 |
| 混合检索、重排与分数语义 | `kb-retrieve.ts`（`0.7*vec + 0.3*bm25` 乘以治理因子）+ `RetrievalService` 多源联邦 | `hybrid.py`（RRF `w/(60+r)` + `Reranker` + `ScoreCalibrator` `[0,1]` + `min_calibrated_score` 拒答） | 1. 分数尺度不可跨源直接比较（OpenBot 联邦需要统一 `[0,1]` 语义）；2. SDK 尚无治理质量因子（freshness/trust/conflict）挂钩位 | Phase 2 冻结统一检索返回模型：强制分离 `raw_score`、`rerank_score`、`calibrated_score`（归一化 `[0,1]`，供 OpenBot 联邦融合）与 `scoring_breakdown`；后续通过可扩展的 `RankingPolicy` 接入可信度/时效性信号 | P0 |
| 证据链、锚点与 Citation URI | `ku://kb/<kbId>/doc/<docId>@<versionId>#<section>`（无原文哈希校验、无重锚） | `kb://org/<org_id>/doc/<doc_id>@<version>#anchor=<id>` + `EvidenceAnchor` + `MaterialReceipt` | URI 协议不兼容；OpenBot 现有前端与历史对话已存在 `ku://` 与 `obj:doc:` 引用 | Phase 2 冻结“双轨兼容 URI 契约”：SDK 内部坚持规范 `kb://`（并扩展可携带 `tenant_id`/`kb_id` 或通过 `EvidenceObject` 携带完整坐标），在 Adapter 层提供无损 `kb:// <-> ku://` 双向映射，过渡期禁止破坏存量 `ku://` 链接解析 | P0 |
| Agent 任务上下文与中途撤权 | `knowledge.runtime.context` / `knowledge.agent-profile` / `knowledge.resolve`（静态上下文组装，无运行期撤权） | Q3-M1 `AgentProfile`、`TaskContext`、`ContextSnapshot`、`MidTaskRevocation` | OpenBot 尚未对接 SDK Runtime 快照与中途撤权 | 通过 Adapter 将 OpenBot Agent 运行会话对接 SDK `TaskContext` 与 `ContextSnapshot`，实现运行期权限回收与内容失效感知 | P1 |
| Web 快照、Dataset 与文件夹连接器 | `collectWeb` / `web.setRefreshPolicy` / `importDataset` / `local-folder.*` / `knowledge.connector.*` | `BaseConnector`、`ConnectorSyncRunner`、`ControlledFilesystemConnector`、`WebhookSyncConnector`、`TombstoneRecord` | SDK 缺少 `asset_type` 分类（web_page/dataset/file/generated）及 Web 刷新调度元数据；本地文件夹扫描位于用户终端（OpenBot 侧） | SDK 扩展通用 `asset_type` 与 `source_metadata`（`source_url`、`etag`、`schema_summary`），提供标准 Connector Sync Plan/Commit/Tombstone 契约；用户桌面本地文件扫描与爬虫抓取执行留在外部 Connector/OpenBot 边缘，同步结果推送至 SDK | P1 |
| 治理审核、纠偏与 Claims | `knowledge.governance.*`（`chunk_governance`、`governance_tasks`、`claims`、`claim_relations`） | L2 三分离审批状态机、`EvidenceIssue` 流内纠偏、`EvidencePack`（RO-Crate）；`EvidenceGraph`/Claims 尚在 Q3-M3 规划 | OpenBot 已有局部 SQLite `claims` 表但缺乏不可变审计与权限防泄漏；SDK L2 已成型但无图谱/Claim 表 | 短期先用 SDK L2 审批与 `EvidenceIssue` 承接纠偏闭环；中期按 Schema v6 统一落地权限隔离的 `Claim`/`EvidenceGraph` 契约，替代 OpenBot 私有 `claims` 表 | P2 |
| HTTP API 契约与多语言客户端 | OpenBot Gateway 为 TypeScript/Node.js，当前直连本地 TS 模块 | HTTP `/v1/*` 采用 `{"params": ...}` + `__type__` 标记；仅有 Python `HttpKnowledgeClient` | 跨语言调用成本高；错误码粒度不足；无 TypeScript Client SDK | Phase 2 冻结语言无关的 HTTP API 契约（标准 JSON Schema + 稳定错误码 + `request_id` + 幂等键，保持 `/v1/*` 兼容或演进 `/v2/*`）；后续提供官方轻量化 TypeScript SDK 供 OpenBot Adapter 调用 | P0 |
| MCP 外部工具接入 | OpenBot 自身具备工具体系（`knowledge-consume-tool.ts`） | `knowledge-sdk-mcp`（4 个标准工具：`search_evidence`、`verify_citation`、`get_evidence_pack`、`report_evidence_issue`） | 能力互补、无冲突 | 保留 SDK MCP 能力供外部 IDE/第三方 Agent 接入；OpenBot 主链路优先通过低延迟 HTTP/TS Adapter 调用 SDK | P2 |
| 交付物、推荐、最近访问、Feed 与 UI 工作台 | `deliverables.*`、`recent.*`、`recommendations`、`feed.*`、`timeline.*`、`access.request`、95 个 UI 文件 | 不包含（符合架构定位） | **非 SDK 差距，属正确边界分离** | 明确保留在 OpenBot 侧；交付物归档入库时通过 SDK `ingest` API 写入（`asset_type=deliverable`），访问申请审批通过后调用 SDK 成员/ACL API 生效 | Stay-in-OpenBot |

---

## 三、关键跨仓边界与风险汇总

### 3.1 必须坚守的架构边界（反腐败层原则）

1. **禁止将 OpenBot 私有概念渗入 SDK**：SDK 中不得出现 `robotIds` 绕权逻辑、`upbeyond-91aeea3c` 租户别名、`bases.json` 格式、`ku://workspace/...` 工作区交付物路由、前端 Feed/推荐算法或邮件发送服务。
2. **禁止在 OpenBot 侧保留第二套知识权限真相源**：过渡期双写/灰度完成后，文档内容、索引、ACL、版本与审计账本的唯一权威来源（Single Source of Truth）必须是 Knowledge SDK。
3. **OpenBot `RetrievalService` 的定位**：继续作为 OpenBot 产品层的联邦编排器，将 `Knowledge SDK` 作为标准 `knowledge` 检索源挂载，与 `memory`、`artifact` 等非知识库源在产品层合并展示。

### 3.2 进入 Phase 2 前必须联合决策的 5 项阻断问题

1. **安全红线**：OpenBot 是否确认废除 `canReadViaRobotBinding` 的“绕过用户 ACL 读私密库”行为，改为严格的 `User ∩ Agent` 交集，并为合法的“公共机器人”引入显式 `service` 主体或公共空间授权？
2. **身份主键**：OpenBot 是否确认将 `base-members` 从 `email` 键平滑迁移至稳定 `user_id`（`issuer + sub`），邮箱仅保留为邀请展示属性？
3. **租户规范化**：OpenBot 个人空间（`tenantId = null`）在调用 SDK 时统一映射为何种 `tenant_id` 策略（例如 `personal:<user_id>` 独立个人租户，或归属用户所属主租户下的 `space_type=personal` 空间）？
4. **版本标识**：SDK 是否采用“整数递增 `version_no` + 稳定不透明 `version_id`”双字段方案以同时兼容 SDK 历史 `kb://...@<int>` 与 OpenBot 字符串 `version_id`？
5. **HTTP 契约形态**：新增面向 OpenBot 的跨语言标准 JSON API 是采用 `/v1/*` 兼容扩展（新增 `X-KB-Contract: json-v2` 或新 REST 端点）还是引入并行 `/v2/*` 前缀（保持 `/v1/*` Python `__type__` 客户端 100% 不断裂）？

以上 5 项问题已在 Phase 2 草案文档（`02_DOMAIN_MODEL_ALIGNMENT.md` 与 `03_DOMAIN_CONTRACTS.md`）中给出推荐设计方案，全部标注为 **`待评审`**，待 Team A、Team B 与架构 owner 联合签认后冻结。
