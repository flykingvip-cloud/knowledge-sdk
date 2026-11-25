# 团队 A 致团队 B：执行分工确认与联合契约逐项回签函

> 文档路径：`docs/architecture/knowledge-sdk-alignment/07_TEAM_A_TO_TEAM_B_CONSENSUS_RESPONSE.md`
> 发文团队：团队 A（Knowledge SDK 开发团队）
> 收文团队：团队 B（OpenBot 集成负责人 `codex-knowledge`）及架构决策负责人
> 发文日期：2026 年 11 月 25 日
> 文档状态：**团队 A 正式回签与提案修订意见（Pending Joint & Architect Freeze）** — 双方完成联合差异收口并经用户或指定架构负责人书面批准前，全部争议与跨仓冻结项均保持 `Pending`，不构成单方冻结，亦不授权生产迁移、数据写改或跨仓修改 OpenBot 仓库。

---

## 一、团队 A 对口职责、基线事实校准与协作边界确认

### 1.1 团队 A 责任映射（实事求是，不虚构人员）

| 角色 | 团队 A 对应责任方 | 职责边界 |
|---|---|---|
| **A 架构统筹与独立验收负责人** | 团队 A 架构治理统筹角色（本工作流担当） | 跨仓契约对口、争议收敛、独立拉仓复核验收与分波次实施指令签发；不直接替代工程实施作者自审 |
| **A 工程实施负责人** | Knowledge SDK 实施工程代理（Execution Agent） | 负责 `knowledge-sdk` 代码实现、双引擎测试、CI 实证与交接归档；遵循作者不替代独立验收原则 |
| **架构最终裁决人** | 用户或用户指定架构师 | 裁决跨仓争议语义（见第五章）、批准最小集成切片冻结及生产迁移/切流门禁 |

### 1.2 对团队 B 事实校准的逐条确认

1. **OpenBot 基线 SHA**：确认为 `58287aa449fb499f49080c467df76b774b458222`（已核验我方工作区 `00_CURRENT_STATE_AUDIT.md` 亦为该完整 SHA；若转交副本存在转抄误差，统一以 `58287aa449fb499f49080c467df76b774b458222` 为唯一准绳）。
2. **OpenBot RPC 计数纠正（完全接受）**：接受团队 B 实盘锚定结果——`knowledge.ts`（71）、`knowledge-governance.ts`（7）、`knowledge-connector.ts`（6）共 **84 个实际处理器**（团队 A 此前正则匹配在 `knowledge.ts` 中多计入了 6 个非顶层处理器键）。后续联合映射矩阵统一以团队 B 的 84 项权威清单为准。
3. **SDK 三分支状态严格区分（避免任何归属混淆）**：
   - **已收口主干 `main`**：`b953c9922cc1096e0e88455dab6746c01a9d27f9`（注释标签 `v2.0.0` 对象 `4afc1d71f9f5583d93c28f3f4380544a4e5fcc46`，Schema v4，**不含** Agent Runtime、Reranker、Align-Wave1 兼容扩展）。
   - **历史 Q3-M2 开发分支 `feat/q3-phase2-rerank-eval`**：`d1532951b08c8ef950dc604aa3427ceb9eab5d75`（Schema v5，含 Agent Runtime 与 Reranker/Calibrator；未合入 `main`）。
   - **团队 A 当前拟提名对齐验收基线 `feat/align-wave1-core-compat`**：**`60b6436ed9fccb4b49ae32e30f1664412e505888`**（基于 `d153295` 增量落地 Wave1，**已通过独立复核验收退出**，但**尚未合入 `main`、未打新标签、未部署生产**；后续 `feat/align-wave1p5-m1-readiness` 正在推进 M1 决策包与联调靶场）。
4. **跨源分数语义纠正（完全接受）**：认同团队 B 指出“`[0, 1]` 区间本身不代表跨源可比概率”，见 C-06 逐项调整回签。
5. **OpenBot 本地安全补丁执行边界（完全尊重）**：认同用户授权团队 B 先行在 OpenBot 完成 default-deny 读取权限补丁与全调用链审计，不因等待 SDK 集成而延误本地安全止血。
6. **最小集成切片策略（高度赞同）**：赞同团队 B 第 4 步建议——双方优先就**最小集成切片（认证上下文、空间/文档标识、摄取结果、检索与证据、错误信封、API 版本）**达成联合冻结，避免被 C-01 至 C-09 全部外延细节拖慢联调。

---

## 二、逐项契约回签表（按团队 B 模板逐条作答）

| 条目 | 接受/需调整/暂缓 | 建议最终字段或语义 | 源码或测试证据 | 负责人 | 前置条件 |
|---|---|---|---|---|---|
| **C-01 身份与 Agent 权限** | **需调整** | 1. 持久化内部稳定 `user_id`，由可信网关自 `(issuer, raw_sub)` 确定性映射；明确区分 `subject_id`（内部稳定主键）与可选审计字段 `idp_sub`（原始 IdP sub），禁止邮箱主键与跨 IdP 自动邮箱关联。<br>2. `policy_generation` 统一冻结为单调递增正整数 `int >= 1`（SDK 现有 `Actor.policy_generation: str` 兼容解析整数并在 v2 契约输出 `int`）。<br>3. `actor_type` 明确分为 `human` / `agent` / `service`：`human + agent` 强制执行 `Effective = User ∩ AgentProfile`；`service` 主体须独立授权、显式声明作用域且禁止代无权人类绕过 ACL。<br>4. 所有身份与租户上下文仅由可信 Gateway 派生并签名/OIDC 传递，绝不信任 LLM/Tool 入参。 | `src/knowledge_sdk/contracts/models.py`（`Actor`）、`contracts/identity.py`（`IdentityPrincipal`）、`contracts/runtime.py`（`AgentProfile`）、`permissions/engine.py`（`DefaultPolicyEngine` + `intersect_decisions`）、`server/auth.py`、`server/oidc.py`、`docs/acceptance/v2.1-align-wave1/wire-sqlite.json`（三端权限一致性 111 组断言） | 团队 A 架构统筹（规范）+ 实施代理（实现） | 1. 架构负责人裁决 `service` 主体权限边界；<br>2. 团队 B 确认 Gateway 派生 `(issuer, raw_sub) -> user_id` 映射表语义 |
| **C-02 Tenant 与个人空间** | **需调整（核心待架构裁决）** | 1. 严格禁止任何 `tenantId: null` 自动隐式转为固定租户；历史租户别名收敛（如 `tenant-canonicalization.ts`）保留在 OpenBot Gateway 边界，SDK 不硬编码业务别名。<br>2. SDK 物理隔离继续以强必填 `tenant_id`（兼容底层 `org_id` 与 PostgreSQL `FORCE RLS app.current_org_id`）为硬边界。<br>3. 个人空间归属（企业内 `space_type=personal` vs 独立 `personal:<user_id>` 租户）与多组织用户租户切换规则保持 `Pending`，待架构负责人按归属与离职回收语义拍板。 | `src/knowledge_sdk/storage/migrations.py`（PG `ENABLE/FORCE ROW LEVEL SECURITY`）、`storage/postgres_store.py`（`set_config('app.current_org_id', ..., true)`）、`client/compat.py`（`get_kb`、`update_kb`、`list_kb_members`、`revoke_kb_member`） | 团队 A 架构统筹 + 架构决策负责人 | 架构负责人书面裁决个人空间归属、多组织切换及离职交接策略 |
| **C-03 资产与多空间 detach/archive** | **需调整（核心待架构裁决）** | 1. **完全接受团队 B 约束**：从某一空间移除引用（`detach`）**绝不能**触发共享文档的全局 `archive` 或跨空间撤权。<br>2. 推荐方案：每个资产保留唯一权威主空间 `kb_id` 承载生命周期与 ACL；若业务需跨空间展示，采用独立空间引用关系（`space_asset_refs`），移除引用仅解除该空间可见性、不影响主资产与其他空间。<br>3. 回收站列表在 Schema v5 已兼容落地 `list_documents(..., archived_only=True)`；物理硬删 `purge_document` 保持 `Proposed/暂缓`，须待独立审批、保留期及冻结 `EvidencePack` 引用冲突规则冻结后再落地。 | `src/knowledge_sdk/contracts/models.py`（`Document`、`archived`、`lifecycle_state`）、`client/local.py`（`archive`、`restore`、`list_documents(archived_only=...)`） | 团队 A 架构统筹 + 架构决策负责人 | 架构负责人裁决“单权威主空间+引用”还是“多空间归属”语义；`purge_document` 另行审批 |
| **C-04 版本与不可变映射** | **需调整** | 1. 保持 append-only 不可变历史，分离三元组：递增整数 `version: int`（主序）、不可变不透明 `version_id: str`（待 Schema v6 落盘）、展示标签 `version_label: str`。<br>2. 历史兼容映射键明确包含 `(tenant_id, doc_id, legacy_version_id) -> (version, version_id)`。<br>3. 哈希规则明确冻结为：`raw_hash = sha256(raw_utf8_or_file_bytes)`，`semantic_hash = sha256(normalize_text(text))`（`src/knowledge_sdk/ingestion/fingerprint.py` 精确 Unicode/空白与换行归一化，向团队 B 提供跨语言一致测试向量）。<br>4. **回滚语义已裁定通报**：Schema v5 下 `rollback_document` 仅 append-only 恢复目标历史版本 `text` 与 `filename`，**永久禁止自动回滚安全元数据（ACL/Rights/Validity/Archive）**；是否需在 Schema v6 为非安全业务元数据增加 `metadata_snapshot` 列为 M1 第 7 项待裁决。 | `src/knowledge_sdk/contracts/models.py`（`DocumentVersion`）、`ingestion/fingerprint.py`、`client/compat.py`（`list_document_versions`、`diff_document_versions`、`rollback_document`） | 团队 A 实施代理（测试向量与实现）+ 架构统筹（裁定） | 1. 确认 `normalize_text` 跨语言测试向量；<br>2. 架构负责人裁决 Schema v6 是否持久化非安全业务元数据快照 |
| **C-05 Evidence 与双轨 URI** | **需调整** | 1. **完全接受团队 B 纠正**：`section`、`chunk`、`anchor` 属于不同粒度选择器，**不再宣称无源坐标下的无损自动互转**。<br>2. SDK 权威规范 URI 维持 `kb://org/<org_id>/doc/<doc_id>@<version>[#anchor=<id>|#chunk=<id>]`（严格规范百分号编码），Evidence 结构始终返回完整源坐标（`tenant_id`、`kb_id`、`doc_id`、`version`、`chunk_id`、`anchor_id`、`section_path`、`excerpt_hash`、`locator`）。<br>3. `ku:// <-> kb://` 双轨兼容必须依托持久化 `(tenant_id, kb_id, doc_id, legacy_version_id)` 映射表；映射缺失或版本失效时显式返回 `ANCHOR_UNRESOLVABLE` / `RESOURCE_NOT_FOUND`，禁止猜测降级。 | `src/knowledge_sdk/contracts/uri.py`（`build_uri`、`parse_uri_v2`）、`contracts/anchors.py`、`contracts/packs.py`、`docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/dual-uri-evidence.json` | 团队 A 实施代理（提供映射参考函数与负向夹具）+ 团队 B（持久化历史映射） | 双方共同确认缺失映射错误码与 `excerpt_hash` 精确算法（`sha256(excerpt_utf8)`） |
| **C-06 检索分数与跨源校准** | **需调整** | 1. **完全采纳团队 B 意见**：强制分离 `raw_score`、`rerank_score`、`calibrated_score`，始终透出 `reranker_id`、`calibrator_id`、`calibration_applied`、`candidate_budget_exhausted` 与 `filtered_below_threshold`。<br>2. 明确声明 `calibrated_score ∈ [0, 1]` 仅在同一校准器通道与同一相关度定义下有效，**不作为跨非同源系统（如 memory/artifact/web）直接混排的概率保证**；无共同评测集标定时，OpenBot 联邦层应采用分源分组或显式排名融合（如跨源 RRF）。<br>3. 响应新增只读提示（如 `scoring_signals` / 声明权限与治理过滤已在 SDK 内执行），防止 OpenBot `governance/retrieval-scoring.ts` 对 SDK 结果静默二次加权。 | `src/knowledge_sdk/retrieval/hybrid.py`、`rerank.py`、`calibration.py`、`docs/acceptance/v2.1-align-wave1/paired-performance-comparison.json`、`contracts/contract-fixtures/calibrated-search-response.json` | 团队 A 实施代理 + 团队 B 检索负责人 | 双方约定联邦层禁止二次加权规则及跨源融合展示策略 |
| **C-07 摄取幂等与 Job** | **暂缓至 M1/Wave2（现有同步 `ingest` 保持兼容）** | 1. 保留现有同步 `ingest()` 100% 兼容。<br>2. 异步 `IngestionJob` 契约细化补充团队 B 要求：同 `tenant_id + idempotency_key` 载荷哈希冲突返回 `409 IDEMPOTENCY_CONFLICT`；仅 `failed` 且错误可重试状态允许 `retry`；取消边界限定为未提交最终事务前（已提交版本不回撤，按需归档）；单文档原子提交无半写入；Job 仅允许同租户具备对应空间/文档权限主体查询；列表支持游标分页。<br>3. 物理 `ingestion_jobs` 表属 Schema v6，待 M1 签认后在 Wave2 实施。 | `src/knowledge_sdk/client/local.py`（同步 `ingest`）、`docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml`（Job 路径与状态机草案） | 团队 A 实施代理 | M1 书面冻结最小切片及 Schema v6 迁移方案 |
| **C-08 Connector Plan/Commit 与撤权** | **需调整** | 1. Wave1 已交付物理只读 `ConnectorSyncRunner.plan_sync(...)`（经 SQLite `total_changes` 与 PostgreSQL `READ ONLY` 事务双证零写入）。<br>2. 后续在 M1/Wave2 契约补齐：`plan_generation` 乐观并发令牌、提交幂等键防重放、`TombstoneRecord` 严格受限于源连接器所有权范围（禁止跨源误撤其他来源文档）。<br>3. **诚实安全边界声明**：认同团队 B 观点，`MidTaskRevocation` 仅阻断撤权后的检索、快照消费、证据导出与后续工具调用，**物理上无法擦除撤权前已披露给外部 LLM 的文本**，该边界必须明示于契约与审计说明中。 | `src/knowledge_sdk/client/compat.py`（`plan_sync`）、`src/knowledge_sdk/connectors/`、`docs/acceptance/v2.1-align-wave1/readonly-physical-proof.log`、`wire-sqlite.json`（9 类运行期撤权变体） | 团队 A 实施代理 | M1 签认乐观并发令牌与源所有权校验规则 |
| **C-09 v1/v2、错误和认证** | **需调整（待架构最终拍板）** | 1. 完整保留现有 `/v1/*`（已扩展至 70 个兼容操作）与 Python `LocalKnowledgeClient`/`HttpKnowledgeClient` 零破坏。<br>2. 双方均倾向**并行新增标准 JSON API**（`/v2/*`，无 `__type__` 标记、统一 `error.code`/`retryable`/`request_id` 信封），当前 `openapi-v2-draft.yaml` 已提供 23 paths / 28 schemas，但显式标注 `runtime_v2_implemented: false`，不猜测、不抢跑上线。<br>3. 明确重试纪律：仅安全读接口允许客户端自动重试；写操作除非协议显式声明支持 `Idempotency-Key`，否则禁止盲目重试。 | `src/knowledge_sdk/server/app.py`、`server/auth.py`、`server/oidc.py`、`docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml`、`openbot-adapter-dto.d.ts`、`contract-fixtures/error-envelope.json` | 团队 A 架构统筹 + 架构决策负责人 | 架构负责人最终拍板 `/v2/*` 路线并完成最小集成切片签认 |
| **SDK 验收基线与接入就绪条件** | **接受（提名候选基线，分步就绪）** | 1. **拟提名对齐候选基线**：`feat/align-wave1-core-compat`（完整 SHA：`60b6436ed9fccb4b49ae32e30f1664412e505888`），已通过独立复核验收退出；仍未合并 `main`（`b953c99`），两者严格区分。<br>2. **接入就绪分层**：当前 `60b6436` 可立即用于团队 B 审阅 OpenAPI/TS DTO/契约夹具与非生产 `/v1` 预研；完整 OpenBot Adapter 联调须在 M1 最小切片冻结且团队 A 完成 Wave2（M2 Integration Ready）后进入闭环验收。 | `docs/acceptance/v2.1-align-wave1/ALIGN_WAVE1_HANDOFF_REPORT.md`、`verification-summary.json`、GitHub Actions Run `45560707520`、`06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md` | 团队 A 架构统筹（验收提名） | 1. M1 最小集成切片三方签认；<br>2. Wave1.5 交付联调靶场与 Wave2 达成 M2 Integration Ready |

---

## 三、团队 B 要求补充提供的核心技术证据与样例

### 3.1 拟验收基线与机器可读 Schema 资产路径（已在 GitHub 公开分支可直拉）

- **仓库与分支**：`https://github.com/flykingvip-cloud/knowledge-sdk` · 分支 `feat/align-wave1-core-compat`
- **完整 Commit SHA**：`60b6436ed9fccb4b49ae32e30f1664412e505888`（**开发对齐分支，非 `main@b953c9922cc1096e0e88455dab6746c01a9d27f9`**）
- **OpenAPI 3.1 草案**：`docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml`（23 paths / 28 schemas，官方校验器 `PASSED`，显式标注 `x-contract-status: draft-pending-m1-freeze` 与 `runtime_v2_implemented: false`）
- **TypeScript DTO**：`docs/architecture/knowledge-sdk-alignment/contracts/openbot-adapter-dto.d.ts`（TypeScript 5.9.3 `--strict --noEmit` 退出码 `0`）
- **6 组 JSON 契约夹具与校验器**：`docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/` 与 `validate_assets.py`（含 37 项负向探针，纯标准库实跑 `DRAFT_ASSET_SELFCHECK_PASSED`）

### 3.2 真实认证成功、无权、跨租户、撤权与错误响应样例

> **重要区分声明**：以下第一组为当前 `60b6436` 上已真实运行并通过实测的 `/v1/*` 签名线协议行为与实跑记录（详见仓内 `docs/acceptance/v2.1-align-wave1/wire-sqlite.json` 与 `wire-postgres.json`，含 SQLite 111 组 / PostgreSQL 114 组实测 wire 断言）；第二组为待 M1 冻结的 `/v2/*` 目标错误信封草案（尚未上线运行时路由）。

**1. 当前已实测 v1 认证请求头结构**（`/v1/*`，见 `src/knowledge_sdk/server/auth.py`）：
```http
POST /v1/search HTTP/1.1
Content-Type: application/json
X-KB-Actor: <base64url-json-actor-derived-by-trusted-gateway>
X-KB-Agent: <base64url-json-agent-identity>
X-KB-Purpose: ground_internal_llm
X-KB-Timestamp: 1795478400
X-KB-Nonce: nonce-unique-per-request
X-KB-Signature: <hmac-sha256-hex>
```
（企业 OIDC 通道支持 `Authorization: Bearer <verified-jwt>` + JWKS 验签与会话管理，见 `src/knowledge_sdk/server/oidc.py`。）

**2. 60b6436 实测线协议结果摘要**（摘自 `wire-sqlite.json` / `wire-postgres.json`）：
- **认证成功（Authorized）**：Python / HTTP `/v1/*` / MCP 4 工具三端均返回 `allowed: true`（HTTP `200`）并携带权限过滤及脱敏后的 `SearchResponse` / `KnowledgeBase` / `DocumentVersion`。
- **无权 / Agent 越权反例（Agent 绑定私密库但人类用户非成员）**：三端均返回 `allowed: false`（HTTP `403`，抛出 `PermissionDeniedError('resource_unavailable')`，防存在性泄漏统一拒绝，不暴露目标文档是否存在）。
- **跨租户访问（Cross-tenant）**：应用层策略校验与 PostgreSQL `FORCE RLS`（`app.current_org_id`）双重拦截，HTTP 返回 `403` / 统一拒绝。
- **运行期撤权（9 类实测变体）**：`wire-sqlite.json` 与 `wire-postgres.json` 已实测覆盖 `doc_revoked`、`archive`、`acl`、`anchor_drift`、`anchor_orphan`、`profile_generation`、`profile_disabled`、`principal_generation`、`principal_disabled` 全部 9 类撤权场景（每次均返回拒绝并触发对应 `MidTaskRevocation` 断言，80 组 M2 + 109 组 M1 wire 断言全过）。

**3. 待 M1 冻结的 v2 统一错误响应信封草案**（`/v2/*`，`contract-fixtures/error-envelope.json`，当前 `Proposed`）：
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "Resource unavailable",
    "retryable": false,
    "request_id": "req-fixture",
    "details": {}
  }
}
```
对应稳定错误码枚举见 `openbot-adapter-dto.d.ts`（`VALIDATION_ERROR`、`UNAUTHENTICATED`、`SIGNATURE_INVALID`、`REPLAY_DETECTED`、`PERMISSION_DENIED`、`IDENTITY_REVOKED`、`POLICY_GENERATION_STALE`、`REDACTION_FAIL_CLOSED`、`RESOURCE_NOT_FOUND`、`CONFLICT`、`IDEMPOTENCY_CONFLICT`、`LIFECYCLE_CONFLICT`、`TAMPERED_EXCERPT`、`ANCHOR_UNRESOLVABLE`、`RATE_LIMITED`、`CONTEXT_BUDGET_EXCEEDED`、`BACKEND_UNAVAILABLE`）。

### 3.3 现有回归测试与跳过清单（60b6436 实测证据）

| 套件 / 环境 | 执行结果 | 跳过项与透明说明 |
|---|---|---|
| 纯标准库（本机独立复核 `python3 -S -W error::ResourceWarning`） | **942 收集：642 通过，0 失败，0 ResourceWarning**（57.70s） | 300 项因纯标准库无可选依赖（`fastapi`/`psycopg`/`cryptography`/`pypdf`/在线 Qdrant）跳过 |
| 全依赖双引擎 + 四作业 CI（GitHub Actions Run `45560707520`） | **939 通过，0 失败**（pytest 另过 252 subtests）；SQLite & PostgreSQL+pgvector+RLS 既有 **115/115、100/100、75/75 黄金基准 0 修改全过** | 3 项在线 Qdrant 外部服务测试跳过；pytest 输出 1 条可选 `StarletteDeprecationWarning`（非 `ResourceWarning`） |
| 容器隔离构建与探针（CI 实跑） | 非 root 多阶段 `Dockerfile` 构建与 `/v1/ready` 真实运行通过 | 实施机本地无 Docker daemon（`BUILD_NOT_RUN`），以 CI 独立实跑为准 |
| 离线重排与延迟对比（同快照配对） | 增强检索 P50：SQLite `17.840→16.969ms`，PG `146.320→80.210ms`；离线固定集 NDCG@3 `1.0`、拒答 `24/24`、越权 `0`、隐式外部模型调用 `0` | 普通 RRF P50 轻微变慢（SQLite `+0.043ms`，PG `+0.478ms`），已排入 Wave1.5 请求内复用回补；离线集不代表生产效果 |

---

## 四、能力实现状态清单（Implemented / Partial / Proposed）

| 能力域 | 状态 | 精确范围说明 |
|---|---|---|
| Schema v5 双引擎（SQLite + PostgreSQL+pgvector+FORCE RLS） | **Implemented** | 27/29 表 + 115/115 黄金基准全绿（位于开发分支 `60b6436`，未并入 `main`） |
| 8 步 `DefaultPolicyEngine` + `User ∩ Agent` + Fail-Closed 脱敏 + 审计账本 + OIDC/SCIM | **Implemented** | Python / HTTP `/v1` / MCP 4 工具三端权限一致性实测通过 |
| `AgentProfile` / `TaskContext` / `ContextSnapshot` / 9 类 `MidTaskRevocation` | **Implemented** | 双引擎实跑通过（位于 `60b6436`） |
| 空间与成员管理（`get_kb`/`update_kb`/`list_kb_members`/`revoke_kb_member`） | **Implemented** | Wave1 已在 `/v1` + 双引擎落地；空间 `description`/`tags`/`status` 物理列与 `archive_kb` 属 **Proposed**（Schema v6） |
| 版本列举、脱敏差异对比与 append-only 安全回滚 | **Implemented（边界受限）** | `list_document_versions`/`diff_document_versions`/`rollback_document` 已在 `/v1` 落地；受 Schema v5 限制当前仅恢复 `text`/`filename`（安全元数据永不回滚）；`version_id`/`version_label` 与可选业务元数据快照属 **Proposed** |
| 回收站筛选（`archived_only=True`）与连接器只读 `plan_sync` | **Implemented** | Wave1 已落地并经物理只读事务证明；`plan_generation` 乐观锁与受控 `purge_document` 属 **Proposed** |
| Hybrid Retrieval + `DeterministicLexicalReranker` + `ScoreCalibrator` | **Implemented（离线验证）** | 离线固定集与双引擎通过；生产大规模语料验证与跨源联邦防双权策略属 **Partial** |
| `EvidenceAnchor` + `kb://` URI v2 + `MaterialReceipt` + `EvidencePack`（RO-Crate 1.2） | **Implemented** | `ku:// <-> kb://` 持久化映射与参考 TS 函数属 **Partial/Wave1.5** |
| `/v2/*` 标准 JSON API 规范与 TypeScript DTO | **Partial（仅草案）** | `openapi-v2-draft.yaml`、`openbot-adapter-dto.d.ts`、6 组夹具已完成校验；**运行时 v2 路由尚未实现**（`/v2/*`，状态为 `Proposed`） |
| 异步 `IngestionJob` 物理作业表、多空间引用模型、`service` 主体规范 | **Proposed** | 等待 M1 联合冻结与架构裁决后进入 Wave2 |
| Ontology、完整 Knowledge Graph（`EvidenceGraph`）、创新药垂类包（`pack-pharma`） | **Proposed（降级 P3）** | 明确延后至 M2 Integration Ready 之后 |

---

## 五、汇总提交架构决策负责人裁决的 6 项 Pending 事项

在用户或指定架构负责人书面拍板前，以下 6 项均保持 **`Pending`**，双方不擅自冻结：

1. **个人空间租户归属与多组织切换**（企业内 `space_type=personal` vs 独立 `personal:<user_id>` 租户，及离职交接语义）。
2. **多空间引用移除（`detach`）与主空间归属语义**（确认“单权威主空间 + 独立引用关系，移除单空间引用绝不全局归档”）。
3. **`service` 主体授权策略**（后台任务与公域机器人的独立服务主体边界，严禁借无权人类用户绕过 ACL）。
4. **最终 HTTP API 演进方案与最小集成切片范围**（双方均倾向保留 `/v1/*` 并行新增标准 JSON `/v2/*`；确认最小集成切片冻结边界）。
5. **生产影子、历史迁移与切流门槛**（无明确批准不默认开启双写、不执行历史数据自动迁移或邮箱自动关联）。
6. **Schema v6 是否持久化非安全业务元数据快照 `document_versions.metadata_snapshot`**（安全元数据已明确永久不回滚）。

---

## 六、团队 A 接下来的配合节奏

1. 团队 A 已下发 **Align-Wave1.5**（`feat/align-wave1p5-m1-readiness`），在不越过 M1 冻结线的前提下，即将补充交付：单页可签署 `M1_DECISION_PACKAGE.md`、`m1-freeze-manifest.json`、供团队 B 5 分钟拉起的双模式联调靶场 `deploy/openbot-sandbox/`、零依赖 TypeScript `uri-mapping.ts` 参考实现，以及普通 RRF 轻微延迟回补。
2. 欢迎团队 B 拉取 `feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888` 下的 `docs/architecture/knowledge-sdk-alignment/contracts/` 与 `docs/acceptance/v2.1-align-wave1/wire-*.json` 核验草案与实测 wire 行为，产出**联合差异清单与最小集成切片候选版**，共同提交用户 / 架构负责人批准冻结。
