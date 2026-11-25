# 团队 A 执行指令书（对齐第一波次 · Align-Wave1）

> 文档路径：`docs/architecture/knowledge-sdk-alignment/05_TEAM_A_EXECUTION_DIRECTIVE_WAVE1.md`
> 下发角色：架构治理与验收负责人（团队 A 统筹）
> 执行对象：Knowledge SDK 实施工程团队（Execution Agent）
> 基线分支：`feat/q3-phase2-rerank-eval`（Commit `d1532951b08c8ef950dc604aa3427ceb9eab5d75`）；不动 `main`（`b953c99`）与标签 `v2.0.0`（`4afc1d7`）
> 目标实施分支：`feat/align-wave1-core-compat`
> 生效日期：2026 年 11 月 24 日

---

## 一、总体授权与补充指令约束

你作为 Knowledge SDK 实施团队，立即按本指令书启动 **Align-Wave1（对齐第一波次）** 研发。本波次在 **M1 跨仓契约联合评审尚未正式签认** 期间并行推进，核心目标是：

1. 将 Phase 0–2 审计与规划文档正式归档入库，保障跨团队与跨 Agent 可读。
2. 零冲突落地 **Layer-1 兼容能力补齐**（承接 OpenBot 必需的空间/成员/版本/回收站与连接器预演能力），**严禁改写 Schema v5 表结构或破坏 `/v1/*` 既有契约**。
3. 完成 **Workstream A 基础能力收尾**（Reranker 延迟剖析与优化、HTTP/Python/MCP 三端权限一致性回归套件、容器化与健康/指标基线）。
4. 交付 **Workstream C 团队 B 并行集成资产包**（`/v2/*` OpenAPI 3.1 草案、TypeScript DTO 草案、跨仓权限/URI 契约夹具），让 OpenBot 团队 B 无需等待 M2 即可启动 Adapter 开发。

**核心铁律**：不得等待 SDK 全部功能完成才启动集成支持；不得擅自锁定须经 M1 联审的 Layer-2 不可逆模型变更；不得执行生产数据迁移、合并 `main`、打标签或生产部署。

---

## 二、任务边界（IN SCOPE / OUT OF SCOPE）

### 2.1 本波次必须完成（IN SCOPE）

- **Task 0（文档入库与分支初始化）**：从 `feat/q3-phase2-rerank-eval@d153295` 切出新分支 `feat/align-wave1-core-compat`，将 `00_CURRENT_STATE_AUDIT.md` 至 `05_TEAM_A_EXECUTION_DIRECTIVE_WAVE1.md` 六份文档完整提交至 `docs/architecture/knowledge-sdk-alignment/`。
- **Task 1（Layer-1 兼容管理与生命周期能力）**：在不升级 Schema 版本（维持 Schema v5）的前提下，补齐空间、成员、版本、回收站与连接器预演等兼容接口，同时打通 `LocalKnowledgeClient`、`HttpKnowledgeClient`、`server/app.py`（`/v1/*`）与双引擎（SQLite + PostgreSQL+pgvector+RLS）。
- **Task 2（基础能力收尾、性能治理与三端权限一致性）**：优化 `DeterministicLexicalReranker` / `hybrid.py` 候选重排延迟；建设 HTTP/Python/MCP 三端统一权限一致性矩阵测试；交付标准 `Dockerfile`、`/v1/ready` 探针与防泄漏指标导出。
- **Task 3（团队 B 契约草案与联调夹具包）**：交付 `openapi-v2-draft.yaml`、`openbot-adapter-dto.d.ts` 与 `contract-fixtures/` JSON 夹具，支撑 M1 联合评审与团队 B 并行开发。

### 2.2 本波次严禁触碰（OUT OF SCOPE）

- **严禁执行 Schema v5 到 v6 迁移**（如新增 `version_id` 列、`ingestion_jobs` 表、`asset_type` 物理列、或原规划的 `EvidenceGraph` 图谱表），上述结构变更必须等待 M1 签认后在 Wave2 统一设计可回滚迁移。
- **严禁上线运行时 `/v2/*` 路由或删除/修改既有 `/v1/*` 62 个端点的请求与返回格式**（本波次仅交付 `/v2` OpenAPI 草案）。
- **严禁实现物理硬删除 `purge_document`**（属 Layer-2 高敏感能力，须待 M1 评审明确证据包冻结冲突规则与回滚/留痕方案后再实现）。
- **严禁修改既有 115 条黄金基准用例**（`G1`–`G9` 必须保持原样 100% 通过）。
- **严禁开发 P3 领域扩展**（Ontology、完整知识图谱、`pack-pharma` 创新药垂类包、非必需第三方连接器）。
- **严禁引入与新架构冲突的设计**（邮箱作为 ACL/成员主键、Agent 绑定绕过用户 ACL、在 SDK 内硬编码 OpenBot 租户别名或私有业务字段）。
- **严禁破坏零运行时强依赖**：`pyproject.toml` 中 `[project.dependencies]` 必须保持 `[]`。
- **严禁修改 `main`、推送标签、修改 `pyproject.toml` 发版版本号或触发外部部署**（仅在交接报告中记录 `1.2.0` vs `v2.0.0` 版本漂移供统筹决策）。

---

## 三、分项工程任务书

### Task 0：文档归档与实施分支建立

1. 确认基于 `feat/q3-phase2-rerank-eval@d153295` 创建并切换到分支 `feat/align-wave1-core-compat`。
2. 将以下 6 份对齐文档完整归档至 `docs/architecture/knowledge-sdk-alignment/`（确保 UTF-8 无截断）：
   - `00_CURRENT_STATE_AUDIT.md`
   - `01_OPENBOT_REQUIREMENTS_MAPPING.md`
   - `02_DOMAIN_MODEL_ALIGNMENT.md`
   - `03_DOMAIN_CONTRACTS.md`
   - `04_TEAM_A_NEXT_STAGE_EXECUTION_PLAN.md`
   - `05_TEAM_A_EXECUTION_DIRECTIVE_WAVE1.md`
3. 校验原工作区与 115 条黄金基准在改动前完整可读，不做任何静默修改。

### Task 1：Workstream B · Layer-1 零冲突兼容能力补齐（双引擎 + HTTP v1）

全部新增方法必须严格经过 `DefaultPolicyEngine` 权限检查、多租户 `org_id` + PostgreSQL `FORCE RLS` 隔离与链式 `AuditEvent` 留痕，且不得更改 Schema v5 表结构：

1. **知识空间管理补齐**：
   - `get_kb(actor, kb_id, *, agent=None, purpose=Purpose.READ, policy_context=None) -> KnowledgeBase`：按空间读权校验，跨租户或无权时遵循防存在性泄漏策略拒绝。
   - `update_kb(actor, kb_id, *, name=None, visibility=None, governance_tier=None, agent=None, purpose=Purpose.READ, policy_context=None) -> KnowledgeBase`：仅空间 Admin / Owner（符合 `MANAGE_SPACE` 权限且满足 `User ∩ Agent`）可执行，变更写入 `AuditEvent`；禁止修改 `kb_id` 或跨租户转移 `org_id`。
2. **知识空间成员管理闭环（稳定 `user_id` 主键）**：
   - `list_kb_members(actor, kb_id, *, agent=None, purpose=Purpose.READ, policy_context=None) -> List[Dict[str, Any]]`（或对应冻结 dataclass）：仅允许空间 Admin / 具备管理权限主体查询，返回 `user_id` 与 `role` 列表；严禁引入 `email` 作为查询或授权键。
   - `revoke_kb_member(actor, kb_id, user_id, *, agent=None, purpose=Purpose.READ, policy_context=None) -> None`：仅空间 Admin 可执行，移除 `kb_members` 记录并写 `AuditEvent`；移除后被撤权用户立即无法访问该空间下私有/团队文档（同步触发或验证与 `MidTaskRevocation` / 运行期任务撤权兼容）。禁止撤销最后一个空间 Owner 导致孤儿空间（返回 `ConflictError` 或 `ValidationError`）。
3. **版本列举、差异对比与安全回滚（Append-Only）**：
   - `list_document_versions(actor, doc_id, *, agent=None, purpose=Purpose.READ, policy_context=None) -> List[DocumentVersion]`：校验文档读权（遵守显式 Deny 与归档可见性规则），按 `version` 升序或明确顺序返回版本元数据列表（不得泄漏未授权正文）。
   - `diff_document_versions(actor, doc_id, from_version, to_version, *, agent=None, purpose=Purpose.READ, policy_context=None) -> Dict[str, Any]`：基于纯标准库（如 `difflib` / 段落与哈希比对）输出结构化差异摘要，且文本片段必须先经过 `RedactionRegistry` Fail-Closed 脱敏处理。
   - `rollback_document(actor, doc_id, target_version, *, agent=None, purpose=Purpose.READ, policy_context=None) -> DocumentVersion`：需要 `WRITE_DOCUMENT` 权限（L2 受控空间回滚须进入 `draft` / 遵循既定审批规则，不得绕过 L2 三分离发布），基于 `target_version` 原文与元数据**创建新递增版本 `current_version + 1`**，在 `AuditEvent` 中记录 `rollback_from_version`，**严禁覆写或物理删除任何历史版本**。
4. **回收站显式筛选**：
   - 兼容扩展 `list_documents(actor, kb_id=None, include_archived=False, *, archived_only=False, ...)`：当 `archived_only=True` 时仅返回当前主体有权管理的已归档文档，支撑 OpenBot 回收站列表展示；默认 `archived_only=False` 与原有行为 100% 一致。
5. **连接器两阶段预演接口**：
   - 在 `ConnectorSyncRunner` 补齐只读 `plan_sync(...)`，输出 `to_upsert`、`to_tombstone`、`unchanged_count` 结构化预演清单，不写入数据库也不推进 `ConnectorCursor`，与既有提交同步逻辑保持行为同构。
6. **客户端与 HTTP 透传**：
   - 以上新增方法同步注册至 `LocalKnowledgeClient`、`HttpKnowledgeClient`（`OPERATIONS`）与 `server/app.py`（`/v1/*` 兼容路由），同时保持既有 62 个操作签名和路由零改动。

### Task 2：Workstream A · 性能治理、三端权限一致性与部署监控基线

1. **Reranker 候选路径延迟优化**：
   - 剖析 Q3-M2（`d153295`）中 `DeterministicLexicalReranker` 与 `retrieval/hybrid.py` 候选构建延迟来源（如重复分词、多余正则编译、重复拷贝或过宽 `rerank_top_k`），实施纯标准库零依赖优化。
   - 在同一机器与同一数据集上运行优化前后基准对照，留存真实延迟指标 JSON（P50 / P95 / 平均耗时），确保离线评测集 NDCG@3、24/24 拒答、0 越权、0 隐式模型调用与 115/115 黄金基准全部零退化。
2. **HTTP / Python / MCP 三端权限一致性回归套件**：
   - 新增独立测试模块（覆盖 SQLite 与 PostgreSQL 双引擎），对同一批权威权限用例在 `LocalKnowledgeClient`、HTTP `/v1/*`、MCP 4 工具三端执行等价断言：
     - 跨租户隔离（含 PG RLS）。
     - 文档显式 Deny 覆盖 Owner / Admin。
     - `Effective = User ∩ Agent` 权限交集（**专项反例**：即使 `AgentProfile.allowed_kb_ids` 包含某私密库，若人类 `Actor` 非该库成员，三端均必须拒绝，彻底验证不存在 `canReadViaRobotBinding` 类越权）。
     - `policy_generation` 过期与 SCIM 禁用主体秒级撤权。
     - Fail-Closed `RedactionRegistry` 异常拒放。
     - 撤销 KB 成员（`revoke_kb_member`）后立即拒绝读取与检索。
3. **独立部署与可观测性基线**：
   - 新增标准多阶段 `Dockerfile`（仅暴露 HTTP/MCP 服务，不改变 `pyproject.toml` 零强依赖）及最小运行说明。
   - 新增 `GET /v1/ready` 就绪探针（校验底层存储连接与 Schema 版本可用性，不泄漏 DSN/凭据）及结构化指标收集与导出端点（如 `GET /v1/metrics` 或可配置 Prometheus 文本指标，严禁在标签或日志中记录文档正文、Query 原文、Token 或密钥）。

### Task 3：Workstream C · 团队 B 并行集成资产包（M1 评审与 Adapter 预备）

在 `docs/architecture/knowledge-sdk-alignment/contracts/` 目录交付三类可直接供 OpenBot 团队 B 审阅与编写 Adapter 的契约资产：

1. `openapi-v2-draft.yaml`：严格对齐 `03_DOMAIN_CONTRACTS.md`（C-01 至 C-09）的 OpenAPI 3.1 草案，显式标注 `x-contract-status: draft-pending-m1-freeze`，覆盖统一请求头（`X-Request-Id`、`X-Tenant-Id`、鉴权上下文）、空间/成员/资产/版本/检索/证据/异步作业/连接器路径及统一错误信封（`error.code`、`retryable`、`request_id`）。
2. `openbot-adapter-dto.d.ts`：与 OpenAPI 草案逐字段一致的 TypeScript 接口与错误码联合类型定义，并附 `kb:// <-> ku://` 双轨引用转换类型契约。
3. `contract-fixtures/`：包含至少 6 组可机器校验的 JSON 契约夹具（`identity-context.json`、`agent-intersection-deny.json`、`kb-lifecycle.json`、`dual-uri-evidence.json`、`calibrated-search-response.json`、`error-envelope.json`），配套最小校验脚本验证夹具与 OpenAPI 草案一致。

---

## 四、验收标准与五层证据要求（L1 至 L5）

本波次交付必须通过以下五层硬验收门禁，任何一项未达成均不得宣称 Wave1 完成：

| 层级 | 验收项 | 硬性通过标准 |
|---|---|---|
| **L1** | 纯标准库离线门禁 | `python3 -S -W error::ResourceWarning` 全量测试 0 失败、0 `ResourceWarning`；验证 `pyproject.toml [project.dependencies] == []` 且 Schema 版本保持 `5` 未变更 |
| **L2** | 全依赖双引擎 + 四作业 CI | SQLite 与真实 PostgreSQL+pgvector+RLS 双引擎全量测试通过；GitHub Actions 全作业全绿；既有 **115/115 黄金基准 0 修改、100% 通过**；新增 Wave1 双引擎用例全部通过 |
| **L3** | 三端一致性、性能对比与部署探针 | 留存 HTTP/Python/MCP 三端权限一致性实跑日志；留存 Reranker 优化前后延迟对比 JSON；验证 `/v1/health`、`/v1/ready`、指标防泄漏测试及 `Dockerfile` 语法/构建检查 |
| **L4** | 契约资产自检与安全边界检查 | 运行脚本校验 `openapi-v2-draft.yaml` 合法性及 `contract-fixtures/*.json` 一致性；校验所有新增 API 错误响应体不泄漏未授权资源存在性或正文；若未修改 UI，明确记录“无 UI 变更，沿用已验收浏览器基线” |
| **L5** | 交接报告与 Git 收口纪律 | 归档 `docs/acceptance/v2.1-align-wave1/ALIGN_WAVE1_HANDOFF_REPORT.md`；提交并推送至 `feat/align-wave1-core-compat`；**未改动 `main`、未打标签、未执行生产迁移或外部部署** |

---

## 五、交接汇报格式要求

执行完成并推送 `feat/align-wave1-core-compat` 后，请按以下五段式向验收负责人汇报：

1. **分支、Commit 与 CI 实跑链接**：提供最新 Commit SHA、四作业 GitHub Actions Run 链接及归档交接报告路径。
2. **分任务实际完成情况与代码证据**：逐项列出 Task 0–3 实际改动文件路径、新增方法与新增测试数量。
3. **量化测试与性能结果**：汇报纯标准库测试数、全依赖测试数（含跳过原因）、115/115 黄金基准原样通过结果、三端权限一致性结果及 Reranker 延迟优化前后数据。
4. **未覆盖项与剩余风险**：诚实列出任何跳过的外部依赖（如在线 Qdrant）、Docker 构建环境限制或发现的新接口冲突。
5. **等待 M1 冻结与下一步建议**：列出已就绪待团队 B 审阅的契约资产，等待架构统筹验收并下发 **Align-Wave2（M1 冻结后 Layer-2 + Schema 演进 + `/v2/*` 运行时落地）** 指令书。
