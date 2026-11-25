# 团队 A 下一阶段实施计划：统一架构约束下的 Knowledge SDK 演进与协同交付

> 文档路径：`docs/architecture/knowledge-sdk-alignment/04_TEAM_A_NEXT_STAGE_EXECUTION_PLAN.md`
> 制定团队：团队 A（Knowledge SDK 开发团队）
> 依据基线：`knowledge-sdk@feat/q3-phase2-rerank-eval (d153295)` / `main (b953c99)` / `v2.0.0`；前置产出 `00_CURRENT_STATE_AUDIT.md`、`01_OPENBOT_REQUIREMENTS_MAPPING.md`、`02_DOMAIN_MODEL_ALIGNMENT.md`、`03_DOMAIN_CONTRACTS.md`
> 生效日期：2026 年 11 月 24 日
> 适用范围：作为对原有 Q3 研发计划的**正式补充指令与重排执行方案**，立即生效；涉及 Layer 2 与跨仓冻结项严格遵守“评审签认后再落地”的门禁原则

---

## 一、补充指令生效声明与原有任务四类处置

### 1.1 团队 A 执行准则（立即生效）

团队 A 继续作为 `knowledge-sdk` 的主要研发团队，不推翻已有 Q1–Q3 核心成果，而是在现有计划之上正式叠加 **OpenBot 与 Knowledge SDK 统一架构约束**，完成三项核心视角切换：

1. **目标切换**：不再仅以 SDK 自身功能数量作为完成标准，每一项新增或改动能力必须通过三问检验——OpenBot 能否通过正式 API 调用、是否完整覆盖现有业务、是否严格遵守统一权限与证据语义。
2. **验收标准切换**：将 OpenBot 现有业务强依赖但 SDK 缺失的能力（`get_kb`、`update_kb`、`archive_kb`、`list_kb_members`、`revoke_kb_member`、`list_document_versions`、安全版本回滚、回收站筛选与受控硬删、异步 `IngestionJob`、标准 JSON `/v2` API）正式纳入 SDK **M2（Integration Ready）** 必过验收门槛。
3. **节奏切换**：先将通用 **Knowledge Core** 打磨至可集成生产级，主动降级暂缓 Ontology、完整知识图谱（原 Q3-M3 `EvidenceGraph`）与创新药垂类试点（原 Q3-M4 `pack-pharma`）；不等 SDK 全部功能完结即并行支持团队 B 的 Adapter 开发；未经批准绝不执行生产迁移或不可逆破坏性变更。

### 1.2 既有任务与需求四类处置清单

| 任务类型 | 处理方式 | 对应模块与具体任务 | 门禁说明 |
|---|---|---|---|
| **A 类：符合新架构** | **不等待 M1，继续开发收尾** | 解析与切块鲁棒性（`ingestion/parsers/`、`chunkers/`）、Embedding 与双引擎索引优化、Hybrid Retrieval 与 Reranker 延迟优化、幂等与任务重试底座、`EvidenceAnchor` / `EvidencePack` 回归、容器化与 `/metrics` 监控、Q3-M2（`d153295`）独立验收与 `pyproject.toml` 版本号收口 | 不涉及跨仓契约冲突，保持零运行时强依赖与 115 条黄金用例全绿 |
| **B 类：需要契约调整** | **先分析/原型，M1 冻结后落地** | Identity（`issuer`/`actor_type`/`tenant_id`）、Tenant 与个人空间归属策略、Authorization（`User ∩ Agent` 与 `AgentProfile`）、Asset 多类型与回收站、Version 双标识（`version` + `version_id`）与安全回滚、Evidence 双轨 URI 映射、异步 `IngestionJob`、标准 JSON `/v2/*` HTTP API 与错误码信封 | M1 签认前仅做方案细化、原型与 OpenAPI 草案，**禁止单方锁定不可逆 Schema 或破坏 `/v1/*`** |
| **C 类：暂不影响集成** | **明确降级至 P3（M2 后启动）** | 原 Q3-M3 `EvidenceGraph` / 完整知识图谱与复杂图谱查询、高级 Ontology 建模、原 Q3-M4 `pack-pharma` 创新药垂类包、非 OpenBot 集成急需的第三方专业连接器 | 仅在 `Document.domain_metadata` 与协议层保留扩展槽位，不抢占 M1–M2 核心人力 |
| **D 类：与新架构冲突** | **立即停止按旧方案扩展** | 任何基于可变 `email` 的成员/ACL 授权逻辑、允许 Agent 绑定绕过人类用户 ACL 的快捷放行（如 `canReadViaRobotBinding`）、在 SDK 内硬编码业务租户别名、继续以 Python 专属 `__type__` 序列化新增面向跨语言调用的新接口、在 OpenBot 与 SDK 之间复制第二套知识资产权威库 | 设为代码审查与契约测试一票否决红线 |

---

## 二、三个并行工作流与可执行工单拆解

团队 A 将下一阶段研发拆分为 **工作流 A、工作流 B、工作流 C** 三条并行主线，确保 M1 评审期间开发不停摆、M1 冻结后快速冲刺 M2，同时持续为团队 B 输送可联调资产。

### 2.1 工作流 A：SDK 基础能力收尾（即刻推进，不阻塞于 M1）

| 编号 | 工作项 | 涉及源码/目录 | 交付物与完成标准 |
|---|---|---|---|
| **WA-1** | Q3-M2 基线收口与版本元信息对齐 | `feat/q3-phase2-rerank-eval@d153295`、`pyproject.toml` | 配合完成 Q3-M2 独立复核与基线合入规划；核对并规划 `pyproject.toml` 版本号（当前滞留 `1.2.0` vs Git 标签 `v2.0.0`）与发布策略 |
| **WA-2** | 摄取解析、切块与双引擎索引加固 | `src/knowledge_sdk/ingestion/`、`storage/postgres_store.py`、`retrieval/adapters/pgvector_index.py` | 补齐大文档/多栏 PDF/表格解析边界测试；验证 PostgreSQL 连接池与 `pgvector` 在多租户并发写入与重索引下的延迟与锁竞争表现 |
| **WA-3** | Hybrid Retrieval 与 Reranker 性能治理 | `src/knowledge_sdk/retrieval/hybrid.py`、`rerank.py`、`calibration.py` | 针对 Q3-M2 实测“候选重排路径延迟显著上升”的问题，完成 `rerank_top_k` 预算调优、特征缓存与延迟基线报告，同时不损 115 条黄金基准与 24/24 拒答精度 |
| **WA-4** | 幂等性、任务状态与失败重试底座 | `storage/sqlite_store.py`、`postgres_store.py`、`outbox`、`pending_indexes` | 统一抽象事务性任务状态机与 `idempotency_key` 幂等去重原语，为工作流 B 的 `IngestionJob` 和连接器同步提供零外部 MQ 依赖的可靠底座 |
| **WA-5** | Evidence、Citation 与三端（HTTP/Python/MCP）回归 | `contracts/anchors.py`、`packs.py`、`mcp/tools.py`、`client/` | 固化 `EvidenceAnchor` 重锚、`MaterialReceipt` 防篡改、`EvidencePack` RO-Crate 导出及 4 个 MCP 工具的双引擎一致性回归套件 |
| **WA-6** | 独立部署、可观测性与生命周期集成测试 | 新增 `deploy/`（`Dockerfile`、示例配置）、`server/app.py` | 提供标准容器构建文件、`/v1/health` 与就绪探针、结构化 JSON 日志（含 `request_id`/`tenant_id`）、Prometheus `/metrics` 指标（无正文/密钥泄漏）及全生命周期端到端测试 |

### 2.2 工作流 B：统一架构调整与 OpenBot 缺失能力补齐

工作流 B 严格按 **M1 冻结门禁** 分两步执行（冻结前完成评审准备与 Layer-1 无冲突设计，冻结后集中交付 Layer-1 + Layer-2 实现）：

| 编号 | 优先级 | 工作项 | 契约依据 | 关键实现与兼容约束 |
|---|---|---|---|---|
| **WB-1** | **P0** | 六项跨仓关键决策联合评审与契约冻结 | `03_DOMAIN_CONTRACTS.md`（C-01 至 C-09） | 联合团队 B 与架构 owner 正式签认 6 项核心决策（Agent 权限交集、稳定 `user_id` 主键、个人空间租户策略、双标识版本模型、HTTP `/v2/*` 演进策略、基线合入顺序），产出冻结版 `02`/`03` 契约 |
| **WB-2** | **P0** | Identity、Tenant 与 Authorization 对齐 | C-01、C-02 | `Actor` 兼容扩展 `issuer`、`actor_type`（`human`/`agent`/`service`）、`tenant_id`（兼容映射 `org_id` 与 PG `FORCE RLS`）；固化 `User ∩ Agent` 权限交集与 `AgentProfile.allowed_kb_ids`；统一 `POLICY_GENERATION_STALE` / `IDENTITY_REVOKED` 错误语义；彻底杜绝邮箱键与绕权路径 |
| **WB-3** | **P1** | KB 空间与成员管理能力补齐 | C-02 | 新增 `get_kb`、`update_kb`（含 `description`/`tags`/`metadata`/`visibility`/`governance_tier` 及审计日志）、`archive_kb`、`restore_kb`、`list_kb_members`、`revoke_kb_member`；不引入 OpenBot 私有 `robotIds` 字段 |
| **WB-4** | **P1** | Asset、Version、回收站与受控硬删 | C-03、C-04 | `Document` 兼容扩展 `asset_type`、`source_kind`、`source_ref`、`tags`、`domain_metadata`；版本层保留整数 `version` 主序并增加不可变 `version_id` 与 `version_label`；新增 `list_document_versions`、`diff_document_versions`、append-only `rollback_document`、`list_documents(archived_only=True)` 及受控 `purge_document`（Admin 鉴权 + 冻结证据包冲突保护 + Tombstone + 审计 + 向量/Blob 清理） |
| **WB-5** | **P1** | 异步 `IngestionJob` 完整生命周期 | C-07 | 落盘 `ingestion_jobs` 表（Schema 迁移含可回滚验证），实现 `create_ingestion_job` / `get_ingestion_job` / `list_ingestion_jobs` / `retry_ingestion_job` / `cancel_ingestion_job`，支持 `idempotency_key` 与 `queued -> parsing -> chunking -> indexing -> completed | failed | cancelled` 状态流转；保留既有同步 `ingest()` 100% 兼容 |
| **WB-6** | **P1** | Evidence 双轨兼容与校准检索增强 | C-05、C-06 | `SearchHit` 统一透出 `kb_id`、`version_id`、`raw_score`、`rerank_score`、`calibrated_score`（`[0,1]` 联邦标准分）与 `score_breakdown`；确保 `canonical_uri`（`kb://`）与完整结构化坐标可供 OpenBot Adapter 无损生成/解析过渡期 `ku://`；补齐连接器 `plan_sync` / `commit_sync` 两阶段接口（C-08） |
| **WB-7** | **P1** | 跨语言标准 JSON `/v2/*` API 与错误信封 | C-09 | 在完整保留 `/v1/*`（62 个端点零破坏）的前提下，新增 RESTful `/v2/*` 纯 JSON 端点（去除 `__type__` 标记）、自动导出 OpenAPI 3.1 规范、统一错误响应信封（稳定 `error.code` + `retryable` + `request_id`），复用 `LocalKnowledgeClient` 同一内核 |
| **WB-8** | **P1** | HTTP / Python / MCP 三端权限一致性验证 | C-01、C-09 | 建立跨协议一致性矩阵测试：同一批 `(Actor, Agent, Purpose, DocumentACL, Redaction, MidTaskRevocation)` 用例在 `LocalKnowledgeClient`、HTTP `/v1`、HTTP `/v2`、MCP 4 工具下返回完全一致的放行/拒绝/脱敏/撤权语义 |

### 2.3 工作流 C：团队 B（OpenBot）并行集成支持（持续同步推进）

团队 B 无需等待 M2 完工即可基于契约草案和模拟靶场并行开发 OpenBot `KnowledgeSdkAdapter`，团队 A 按三波次交付支撑包：

| 编号 | 交付窗口 | 面向团队 B 的具体支持产物 | 目标 |
|---|---|---|---|
| **WC-1** | **M1 评审同期（立即启动）** | `OpenAPI 3.1` `/v2` 规范草案、TypeScript DTO 与错误码枚举定义、`Identity / Tenant / Agent` 鉴权头与签名示例、`kb:// <-> ku://` 双向映射参考实现 | 让团队 B 立即启动 `KnowledgeSdkAdapter` 接口编码，零等待阻塞 |
| **WC-2** | **M1 冻结后 1 周内** | 契约测试夹具包（Contract Test Fixtures）：覆盖 `User ∩ Agent` 交集、禁止 `canReadViaRobotBinding` 绕权、邮箱迁移至稳定 `user_id`、租户规范化、双轨 URI 互转、错误码处理 | 双方各自在 CI 中独立跑通同一套契约夹具，提前暴露接口偏差 |
| **WC-3** | **M2 交付同期** | 可一键拉起的 `knowledge-sdk` 本地/CI 联调容器镜像（SQLite + PostgreSQL 双模式）与端到端联调清单 | 配合团队 B 验证 6 条 OpenBot 典型业务流（空间与成员、上传与异步向量化、版本对比与回滚、回收站与硬删、Agent 检索与引用校验、连接器 Plan/Commit 与 Tombstone 撤权） |
| **WC-4** | **M3–M4 阶段** | 影子双写/双读一致性校验工具与权限越权零容忍对比脚本 | 协助团队 B 在生产切流前完成存量数据校验、检索质量对比与一键回滚演练 |

---

## 三、开发优先级总表（P0 至 P3）

| 优先级 | 具体工作项 | 对应工作流 | 核心目标 | M1 冻结前允许动作 |
|---|---|---|---|---|
| **P0** | 六项跨仓关键决策联合评审（C-01 至 C-09） | WB-1、WC-1 | 冻结跨仓核心领域契约与安全红线 | 立即主导评审、输出 OpenAPI/TS DTO 草案 |
| **P0** | Identity、Tenant、Authorization 对齐 | WB-2、WC-2 | 消除跨系统身份主键与 Agent 越权冲突 | 编写兼容方案与反例安全测试，不改破坏性表结构 |
| **P1** | Asset、Version、Evidence 统一建模 | WB-4、WB-6 | 统一知识数据模型与双轨证据语义 | 评审确认后执行无损迁移与双引擎实现 |
| **P1** | SDK 缺失的 KB 管理、成员管理、回收站与受控硬删 | WB-3、WB-4 | 完整承接 OpenBot 现有知识管理业务 | 可先行推进不冲突的接口设计与单元测试原型 |
| **P1** | 异步 `IngestionJob` 与幂等重试 | WA-4、WB-5 | 完整支撑大文件/批量/Web 摄取生命周期 | 立即打磨底层任务状态与幂等原语（WA-4） |
| **P1** | 标准 JSON `/v2/*` API 与错误信封 | WB-7、WC-1 | 面向 OpenBot TypeScript Adapter 的稳定跨语言契约 | 立即产出 OpenAPI 3.1 草案供团队 B 审阅 |
| **P1** | HTTP、Python、MCP 三端权限一致性 | WA-5、WB-8 | 保证多入口唯一权威安全边界 | 立即补齐既有 `/v1` + Python + MCP 一致性测试 |
| **P2** | 基础能力收尾、性能压测、容器部署与监控 | WA-1 至 WA-6、WC-3 | 达到 **M2 SDK Integration Ready** | 立即并行推进（解析/重排延迟/部署/监控） |
| **P3** | Ontology、完整 Knowledge Graph、创新药专业扩展（`pack-pharma`） | 后续阶段 | M2 达成后再推进高阶垂类领域能力 | 仅保留 `domain_metadata` 与协议扩展槽，暂不投入主干开发 |

---

## 四、M1 至 M5 里程碑责任分工与退出验收标准

| 里程碑 | 团队 A 角色 | 核心交付范围 | 量化退出验收门禁（Definition of Done） |
|---|---|---|---|
| **M1 统一契约冻结** | **A 与 B 联合主责** | 完成 C-01 至 C-09 联合评审与 6 项阻断决策拍板，冻结 OpenAPI `/v2` 规范草案与契约测试夹具 | 1. 团队 A、团队 B、架构 owner 书面签认 `02`/`03` 契约文档；<br>2. 明确废除 `canReadViaRobotBinding` 绕权与邮箱主键的迁移路径；<br>3. 交付团队 B 可用的 OpenAPI 3.1 + TS DTO + 契约夹具包 |
| **M2 SDK Integration Ready** | **团队 A 主责** | 完成工作流 A 全部收尾项 + 工作流 B 全部 P0/P1 对齐项（不含 P3 Ontology/图谱/药研扩展） | 1. OpenBot 必需能力 100% 落地且双引擎（SQLite + PostgreSQL+pgvector+RLS）测试全绿：`get_kb`/`update_kb`/`archive_kb`/`list_kb_members`/`revoke_kb_member`/`list_document_versions`/安全回滚/回收站/受控硬删/异步 `IngestionJob`/标准 JSON `/v2/*`；<br>2. 存量 `/v1/*` 62 端点与 **115/115 黄金基准零退化**，并新增对齐与权限越权回归组（全绿）；<br>3. HTTP `/v1`、HTTP `/v2`、Python SDK、MCP 权限与脱敏 100% 一致；<br>4. 零运行时强依赖保持不变，容器镜像、健康检查、`/metrics` 与 OpenAPI 文档就绪；<br>5. 团队 B 基于 SDK 镜像跑通全部契约测试 |
| **M3 OpenBot Adapter 闭环** | **A 接口支持，B 主责** | 团队 B 完成 `KnowledgeSdkAdapter` 并接入 OpenBot Gateway；团队 A 响应接口差异与性能/边界缺陷 | 1. OpenBot 6 条典型知识业务流在非生产环境通过 SDK 闭环运行；<br>2. 存量 `ku://` 引用与新 `kb://` 引用可无损解析和校验；<br>3. 越权回归测试（含历史 `robotIds` 与改邮箱场景）0 泄漏 |
| **M4 生产迁移准备** | **A 与 B 共同负责** | 影子双写/双读比对、存量数据与邮箱成员 -> 稳定 `user_id` 迁移工具、可回滚演练、DR 与压测报告 | 1. 影子比对一致性与检索延迟达标；<br>2. 迁移脚本经过演练验证并附经批准的一键回滚方案；<br>3. 产出准生产评审包并提交正式变更审批（未获批不执行生产写入） |
| **M5 SDK 唯一知识权威** | **双方实施，须正式批准** | 按租户分批灰度切换读写权威源至 Knowledge SDK，退役 OpenBot 本地重复存储与旧权限旁路 | 1. 生产灰度零越权、零数据丢失、可观测指标稳定；<br>2. 归档 `FINAL_ALIGNMENT_REPORT.md` 完成收官 |

---

## 五、不可逾越的工程红线与本周立即可启动动作

### 5.1 五条强制工程红线

1. **零存量破坏**：严禁删除现有 `/v1/*` 接口、严禁破坏现有 115 条黄金用例、严禁在 Schema 升级中破坏历史数据可读性。
2. **零未经批准的生产/破坏性操作**：任何生产数据迁移、生产检索切换、不可回滚 Schema 变更、物理清空历史资产，均须经过明确批准并附可验证回滚脚本。
3. **零核心边界污染**：严禁将 OpenBot 私有逻辑（`bases.json`、租户别名映射、邮件发送、Feed/推荐、UI 状态）写入 `knowledge-sdk`；严禁破坏 `pyproject.toml [project.dependencies] = []`。
4. **零安全妥协**：坚持“稳定 `user_id` 为唯一授权键”与“`Effective = User ∩ Agent` 权限交集”，所有权限与脱敏过滤先于排序和重排执行。
5. **诚实汇报纪律**：每个子里程碑汇报必须附实测代码路径、测试命令与真实通过/跳过计数，明确区分“已实测完成”与“待评审/待验证”。

### 5.2 本周立即启动清单（无需等待 M1 冻结即可并行执行）

1. **发起 M1 联合评审会（WB-1）**：将 `00`–`03` 四份文档与本计划同步给团队 B 与架构 owner，聚焦拍板 6 项核心冻结决策。
2. **产出 `/v2/*` OpenAPI 3.1 草案与 TypeScript DTO 包（WC-1）**：率先交付给团队 B 评审接口字段与错误码，缩短双方并行等待。
3. **推进 Q3-M2（`d153295`）复核收口与 Reranker 延迟剖析（WA-1、WA-3）**：查明候选路径延迟瓶颈并准备低延迟基线方案，同步核对 `pyproject.toml` 版本元信息。
4. **补齐三端权限一致性回归基线（WA-5）**：在现有 `LocalKnowledgeClient`、HTTP `/v1` 与 MCP 工具间建立自动化同用例权限断言套件，为后续叠加 `/v2` 做铺垫。
5. **落地通用任务幂等与容器化部署脚手架（WA-4、WA-6）**：完成 `idempotency_key` 抽象设计、`Dockerfile` 与 `/metrics` 指标埋点方案。
6. **正式冻结 C/D 类低优与冲突项**：暂停原 Q3-M3 `EvidenceGraph` 与 Q3-M4 `pack-pharma` 开发排期，集中团队 A 全部主干带宽攻坚 M1 冻结与 M2 Integration Ready。
