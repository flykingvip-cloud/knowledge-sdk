# Enterprise AI Master Architecture v2.1 双团队并行落地执行指令（Wave-V21-0）

> **指令状态**：`WAVE_V21_0_DISPATCHED_NON_DESTRUCTIVE`（基于《Master Architecture v2.1 — OpenBot 既有能力清单与 Knowledge SDK 边界规范》与《Space Pre-v7 B2-2/B2-3 复审结论》联合下发）  
> **适用团队**：团队 A（`flykingvip-cloud/knowledge-sdk` 执行代理）× 团队 B（`flykingvip-cloud/openbot-vp` 执行代理）  
> **双轨推进策略**：**Track 1（Space Pre-v7 既定收口线，不可中断）** 与 **Track 2（Master Architecture v2.1 复用基线与契约冻结波次）** 并行推进，严守先审计穿透、先冻结跨系统契约、严禁重复建设与严禁未授权 DDL/切流红线。  
> **锚定代码基线**：  
> - 团队 A 锚点：`knowledge-sdk@main`（`b953c9922cc1096e0e88455dab6746c01a9d27f9`）、冻结 Wave2 联调基线 `feat/align-wave2-m2-min-slice@9940818b962ccb186c0dfb0158de6bd9bd49057b`（Schema v6 + `/v2/spaces`）、Pre-v7 设计原型 `feat/space-alignment-v1-design-proto@4bed2a1c86153035314815165f29d26a078fab50`  
> - 团队 B 锚点：`openbot-vp@main`（`58287aa449fb499f49080c467df76b774b458222`）、Space M2-B 隔离适配分支 `codex/openbot/knowledge-sdk-v2-min-slice-adapter@f0fccbd37bb9a45545562ee668295f9153b6f6aa`（Gate 7 `MET`、Gate 3/4 `NOT_MET`）  
> **硬性冻结红线**：`schema_v7_ddl_authorized: false` · `schema_v8_v9_ddl_authorized: false` · `final_alignment_frozen: false` · `prod_shadow_migration_cutover_authorized: false` · `semantic_object_dual_write_prohibited: true` · `duplicate_runtime_or_connector_build_prohibited: true`。

---

## 一、Wave-V21-0 总授权边界与双轨分工总览

本波次为 **v2.1 新架构落地的第 0 号并行执行波次（非破坏性契约冻结、代码穿透审计与沙箱原型波次）**。在 Owner 书面签认 v2.1 基线与 Space Pre-v7 退出门槛全绿之前，双方必须严格遵守以下 **8 项允许** 与 **10 项严格禁止** 边界：

| 分类 | 具体执行边界条款 |
|---|---|
| **本波次允许执行（8 项）** | 1. 团队 B 在隔离分支继续推进 Track 1 Space Pre-v7 收口（穿透 30 项 `partial`、补齐 `PRE-02` 处置建议单、待命响应 `EXT-02`）；<br>2. 双团队按 10 项标准化字段完成 Stream A–E 代码级穿透闭环（B/C 必须穿透至持久化与最终执行）；<br>3. 冻结 5 组跨系统契约（Model/Embedding、Controlled Data Bridge、CogniWeave Memory/Revocation、Unified Trace、v3 扩展接口草案）及黄金向量；<br>4. 团队 A 在隔离分支实现纯协议模型、零生产 DDL 的沙箱级原型与自动化边界守门脚本；<br>5. 团队 B 在隔离分支实现默认关闭的只读 `SemanticObject` 导出适配器与契约类型守卫单测；<br>6. 团队 A/B 开展跨语言契约 SHA-256 双向复算与差异登记（`V21-DELTA-*`）；<br>7. 保持既有 `9940818b`（Schema v6 + `/v2/spaces`）与 `f0fccbd3`（Gate 7 `MET`）全量回归零退化；<br>8. 输出标准 Handoff 报告供独立验收团队复核并呈报 Owner 签认解锁 Wave-V21-1。 |
| **本波次严格禁止（10 项）** | 1. 严禁任何 Schema v7 / v8 / v9 不可逆 DDL 合入生产迁移序列或主分支；<br>2. 严禁修改 `9940818b` `/v2/spaces` 兼容语义或覆盖 M1 冻结的 28 项契约资产（`verify_frozen.py` 必须 100% 零漂移）；<br>3. 严禁在 `knowledge-sdk` 中新建 12 项红灯重复能力（Agent Runtime、Model Provider/Vault/Fallback、Tool/MCP/Workflow、DB/ERP/CRM 连接器、Connector Vault、Data Capability 执行引擎、Agent 记忆蒸馏、Bandit 选模引擎）；<br>4. 严禁向 `knowledge-sdk` `pyproject.toml` 核心 `dependencies = []` 引入强制第三方依赖；<br>5. 严禁对 `openbot-enterprise-semantic-objects.json` 形成双写或擅自迁移 Semantic Object 写主；<br>6. 严禁在未获安全审批前解除 `data-capability-tool.ts` 的 `knowledge-object-only` Fail-Closed 保护或开放自由 Text-to-SQL；<br>7. 严禁将 `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` 默认值改为 `true` 或切入 OpenBot 生产默认路由；<br>8. 严禁执行任何历史数据迁移、生产影子流量或生产切流；<br>9. 严禁把 16 份未归属架构草稿混入 `openbot-vp` 工作分支或向 `main` 发起未授权 PR；<br>10. 严禁将 `T-01`–`T-27` 宣称为已通过正式验收或提前签发 `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md`。 |

---

## 二、团队 A（Knowledge SDK）Wave-V21-0 执行任务指令（VA-1 至 VA-5）

**仓库与分支纪律**：严格保护 `main@b953c992`、`07f5d39f`、`9940818b`、`4bed2a1c` 及 `migrations/`（Schema v6）零改动。基于 `9940818b` 切出独立隔离分支 **`feat/v21-wave0-contracts-and-adapters`** 执行以下五项任务：

### VA-1｜跨系统唯一契约包与黄金测试向量（contracts/v21-reuse-v1）

在独立目录 `contracts/v21-reuse-v1/` 下（严禁触碰 M1 冻结目录）交付以下 **5 组可机读 JSON Schema + OpenAPI v3 片段 + Python/TypeScript DTO 草案 + 脱敏黄金向量**：

1. **Model & Embedding/Reranker Adapter 契约（`model-adapter.schema.json`）**：
   - 定义 `LLMInvokeRequest/Response`（复用 OpenBot 公开执行与 Fallback 接口）以及 `EmbedRequest/Response`、`RerankRequest/Response` 双轨适配协议（同时支持“调用 OpenBot 后续公开的 `models.embed` / `models.rerank` 代理”与“宿主注入外部 Provider”），严禁 SDK 内置硬编码模型凭证或隐式付费调用。
2. **受控企业数据桥接契约（`controlled-data-bridge.schema.json`）**：
   - 固化 **Mode A（用户委派透传）/ Mode B（租户受控服务凭证 + 强制行级谓词）/ Mode C（离线受控物化快照）** 鉴权声明（未匹配一律 Fail-Closed，`M-03`）；明确禁止 MVP 自由 Text-to-SQL；强制携带 `policy_generation`、`masking_receipt`、`freshness_ts` 与 `tombstone` 语义。
3. **CogniWeave 记忆资源注册与撤权回执契约（`memory-resource-bridge.schema.json`）**：
   - 定义 `resource_type = "agent_memory"` 的只读发现元数据格式，以及第 4 通道撤权失效通知与不可篡改回执 **`RevocationPurgeReceipt`** 结构（`M-05`）。
4. **全链路统一追踪信封契约（`ai-execution-trace.schema.json`）**：
   - 锁定贯穿 OpenBot × Knowledge SDK × AOR × CogniWeave 的唯一关联头：`tenant_id`、`user_id`、`agent_id`、`trace_id`、`run_id`、`plan_id`、`policy_generation`、`cost_attribution`。
5. **vNext 扩展接口草案（`openapi-v3-draft.yaml`）**：
   - 将 IKC、KSG、Resource Registry、KRDR 与 EDKI 语义桥接接口统一规划在 `/v3/*` 命名空间，强制要求 `Idempotency-Key`、游标分页与脱敏错误码（`M-06`）；明确 Space v7 继续归属 `/v2/spaces` 兼容演进，零冲突。

### VA-2｜核心领域纯协议模型与零 DDL 沙箱原型

在不改动 SQLite/PG 生产迁移表（Schema 仍锁定 `v6`）的前提下，于独立沙箱/原型模块落地四项纯标准库实现：
- **`Resource` 与 `Capability` 严格分离原型**：实现 `KnowledgeResource`、`DataCapabilityRef` 与 `ResourceCapabilityBinding` 数据结构及校验器，彻底禁止二者混为单一对象；
- **IKC 异步知识生产状态机原型**：复用 `9940818b` 既有 `ingestion_jobs` / `idempotency_records` / `outbox_events` 语义，定义 `IntakeJob`、`KnowledgeProductionJob`、`PipelineVersion` 与 `active_published_production_id` 蓝绿切换状态机，硬编码高风险/强合规文档 `whole_document_atomic_publication = true`（严禁审批前暴露 `partial_available`，`M-05`）；
- **KSG-Lite（Phase 0 零 DDL）规则插件**：构建挂载于既有 `governance/workflow.py` 与 `governance/issues.py` 之上的标准校验接口原型，不新增生产表；
- **只读 `SemanticReference` 绑定原型**：定义指向 OpenBot `semantic_object_key` 的只读引用与上层业务概念/制度条款映射结构，代码中显式禁止写入物理连接器字段或凭据。

### VA-3｜四通道撤权编排与双视图防侧信道验证套件（沙箱级）

- 编写沙箱自动化测试覆盖 **四通道撤权闭环**（主存储 ACL + 向量/FTS 索引 + 缓存/物化快照 + Agent 历史上下文/CogniWeave 失效回执），验证任一通道未返回成功回执时任务不得标记 `purged`；
- 编写 `KnowledgeRetrievalPlan` **双视图脱敏测试**：证明审计/治理视图记录完整 `resources_excluded` 与精确 `permission_denied`，而 Agent 与终端用户视图仅返回 `redacted_unauthorized_count` 或不透明脱敏码（`M-04`），杜绝无权资源存在性侧信道。

### VA-4｜自动化架构红线守门脚本与全量零退化验证

- 新增 `scripts/verify_v21_boundaries.py` 并接入 CI 独立作业，强制自动校验五项硬红线：
  1. `pyproject.toml` 核心 `dependencies == []`（零新增强制第三方依赖）；
  2. 源码扫描确认零自建禁止模块（无第二套 DB Connector / Model Credential Vault / Agent Session Runtime / Memory Distillation）；
  3. 既有 `verify_frozen.py` 对 M1 28 项冻结资产与 `/v2/spaces` 100% 零漂移；
  4. SQLite / PG 生产迁移版本严格保持 `Schema v6`；
  5. `contracts/v21-reuse-v1/` 全部文件生成确定性 `v21-contract-manifest.json`（含 SHA-256 清单）。

### VA-5｜交付团队 A 标准交接报告

在分支内输出 `V21_WAVE0_TEAM_A_HANDOFF_REPORT.md`，必须包含：分支与 commit SHA、GitHub Actions 并发 CI 全绿运行编号、`verify_frozen.py` 与 `verify_v21_boundaries.py` 原样输出、沙箱测试明细、Stream D/E（SDK 侧）10 字段审计表，以及移交团队 B 复算的 `v21-contract-manifest.json` 哈希清单。

---

## 三、团队 B（OpenBot）Wave-V21-0 执行任务指令（VB-1 至 VB-5）

**仓库与分支纪律**：严守 `main@58287aa4` 不变、零 PR、零 16 份未归属草稿混入、保持 `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED=false` 默认关闭、严禁修改 `knowledge-sdk` 仓库。双分支隔离操作：
- **Track 1（Space Gate 3 收口）**：继续基于 `codex/openbot/knowledge-sdk-v2-min-slice-adapter@f0fccbd3` 递交补充实证；
- **Track 2（v2.1 审计与适配器）**：基于 `f0fccbd3` 切出独立隔离分支 **`codex/openbot/v21-wave0-audit-and-adapters`**。

### VB-1｜Track 1 高优收口：Space Pre-v7 Exit Gate 3（30 项 partial 穿透与 PRE-02 建议单）

1. **6 项 P0 写/调用路径逐行穿透**：完整追踪 `E010`（`knowledge.recent.record`）、`E029`（`knowledge.access.request`）、`E037`（`knowledge.document.summary`）、`E068`（`knowledge.source.invoke`）、`E070`（`knowledge.capability.invoke`）、`E080`（`knowledge.governance.tasks.update`）的下游写助手与执行引擎，列出真实权限门源码行号与潜在缺口，将 6 项升级为 `code-verified`；
2. **共享 Bundle 过滤器穿透专节**：对 `loadKnowledgeSourceBundle`、`loadEnterpriseStoreBundle`、`searchKnowledgeEvidence`、`buildKnowledgeBaseLibraryGraphForKnowledgeBase` 及治理读助手出具 1 份共享穿透报告，覆盖剩余 24 项只读 RPC，推动 30 项 `partial` 归零；
3. **`PRE-02` 处置建议单与 `EXT-02` 待命**：就双读门分裂（`canReadKnowledgeBase` vs `isKnowledgeBaseVisible`）、`private` KB 成员默认加载、旧邮箱成员主键、`local-operator` 生产回退限制及 `OPENBOT_VAULT_SYNC_LEGACY_GATEWAY_SYNC` 生产禁开基线形成书面处置建议单提请安全/产品拍板，并在 DBA 收件人指定后立即发出 `PRE-03` 脱敏聚合统计申请。

### VB-2｜Stream A–D（OpenBot 侧）代码级深度穿透审计终稿（10 项必填字段）

按《v2.1 边界规范》第七节的 **10 项标准化字段**，逐条穿透源码（**严禁只读 README**）并输出 `docs/architecture/v21-audit/` 四份专项实证报告：

| 专项报告 | 必须穿透的核心源码链路 | 本波次必须回答的关键实证问题 |
|---|---|---|
| **Stream A 报告** | `src/agents/models-config.providers*.ts`、`src/agent-runtime/`、`src/memory/embeddings-*.ts`、`src/memory/mmr.ts`、`src/gateway/server-methods/models*.ts`、`tools-catalog.ts` | 1. 冻结可直接复用的 LLM / Runtime / Tool / Workflow 公开接口表；<br>2. 明确基于 `src/memory/embeddings-*.ts` 封装公开受控 `models.embed` 代理的最小改造面、鉴权与计费接入点；<br>3. 确认 Reranker 无内置神经服务，锁定外部注入或代理模式。 |
| **Stream B 报告** | `src/gateway/enterprise-data/connector-*-package.ts`、`mock-handlers.ts`、`indexed-store.ts`、`semantic-object-store.ts`、`data-gateway.ts`、`masking-engine.ts`、`agent-data-planner.ts`、`src/agents/tools/data-capability-tool.ts` | 1. **逐连接器核实真实驱动 vs Demo/Mock**（Postgres、MySQL、HTTP REST、Notion、用友 T+、SAP/Salesforce）；<br>2. 锁定 `openbot-enterprise-semantic-objects.json` 唯一写主与字段契约；<br>3. 保持 `data-capability-tool.ts:99-108` `knowledge-object-only` 不变，列出未来解锁 Mode A/B/C 受控桥接的安全门禁条件。 |
| **Stream C 报告** | `packages/aor-core/src/`、`packages/aor-backend-openbot/src/`、`packages/evolution-core/src/`、`src/conversation-evaluation/`、`src/gateway/server-methods/billing.ts` | 1. 实测或逐行核查 **AOR Stage 4（持久化 Bandit、Python SDK、Graph Backend、Control Plane）** 真实实现完成度与测试覆盖，不轻信历史阶段报告；<br>2. 明确 `VerifiableEvaluator` 与企业级 LLM-as-Judge / 离线数据集平台的真实缺口；<br>3. 设计 `conversation-evaluation`（默认关闭）向跨系统 `AIExecutionTrace` 演进的关联头注入方案。 |
| **Stream D 报告** | `packages/cogniweave-sdk/src/rest/node-server.ts`、`sync/`、`src/gateway/knowledge/`、`src/gateway/server-methods/knowledge*.ts`、`vault-sync.ts` | 1. 核查 CogniWeave `/v1/*` 14 组路由的租户隔离与按资产/主体批量撤权失效能力缺口；<br>2. 将 OpenBot 本地 `knowledge/` 与 `vault-sync` 124 项入口划分为“保留 UI 壳 + 委派 SDK”、“过渡双写禁止项”与“计划退场项”。 |

### VB-3｜默认关闭的 OpenBot 公开复用 Adapter 草案与单元测试

在 `codex/openbot/v21-wave0-audit-and-adapters` 分支落地三组**纯新增、默认关闭、零生产路由改动**的适配层与 Vitest 测试：
- **`SemanticObjectCatalogReadAdapter`**：对 `semantic-object-store.ts` 提供只读脱敏导出接口（返回 `semantic_object_key`、规范字段与脱敏分类，严禁暴露连接凭据，严禁反向写入）；
- **`ControlledDataBridgeGuard`**：按团队 A `VA-1` 契约实现 Mode A/B/C 校验守卫与 Fail-Closed 单测（强制验证未声明 Mode 或无有效 `policy_generation` 时 100% 拒绝，且 `data-capability-tool` `invoke` 仍保持 `knowledge-object-only`）；
- **`AIExecutionTraceHeaderPropagator`**：实现 `trace_id / run_id / plan_id / policy_generation` 在 Gateway、AOR Backend 与 Knowledge Adapter 间的透传与脱敏测试。

### VB-4｜跨语言契约互认复算与差异登记

拉取团队 A `VA-1` 产出的 `contracts/v21-reuse-v1/` 全部文件，独立复算 `v21-contract-manifest.json` 全部 SHA-256，运行 TypeScript 侧 DTO 与脱敏错误码兼容性单测；任何字段分歧统一登记为 `V21-DELTA-01..N` 提请双团队联合裁决，禁止私自修改团队 A 契约文件。

### VB-5｜交付团队 B 标准交接报告

输出 `V21_WAVE0_TEAM_B_HANDOFF_REPORT.md`，必须包含：双分支 SHA、既有 M2-B / B3 / vault-sync（`60 passed / 0 skipped / 0 failed` 等既有套件）零退化回归证明、新增适配层 Vitest 结果、Space Gate 3 30 项 `partial` 归零与 `PRE-02` 报告、Stream A–D 完整实证包，以及 `VA-1` 契约 SHA-256 复算回执。

---

## 四、双团队协同排期与跨系统交接节奏

| 阶段 | 时间窗口 | 团队 A（`knowledge-sdk`）关键里程碑 | 团队 B（`openbot-vp`）关键里程碑 | 联合同步点 |
|---|---|---|---|---|
| **阶段 1：穿透与契约起草** | Day 1–3 | 完成 `VA-1` 5 组跨系统契约包与黄金向量，发布 `v21-contract-manifest.json` 候选版；启动 `VA-2` 沙箱模型 | 优先推进 `VB-1`（6 项 P0 穿透 + 共享 Bundle 过滤器报告）与 `VB-2` Stream A/B 实码穿透 | **Sync-1（Day 3 晚）**：对齐 5 组契约字段，冻结无分歧项，登记 `V21-DELTA-*` |
| **阶段 2：沙箱验证与互认** | Day 4–6 | 完成 `VA-2` / `VA-3` 沙箱原型（四通道撤权 + 双视图脱敏）与 `VA-4` `verify_v21_boundaries.py` CI 接入 | 完成 `VB-2` Stream C/D 穿透报告、`VB-3` 只读/守卫适配层单测与 `VB-4` 跨语言 SHA-256 复算 | **Sync-2（Day 6 晚）**：确认 `V21-DELTA-*` 清零或升级待裁决清单，校验双仓 CI 绿灯 |
| **阶段 3：交接与独立验收** | Day 7 | 提交 `V21_WAVE0_TEAM_A_HANDOFF_REPORT.md` 与隔离分支远端推送 | 提交 `V21_WAVE0_TEAM_B_HANDOFF_REPORT.md` 与 Track 1 Gate 3 补证包 | **Gate Review**：独立验收团队直检双仓源码与复算哈希，呈报 Owner 签认解锁 Wave-V21-1 |

---

## 五、独立验收 L1–L5 门禁与 Wave-V21-0 六项退出门槛

仅当独立验收团队通过远端只读拉仓复核全部通过 **L1–L5 门禁** 且满足以下 **6 项退出门槛**，Wave-V21-0 方可正式结项并申请开启下一实施波次（Wave-V21-1）：

| 门禁 / 门槛 | 硬性验收指标 | 失败处置 |
|---|---|---|
| **L1 · 边界与零重复守门** | `verify_v21_boundaries.py` 全绿：`knowledge-sdk` `dependencies == []`、零 12 项红灯重复代码、Schema 保持 `v6`、OpenBot `main@58287aa4` 零污染、Semantic Object 零双写 | 任一项漂移直接退回整改 |
| **L2 · 跨语言契约 SHA-256 互认** | 团队 A 与团队 B 对 `contracts/v21-reuse-v1/` 全部文件计算的 SHA-256 逐字节一致，Python 与 TypeScript 黄金向量测试 100% 通过 | 存在未登记分歧不得冻结契约 |
| **L3 · Track 1 Space Gate 3 收口实证** | 团队 B 30 项 `partial` 穿透完成且无未登记高风险写权绕过；`PRE-02` 处置建议单具备安全/产品可签批口径；既有 M2-B / B3 / vault-sync 零退化 | Gate 3 维持 `NOT_MET`，继续阻断 Schema v7 |
| **L4 · 安全与治理红线实测** | 沙箱测试证明 Mode A/B/C Fail-Closed、零自由 Text-to-SQL、`KnowledgeRetrievalPlan` 双视图脱敏、四通道撤权回执、高风险禁 `partial_available`、`data-capability-tool` 保持 `knowledge-object-only` | 任一安全不变量未证明不得放行 |
| **L5 · Stream A–E 穿透完整度** | 五大专项全部按 10 项字段闭环，Stream B 逐连接器区分真实驱动与 Mock/Demo，Stream C 核清 AOR Stage 4 真实实码状态 | 仅凭 README 结论一律拒收 |
| **退出门槛 6 · 审批与授权解耦** | 严禁越权生成 `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` 或合入 Schema v7 DDL；Wave-V21-1 编码授权须待独立验收通过并由 Owner 书面签发 | 越权改动直接作废分支 |

---

## 六、可直接下发双团队的执行指令摘要（Direct Dispatch Briefs）

### 6.1 发给团队 A（knowledge-sdk）的直接派单指令

```text
【派单指令｜团队 A（knowledge-sdk）｜Wave-V21-0】
1. 锚点与分支：严禁改动 main@b953c992、07f5d39f、9940818b、4bed2a1c 及现有 Schema v6 migrations/；请基于 9940818b 切出新分支 feat/v21-wave0-contracts-and-adapters。
2. 核心纪律：严格遵守 Master Architecture v2.1 三大原则（Reuse Before Build / One Capability, One Authority / Optimize the Existing Execution Platform），pyproject.toml 必须保持 dependencies = []，严禁自建 Agent Runtime、Model Provider/Vault/Fallback、Tool/MCP/Workflow、DB/ERP 连接器、Memory Distillation 或 Bandit。
3. 本波次 5 项交付（VA-1 至 VA-5）：
   - VA-1：在 contracts/v21-reuse-v1/ 冻结 5 组跨系统契约（Model/Embedding Adapter、Mode A/B/C Controlled Data Bridge、CogniWeave Memory/Revocation、Unified AIExecutionTrace、/v3/* 扩展草案）与脱敏黄金向量，输出 v21-contract-manifest.json（SHA-256）。
   - VA-2：在独立沙箱模块实现零生产 DDL 原型：Resource != Capability（ResourceCapabilityBinding）、IKC 三段解耦与蓝绿发布（高风险禁 partial_available）、KSG-Lite（Phase 0 零 DDL）与只读 SemanticReference。
   - VA-3：补齐四通道撤权闭环（含 RevocationPurgeReceipt）与 KnowledgeRetrievalPlan 双视图脱敏（redacted_unauthorized_count）沙箱自动化测试。
   - VA-4：新增 scripts/verify_v21_boundaries.py 并接入 CI，确保 verify_frozen.py 28 项 M1 资产与 Schema v6 零漂移。
   - VA-5：交付 V21_WAVE0_TEAM_A_HANDOFF_REPORT.md 与 CI 全绿实证。
4. 明确禁止：schema_v7_ddl_authorized=false，严禁任何 Schema v7/v8/v9 生产迁移、切流或宣称 T-01..T-27 已通过。
```

### 6.2 发给团队 B（openbot-vp）的直接派单指令

```text
【派单指令｜团队 B（openbot-vp）｜Wave-V21-0】
1. 锚点与分支：严禁改动 main@58287aa4，严禁开 PR，严禁混入 16 份未归属草稿，严禁触碰 knowledge-sdk，保持 OPENBOT_KNOWLEDGE_SDK_V2_ENABLED=false。Track 1 Space 收口锚定 codex/openbot/knowledge-sdk-v2-min-slice-adapter@f0fccbd3；Track 2 请基于 f0fccbd3 新建隔离分支 codex/openbot/v21-wave0-audit-and-adapters。
2. 核心纪律：全面贯彻 Master Architecture v2.1，OpenBot 保持 Agent Runtime / Model Services / Enterprise Data Gateway / Semantic Object（openbot-enterprise-semantic-objects.json）唯一写主，严禁与 SDK 双写 Semantic Object，保持 data-capability-tool.ts:99-108 knowledge-object-only Fail-Closed 不变。
3. 本波次 5 项交付（VB-1 至 VB-5）：
   - VB-1（Track 1 优先）：穿透 6 项 P0 写/调用链（E010/E029/E037/E068/E070/E080）并输出 loadKnowledgeSourceBundle / loadEnterpriseStoreBundle 共享过滤器穿透专节以推动 30 项 partial 归零；交付 PRE-02 读门分裂、email 成员与 local-operator 处置建议单；待命响应 EXT-02 DBA 脱敏统计。
   - VB-2（Stream A–D 实码穿透）：按 10 项标准字段穿透输出 4 份代码级审计报告（严禁只读 README）：A 明确 models.embed 公开代理改造面与无神经 Reranker 现状；B 逐连接器甄别真实驱动 vs Mock/Demo 及 Mode A/B/C 解锁安全前置；C 核实 AOR Stage 4 真实实码与测试覆盖及 Trace 接入点；D 核查 CogniWeave 撤权接口与本地 124 项知识入口委派/退场清单。
   - VB-3：在隔离分支落地默认关闭的 SemanticObjectCatalogReadAdapter（只读脱敏）、ControlledDataBridgeGuard（Mode A/B/C 守卫）与 AIExecutionTraceHeaderPropagator 单测。
   - VB-4：拉取复算团队 A contracts/v21-reuse-v1/ 全部 SHA-256 与 TS DTO 兼容性，登记 V21-DELTA-*。
   - VB-5：交付 V21_WAVE0_TEAM_B_HANDOFF_REPORT.md 与全量零退化回归证明。
4. 明确禁止：严禁自签 Exit Gate 3/4、严禁提前生成 FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md、严禁启用生产影子/迁移/切流。
```

---

## 七、现行冻结状态与签认追踪表

```yaml
directive_id: "WAVE_V21_0_DUAL_TEAM_DIRECTIVES"
architecture_baseline: "Master Architecture v2.1 — Existing Capability Reuse Baseline"
track_1_space_pre_v7:
  gate7_status: "MET"
  gate3_status: "NOT_MET"
  gate4_status: "NOT_MET"
  next_owner_approvals_needed: ["EXT-01", "EXT-02", "EXT-03", "EXT-04"]
track_2_v21_wave0:
  team_a_branch: "feat/v21-wave0-contracts-and-adapters"
  team_b_branch: "codex/openbot/v21-wave0-audit-and-adapters"
  team_a_tasks: ["VA-1", "VA-2", "VA-3", "VA-4", "VA-5"]
  team_b_tasks: ["VB-1", "VB-2", "VB-3", "VB-4", "VB-5"]
frozen_guardrails:
  schema_v6_frozen: true
  v2_spaces_contract_frozen: true
  schema_v7_ddl_authorized: false
  schema_v8_v9_ddl_authorized: false
  final_alignment_frozen: false
  prod_shadow_migration_cutover_authorized: false
  openbot_v2_flag_default: false
```
