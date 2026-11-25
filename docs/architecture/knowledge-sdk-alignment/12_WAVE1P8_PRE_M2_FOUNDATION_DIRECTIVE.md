# Align-Wave1.8 执行指令书：M1 冻结前并行基础夯实与 M2 零 DDL 预备波次

> 文档编号：`12_WAVE1P8_PRE_M2_FOUNDATION_DIRECTIVE.md`
> 归档路径：`docs/architecture/knowledge-sdk-alignment/12_WAVE1P8_PRE_M2_FOUNDATION_DIRECTIVE.md`
> 发布日期：2026-11-25
> 签发方：架构与治理控制面（团队 A 控制面）
> 执行方：团队 A 工程执行代理（`knowledge-sdk` Execution Agent）
> 前置基线：`feat/align-wave1p5-m1-readiness@07f5d39f05ef4c7952be48b83025b9c86ea2458e`（已通过团队 A 独立终验并移交团队 B 复算）
> 治理状态：M1 仍处于 `Pending`（`freeze_authorized: false`）；本波次严格限定在 **A 类无冲突基础夯实 + CI 治本 + M2 零 Schema 变动内部预备**，绝不越过 M1 冻结红线

---

## 一、阶段定位、分支策略与硬性红线

### 1.1 为什么现在启动 Align-Wave1.8（而不是干等 M1 冻结，也不提前抢跑 Wave2）

截至 `07f5d39f05ef4c7952be48b83025b9c86ea2458e`，团队 A 已完成 Align-Wave1.5b 全部契约收口、28 项哈希清单与 303 项 TypeScript 断言验证，并正式移交团队 B（`codex-knowledge`）进行独立复算与 M1 冻结候选包拼装。在团队 B 完成独立验证并由用户/架构负责人书面签认六项待决裁决前，**M1 尚未冻结**。

遵循《04 团队 A 下一阶段实施计划》确立的“并行推进不空转、红线绝对不抢跑”原则，团队 A 立即切入 **Align-Wave1.8（M1 冻结前并行基础夯实与 M2 零 DDL 预备波次）**：

1. **彻底消除 Run 45589941009 暴露的 30 分钟 CI 超时悬崖**：在不放宽任何门禁、不依赖追加预算的前提下，通过工作流并行拆分将单作业峰值耗时从 ~34 分钟压降至 15 分钟以内，为后续 Wave2 扫清交付阻塞。
2. **集中消化 WA-2 / WA-4 / WA-5 / WA-6 全部零冲突高价值债务**：夯实解析切块、双引擎多租户并发、Python/HTTP/MCP 三端权限撤权一致性、结构化零泄漏可观测性与全生命周期 E2E。
3. **以零 Schema 变动方式为 M2（Wave2）提前铺轨**：将 `Idempotency-Key` 指纹状态机与 `IngestionJob` 异步作业状态机沉淀为纯标准库契约/领域原语，一旦 M1 正式书面冻结，Wave2 仅需挂载 Schema v6 持久化适配器与 `/v2/*` 薄路由即可高速达标。

### 1.2 绝对分支纪律（严禁污染 M1 待审基线）

**核心命令**：必须从 `07f5d39f05ef4c7952be48b83025b9c86ea2458e` 切出**全新独立分支** **`feat/align-wave1p8-pre-m2-foundation`** 开展全部工作。

| 引用 / 分支 | 基准 SHA（40 位） | Wave1.8 处置纪律 |
|---|---|---|
| `feat/align-wave1p8-pre-m2-foundation` | 从 `07f5d39f05ef4c7952be48b83025b9c86ea2458e` 新建 | **唯一允许推送提交的活跃开发分支** |
| `feat/align-wave1p5-m1-readiness` | `07f5d39f05ef4c7952be48b83025b9c86ea2458e` | **严禁追加任何提交或 force-push**，确保团队 B 复算的 SHA 与 28 项契约哈希纹丝不动 |
| `main` | `b953c9922cc1096e0e88455dab6746c01a9d27f9` | 严禁合并、修改或重指 |
| `v2.0.0` | `4afc1d71f9f5583d93c28f3f4380544a4e5fcc46` | 严禁移动或重建标签 |
| `feat/align-wave1-core-compat` | `60b6436ed9fccb4b49ae32e30f1664412e505888` | 历史验收基线，只读不动 |

### 1.3 IN-SCOPE 与 OUT-OF-SCOPE 边界清单

| 维度 | IN-SCOPE（本波次必须交付） | OUT-OF-SCOPE（严禁触碰的 M1 红线） |
|---|---|---|
| CI 工作流 | 仅在 `feat/align-wave1p8-pre-m2-foundation` 拆分 `.github/workflows/tests.yml` 巨型串行作业为并发多作业，保留 100% 既有检查项 | 严禁删减任何单元测试、黄金套件、Docker 沙箱、校验器或 TS 断言；严禁降低 `-W error::ResourceWarning` 严格度 |
| 数据库 Schema | 维持 SQLite / PostgreSQL Schema v5 原封不动；补充双引擎并发/锁竞争/RLS 隔离测试 | **严禁修改任何 DDL 或迁移脚本**（`storage/migrations.py` 保持 0 改动）；严禁提前升 Schema v6 |
| HTTP 运行时 | 夯实既有 `/v1/*` 契约、`/v1/ready` 深度依赖探针、`/metrics` 指标与零泄漏日志；修复客户端响应流关闭隐患 | **严禁实现、挂载或暴露任何 v2 运行时路由**（`/v2/*`，`runtime_v2_implemented` 维持 `false`） |
| M1 契约资产 | 只读引用；允许新增归档文档 `11` 与 `12`（不回写 `m1-freeze-manifest.json`） | **严禁修改 07f5d39f 已固化的 28 项契约资产**（含 `m1-freeze-manifest.json` 与 `M1_DECISION_PACKAGE.md`）；严禁单方面宣称 M1 `Frozen` |
| 领域与依赖 | 纯 Python 标准库新增内部契约状态机原语（`idempotency`、`ingestion_jobs`） | 严禁向 `pyproject.toml` `[project.dependencies]` 新增任何第三方运行时依赖；严禁修改 `tests/benchmark/` 黄金用例源文件 |
| 业务与跨仓 | 仅限 `knowledge-sdk` 仓库 | 严禁启动 P3 范围（`EvidenceGraph`、`pack-pharma`、外部企业/StratAI 切流）；严禁修改 `openbot-vp` 仓库 |

---

## 二、五大工程任务清单

### Task 1：CI 并发拆分治本（彻底消除 30 分钟超时悬崖）

**问题根因**：在 Run `45589941009` 中，`.github/workflows/tests.yml` 的 `http-and-package` 作业把全量 `unittest`（~8.5m）、全量 `pytest`（~8.5m）、SQLite/PostgreSQL 6 组黄金套件（115/75/100，~13m）、契约校验器、TypeScript 303 断言及双 Docker 沙箱探测（~3.5m）全部串行塞入单个 `timeout-minutes: 30` 作业，累计耗时逼近 34 分钟导致在 PG `legacy100` 阶段触发超时取消。

**实施要求（经本指令正式授权修改工作流）**：

1. 将 `.github/workflows/tests.yml` 中过载的串行 `http-and-package` 作业拆分为职责清晰的并发作业（各作业仍维持 `timeout-minutes: 30` 或 `20`，但实际运行耗时均压降至 **15 分钟以内**）：
   - `unit-and-package-suite`：Python 3.9/3.11+（延续既有矩阵策略）执行 `unittest` 全量套件、`pytest` 全量套件、`-W error::ResourceWarning` 校验、wheel 构建与安装自检。
   - `postgres-golden-suite`：启动 PostgreSQL + pgvector 服务容器，独立并发执行 SQLite 与 PostgreSQL 全部黄金基准套件（`115` 完整集、`75` legacy75、`100` legacy100，以及双引擎新增并发与 E2E 测试）。
   - `contracts-ts-and-docker-sandbox`：执行零配置裸跑契约校验器（`validate_alignment_contracts.py`）、锁定依赖的 TypeScript `tsc --noEmit` + 303+ 项契约/向量测试、SQLite 与 PostgreSQL 双模式联调靶场容器冒烟及运行态容器探测。
2. **零门禁削弱核对**：交接报告必须附带“旧 4 作业 -> 新 N 作业”逐步骤映射表，逐项证明原 Run `45573187717` / `45589941009` 中的每一条命令、参数与环境变量均被完整保留、零删减。
3. **无外部 API 预算依赖**：不新增任何需额外付费 runner 或高额 API 轮询的逻辑，使用标准 GitHub-hosted runner 并发执行即可。

### Task 2：WA-2 摄取解析、切块与双引擎多租户并发索引加固

对照《04 团队 A 下一阶段实施计划》工作流 A（WA-2），针对 OpenBot 真实文档摄取场景消除边界脆弱点：

1. **解析与切块鲁棒性加固（`src/knowledge_sdk/ingestion/`）**：
   - 加固 Markdown / CSV / 纯文本解析器与切块器对极端输入的确定性处理：包含超大单段、多级嵌套表格、空文档/纯空白文档、含 Python 29 码点 Unicode 空白及 `U+FEFF` 的文本、混合 CJK/拉丁 NFC 文本、异常截断或超限体积输入（fail-closed 返回明确结构化错误，不产生崩溃或空 chunk 垃圾）。
   - 验证相同输入在 SQLite 与 PostgreSQL+pgvector 下生成的 `chunk_id`、分块边界、规范化文本哈希与 `EvidenceAnchor` 坐标 **100% 逐字段一致**。
2. **双引擎多租户并发写与重建索引隔离测试**：
   - 在 SQLite（WAL / 锁竞争重试）与 PostgreSQL（真实 `FORCE ROW LEVEL SECURITY`）下新增并发多租户测试：多租户同时执行 `ingest` / `update_document` / `rollback_document` / `reindex` / `search`，验证零跨租户数据泄漏、零死锁崩溃、零未关闭游标或 `ResourceWarning`。

### Task 3：WA-4 零 Schema 改动纯契约原语（幂等指纹与异步摄取作业状态机）与客户端资源关闭审计

为保证 M1 冻结后 Wave2 能在数小时内接入持久化层，本任务在**不改动任何 Schema v5 DDL、不暴露 `/v2` 路由**的前提下，先行落地纯标准库、可独立单测的内部领域模块：

1. **幂等请求指纹与状态机原语（建议路径 `src/knowledge_sdk/contracts/idempotency.py`）**：
   - 严格对齐团队 A/B 在 `08`、`09` 确认的 C-07 / C-09 幂等语义：
     - 定义规范化请求指纹计算器（按确定性 JSON 排序序列化 + UTF-8 SHA-256），覆盖 `(tenant_id, method, canonical_path, idempotency_key)` 复合键。
     - 定义纯状态机与存储协议接口（`IdempotencyRecord`、`IdempotencyDecision`：`NEW` / `REPLAY_EXACT` / `CONFLICT_PAYLOAD_MISMATCH` -> 映射 `409 IDEMPOTENCY_CONFLICT` / `IN_PROGRESS` -> 映射 `409` 或可重试状态）及内置线程安全内存实现 `InMemoryIdempotencyStore`（支持 TTL 过期清理）。
2. **异步摄取作业状态机原语（建议路径 `src/knowledge_sdk/contracts/ingestion_jobs.py`）**：
   - 严格对齐 `03_DOMAIN_CONTRACTS.md`（C-07 `IngestionJob`）：
     - 定义状态枚举：`queued`、`parsing`、`chunking`、`indexing`、`completed`、`failed`、`cancelled`。
     - 显式声明合法状态迁移表（例如终态 `completed` / `cancelled` 禁止再次迁移；`failed` 在未超过 `max_attempts` 时仅允许显式重试迁回 `queued`），任何非法迁移 fail-closed 抛出明确领域异常。
     - 定义确定性进度载荷、失败错误载荷与存储协议接口 `IngestionJobStore`，附带纯内存参考实现 `InMemoryIngestionJobStore` 与完整状态机迁移单测（覆盖正常完成、失败重试、取消竞态、非法跃迁拒绝与幂等提交）。
3. **客户端响应流关闭审计（`HttpKnowledgeClient`）**：
   - 专项核查并修补 `HttpKnowledgeClient` 在 `urllib.error.HTTPError` 及网络异常分支下的响应对象关闭路径（确保在 `-W error::ResourceWarning` 下高频错误响应零未关闭 socket 警告），补充专项单测。

### Task 4：WA-5 Python / HTTP `/v1` / MCP 三端权限、证据防篡改与撤权一致性矩阵深化

对照《04 团队 A 下一阶段实施计划》工作流 A（WA-5），消除多入口协议语义漂移风险：

1. 建立统一的跨协议夹具测试矩阵（建议路径 `tests/test_cross_protocol_parity.py`），对同一批夹具同时驱动 **`LocalKnowledgeClient`（Python）**、**HTTP `/v1` 服务**、以及 **MCP 4 个标准工具（`search_evidence`、`verify_citation`、`get_evidence_pack`、`report_evidence_issue`）**，断言三端在以下 8 类高危场景输出语义 100% 一致：
   - 跨租户与跨知识空间隔离（验证绝不出现类似 OpenBot `canReadViaRobotBinding` 的越权旁路）。
   - `AgentProfile` 与 `Actor` 预算交集约束及 `Purpose` 限制。
   - `DocumentACL` 拒绝与脱敏钩子 `RedactionHook` fail-closed 行为。
   - `policy_generation` 过期（陈旧令牌拒绝）。
   - `MidTaskRevocation` 实时任务中撤权与版本快照锁失效。
   - `verify_citation` 对被篡改摘要（`TAMPERED_EXCERPT`）与已归档/已撤权文档的精确裁定。
   - L1 与 L2 受控空间发布/审批/回滚（显式 `content_and_filename_only` 边界，安全元数据永不回滚）后检索与引用的实时一致性。
   - 软删除 / 回收站归档文档不可见，恢复后恢复受 ACL 约束的可见性。

### Task 5：WA-6 准生产可观测性、零泄漏结构化日志、深度探针与双引擎全生命周期 E2E

对照《04 团队 A 下一阶段实施计划》工作流 A（WA-6），将 `/v1` 生产运行态观测与稳定性一次补齐：

1. **零敏感泄漏结构化 JSON 日志**：
   - 审计 HTTP 服务与核心写入/检索路径的结构化日志字段（包含 `request_id`、`tenant_id`、`operation`、`status_code`、`latency_ms`、`error_code` 等）。
   - 新增自动化负向断言测试：捕获完整日志流，严格断言日志中**绝对不出现**文档正文摘录（excerpt/content）、鉴权密钥/HMAC 签名原文、Bearer Token 或用户邮箱/PII 原文。
2. **深度就绪探针与指标加固**：
   - 核查并加固 `/v1/ready`（执行真实存储连通性与 Schema 版本检查，后端不可用或版本不匹配时返回 `503` 非就绪）及 `/metrics`（Prometheus 文本格式输出请求计数、权限拒绝/撤权计数、检索延迟统计，零额外依赖）。
3. **双引擎完整生命周期 E2E 测试**：
   - 编写并在 SQLite 与 PostgreSQL+pgvector 上均实跑通过的完整端到端业务闭环测试：`create_kb` -> 成员授权 -> `ingest` -> `search` -> `verify_citation` -> `update_document`（多版本）-> `rollback_document`（核验审计边界与安全元数据未回滚）-> `archive_document`（回收站不可检索）-> `restore_document` -> `report_evidence_issue` -> `export_evidence_pack` -> 审计链校验 `verify_audit_chain`。

---

## 三、提交规范、文档归档与零退化约束

1. **分支与提交策略**：
   - 基于 `feat/align-wave1p5-m1-readiness@07f5d39f05ef4c7952be48b83025b9c86ea2458e` 新建分支 **`feat/align-wave1p8-pre-m2-foundation`**。
   - 可按 Task 1–5 保持逻辑清晰的原子提交（或在最终推送前整理为干净的 3–5 个语义提交），但**严禁**向 `feat/align-wave1p5-m1-readiness`、`main`、`v2.0.0` 或 `feat/align-wave1-core-compat` 推送任何对象。
2. **文档归档与 28 项契约零扰动原则**：
   - 在 `feat/align-wave1p8-pre-m2-foundation` 上，**严禁修改** `07f5d39f` 已锁定的 28 项 `contract_asset_hashes` 目标文件、`docs/architecture/knowledge-sdk-alignment/contracts/m1-freeze-manifest.json`、`docs/architecture/knowledge-sdk-alignment/M1_DECISION_PACKAGE.md` 及 `00`–`10` 历史文档。
   - 交接报告写入 `docs/acceptance/v2.1-align-wave1p8/ALIGN_WAVE1P8_HANDOFF_REPORT.md`（若控制面下发了 `11`、`12` 原文，可同步归档至 `docs/architecture/knowledge-sdk-alignment/`，但不得改动 `m1-freeze-manifest.json` 哈希集合）。
3. **零退化硬指标**：
   - `pyproject.toml` `[project.dependencies]` 必须保持 `[]`（零第三方核心运行依赖）。
   - `git diff 07f5d39f05ef4c7952be48b83025b9c86ea2458e -- src/knowledge_sdk/storage/migrations.py tests/benchmark docs/architecture/knowledge-sdk-alignment/contracts` 必须**输出为空（0 行变更）**。
   - Python 全量测试在 `-W error::ResourceWarning` 下必须零警告、零失败；普通 RRF 检索质量与安全指标 0 退化。

---

## 四、Align-Wave1.8 退出验收门禁（L1–L5）与交接报告格式

| 层级 | 验收项 | 硬性通过标准 |
|---|---|---|
| L1 边界与零扰动 | 分支、DDL、契约、依赖检查 | 仅修改新分支 `feat/align-wave1p8-pre-m2-foundation`；`migrations.py`、`tests/benchmark`、`contracts/`、`m1-freeze-manifest.json` 相对 `07f5d39f` 为 0 变更；无 `/v2/*` 运行时路由；`[project.dependencies] = []` |
| L2 并发 CI 全绿 | 拆分后 GitHub Actions 工作流 | 新拆分的全作业 CI **100% 绿灯通过**，且每个作业实际执行耗时均 **小于 18 分钟**；逐步骤映射表证明 0 门禁削弱 |
| L3 单元测试与双引擎 | 全量单测、并发测试、三端矩阵、E2E | `unittest` 与 `pytest` 全通过（0 失败，0 `ResourceWarning`）；SQLite 与 PostgreSQL+pgvector 下 115/75/100 黄金套件、多租户并发写测试、Python/HTTP/MCP 三端矩阵及全生命周期 E2E 全绿 |
| L4 纯契约原语与可观测性 | 幂等/作业状态机、零泄漏日志、探针与指标 | `idempotency` 与 `ingestion_jobs` 状态机全分支单测通过；日志负向断言确认 0 正文/密钥/PII 泄漏；`/v1/ready` 故障返回 `503`、`/metrics` 指标实测可读 |
| L5 交接报告 | 审计级证据包 | 提交 `docs/acceptance/v2.1-align-wave1p8/ALIGN_WAVE1P8_HANDOFF_REPORT.md`，包含完整 40 位 SHA、相对 `07f5d39f` 差异清单、CI 拆分前后耗时对比表与精确 SHA 对应全绿 CI 链接、全部新增测试清单与零扰动校验命令原文 |

### 交接报告必填章节模板

1. **分支与基线声明**：精确 40 位 HEAD SHA、父基线 `07f5d39f05ef4c7952be48b83025b9c86ea2458e`、`feat/align-wave1p5-m1-readiness` / `main` / `v2.0.0` 未改动校验输出。
2. **CI 并发拆分对照与耗时实证**：旧作业与新作业步骤一一映射表、新全绿 CI Run 链接及各作业实测耗时。
3. **五大任务交付与零扰动证明**：Task 1–5 改动文件清单、`git diff 07f5d39f -- migrations.py tests/benchmark contracts/` 为空证明。
4. **双引擎测试、三端一致性与零泄漏可观测性实证**：SQLite/PG 测试计数、`ResourceWarning` 零告警证明、日志脱敏负向断言结果、`/v1/ready` 与 `/metrics` 实测摘要。
5. **M1 治理声明与风险披露**：明确声明 M1 仍待联合冻结、未启动 `/v2` 运行时或 Schema v6，并如实披露任何未决问题。

---

## 五、M1 冻结后的无缝衔接路线图（Wave1.8 -> Wave2）

当团队 B 完成 `07f5d39f` 复算且用户/架构负责人正式书面签认 M1 六项待决项后，团队 A 将以最小成本从 Wave1.8 平滑切入 **Align-Wave2（M2 Integration Ready）**：

1. **高速 CI 即刻护航**：Wave1.8 拆分后的并发 CI 直接承接 Wave2 新增的 Schema v6 与 `/v2/*` 契约测试，不再受 30 分钟超时阻塞。
2. **零 DDL 原语直接挂库**：Wave1.8 交付的 `IdempotencyStore` 与 `IngestionJobStore` 协议及状态机逻辑零重写，在 Wave2 中直接实现 SQLite/PostgreSQL Schema v6 表适配器即可上线真实持久化幂等与异步摄取。
3. **三端与双引擎基线就绪**：Wave1.8 固化的双引擎并发压测、零泄漏结构化日志与 Python/HTTP/MCP 一致性矩阵将成为 Wave2 `/v2/*` 最小切片（`/v2/spaces`、`/v2/assets`、`/v2/retrieval:search`、`/v2/citations:verify` 等）的默认回归防线，直接加速 M2/M3 跨仓联调。
