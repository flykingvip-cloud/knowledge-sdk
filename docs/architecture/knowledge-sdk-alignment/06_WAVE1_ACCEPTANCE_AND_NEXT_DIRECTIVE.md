# Align-Wave1 独立验收结论、回滚裁定与下一阶段指令书（Align-Wave1.5）

> 文档路径：`docs/architecture/knowledge-sdk-alignment/06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md`
> 签发角色：架构治理与验收负责人（团队 A 统筹）
> 执行对象：Knowledge SDK 实施工程团队（Execution Agent）
> 验收对象：`feat/align-wave1-core-compat`（Commit `60b6436ed9fccb4b49ae32e30f1664412e505888`）
> 下一波次目标分支：`feat/align-wave1p5-m1-readiness`（基于 `60b6436` 切出；仍不动 `main` 与 `v2.0.0`）
> 签发日期：2026 年 11 月 24 日

---

## 一、Align-Wave1 独立验收结论与回滚语义正式裁定

### 1.1 独立复核证据摘要

验收方已独立检出 `feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888` 并逐项复核源码、远端 refs、契约校验脚本与纯标准库测试套件：

| 验收维度 | 独立核验结果 | 判定 |
|---|---|---|
| 纯标准库门禁（本机独立实跑） | `python3 -S -W error::ResourceWarning`：**942 tests，642 passed，300 optional skips，0 failed，0 ResourceWarning**（57.70s） | **通过** |
| 四作业 CI 与双引擎门禁 | GitHub Actions Run `45560707520` 全绿；全依赖 939 通过、3 项在线 Qdrant 跳过；SQLite 与 PostgreSQL+pgvector+RLS 双引擎既有 **115/115 黄金基准零修改 100% 通过**；真实隔离非 root Docker 镜像构建与就绪探针通过 | **通过** |
| 契约资产自检（本机独立实跑） | `validate_assets.py` 返回 `rc=0`：`23 paths`、`28 schemas`、`6 fixtures`、`37 negative probes`、`runtime_v2_implemented=false`、`m1_joint_freeze=PENDING` | **通过** |
| 架构与仓库保护红线 | 远端 `main`（`b953c99`）与注释标签 `v2.0.0`（`4afc1d7`）零变更；`pyproject.toml [project.dependencies] == []`；Schema 严格保持 `v5`（零 DDL 变动）；`server/app.py` 无运行时 `/v2/*` 路由（仅有既有 `/scim/v2/`） | **通过** |
| 延迟治理实测 | 增强检索 P50：SQLite `17.840→16.969ms`（-4.89%），PG `146.320→80.210ms`（-45.18%），固定离线集质量指标 100% 保持；普通 RRF P50 轻微变慢（SQLite `+0.043ms`，PG `+0.478ms`）已诚实披露，列为下步轻度优化项 | **通过（附跟踪项）** |

### 1.2 回滚语义边界正式裁定（解除 Wave1 唯一阻塞）

针对交接报告第四章披露的“Schema v5 `DocumentVersion` 未保存历史任意元数据”这一边界，架构治理方正式裁定如下：

1. **安全与合规元数据永久禁止自动回滚（强制红线）**：`DocumentACL`、`ResourceRights`、`valid_from`/`valid_to`、`archived` 状态及 L2 受控发布门槛属于实时安全边界，内容回滚**绝不允许**恢复历史已被撤销的权限或过期策略。Wave1 保留当前安全元数据的实现完全正确。
2. **批准 Schema v5 下的内容回滚边界**：在 Schema v5（Layer-1）阶段，正式确认 `rollback_document` 的契约语义为 **恢复目标历史版本的 `text` 与 `filename`，保留当前安全及业务元数据**（`rollback_scope = "content_and_filename_only"`），以 append-only 新递增版本落地并写审计日志。严禁在无历史快照时伪造旧业务元数据。
3. **非安全业务元数据快照归属 M1/Wave2 裁决**：是否需要为非安全业务元数据（`title`、`tags`、`Document.metadata`）增加历史快照（如 Schema v6 `document_versions.metadata_snapshot`），纳入 M1 联合评审清单第 7 项，由团队 A、团队 B 与架构 owner 统一拍板。

### 1.3 Align-Wave1 最终验收结论

- **正式结论**：基于上述回滚边界裁定与全部 L1–L5 实证，**Align-Wave1（`feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888`）独立验收通过，正式退出！**
- **继续保持暂停/未变项**：M1 跨仓联合冻结尚未完成，**暂不启动 Align-Wave2**；暂不合并 `main`、不打新标签、不改 `pyproject.toml` 发版版本号、不执行生产迁移；企业与 StratAI 接入继续暂停。

---

## 二、下一步任务部署：Align-Wave1.5（M1 联审收口与团队 B 联调就绪包）

在 M1 跨仓书面冻结签认完成前的窗口期，执行团队立即基于 `feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888` 切出新分支 **`feat/align-wave1p5-m1-readiness`**，推进 **Align-Wave1.5**，确保工程进度零空转、不越过 M1 冻结红线，并为团队 B 扫清联调启动障碍。

### 2.1 本波次范围边界（IN SCOPE / OUT OF SCOPE）

**IN SCOPE（必须完成）**：
- **Task 0（回滚契约显式化收尾）**：按 §1.2 正式裁定，在 `rollback_document` 审计记录、兼容文档及 `/v2` 草案/DTO 中显式声明 `rollback_scope = "content_and_filename_only"` 与安全元数据永不回滚规则。
- **Task 1（M1 联合评审决策包与机检签认清单）**：产出单页化、可直接签认的 `M1_DECISION_PACKAGE.md` 与 `m1-freeze-manifest.json`（覆盖原 6 项决策 + 新增第 7 项业务元数据快照裁决），便于团队 B 与架构 owner 一次性拍板。
- **Task 2（团队 B 5 分钟可跑通联调靶场与 TypeScript 契约工具）**：交付容器/本地双模式 OpenBot 联调靶场脚手架与预置多租户种子数据；补齐 TypeScript `kb:// <-> ku://` 双轨映射参考实现与单测，并在 CI 中加入真实 TypeScript 类型检查（`tsc --noEmit`）与 OpenAPI 规范校验。
- **Task 3（普通 RRF 延迟回补与 `archive_kb` Layer-1/2 边界书面确认）**：消除普通 RRF 路径中同一搜索请求内多余的当前主体查询开销（严禁跨请求缓存）；书面明确 `archive_kb`/`restore_kb` 是否需新增物理列（若需加列则严格留待 Wave2）。

**OUT OF SCOPE（严禁越界）**：
- M1 签认前**严禁执行 Schema v5 -> v6 迁移**（零新增表、零新增物理列、Schema 保持 `v5`）。
- **严禁上线运行时 `/v2/*` 路由**、严禁实现 `purge_document` 物理硬删或 `IngestionJob` 物理作业表。
- **严禁修改既有 115 条黄金用例**、严禁破坏既有 `/v1/*` 70 个操作签名、严禁修改 `pyproject.toml [project.dependencies] = []`。
- **严禁开发 P3 领域能力**（Ontology、EvidenceGraph、`pack-pharma`）。
- **严禁改动 `main`（`b953c99`）、`v2.0.0` 标签或 `feat/align-wave1-core-compat` 历史提交，严禁执行生产迁移或发布部署**。

---

## 三、Align-Wave1.5 分项工程任务书

### Task 0：回滚语义显式化（Schema v5 零 DDL 改动）

1. 在 `src/knowledge_sdk/client/compat.py` 的 `rollback_document` 审计事件载荷中显式写入 `rollback_scope: "content_and_filename_only"` 与 `security_metadata_preserved: true`，不得修改 `DocumentVersion` 返回字段或 Schema v5 表结构。
2. 同步更新 `docs/agent-runtime-compat.md`、`docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml` 及 `openbot-adapter-dto.d.ts` 中对回滚语义的说明，明确标注安全元数据永不回滚。
3. 补充双引擎测试断言：验证 `rollback_document` 审计记录包含显式 `rollback_scope`，且旧撤销的 ACL/Rights/过期有效性绝不会被复活。

### Task 1：M1 联合评审决策包（供团队 B 与架构 Owner 拍板）

在 `docs/architecture/knowledge-sdk-alignment/` 下新增：

1. `M1_DECISION_PACKAGE.md`：将需要联合冻结的 **7 项核心决策** 整理为可直接签署的决策表（每项含：现状冲突证据、候选方案对比、团队 A 推荐项、对 SDK 与 OpenBot 的影响、回滚策略及签认状态）：
   - D1：废除 OpenBot `canReadViaRobotBinding` 绕权，全面执行 `User ∩ Agent` + `AgentProfile.allowed_kb_ids`。
   - D2：成员与 ACL 主键全面收敛至稳定 `user_id`（`issuer + sub`），邮箱仅作 OpenBot 邀请属性。
   - D3：个人空间租户归属策略（方案 A 企业内 `space_type=personal` vs 方案 B 独立 `personal:<user_id>`）。
   - D4：双标识版本模型（保留 `version: int` 主序 + 新增 `version_id: str` 与 `version_label`）。
   - D5：跨语言 HTTP 契约演进路线（方案 A 并行新增标准 JSON `/v2/*` vs 方案 B `/v1/*` 协商头）。
   - D6：基线收口与版本漂移处置（Q3-M2/Wave1 合入策略、`pyproject.toml 1.2.0` 与 `v2.0.0` 标签对齐时机）。
   - D7（新增）：Schema v6 是否在 `document_versions` 增加非安全业务元数据快照 `metadata_snapshot`（安全元数据永久不回滚）。
2. `m1-freeze-manifest.json`：机器可读的 M1 签认清单（7 项决策默认 `"status": "pending_joint_signoff"`，严禁自填已批准），配套校验脚本确保未经签认前 Wave2 门禁保持锁定。

### Task 2：团队 B 联调靶场与 TypeScript 契约工具链

1. **联调靶场（`deploy/openbot-sandbox/`）**：
   - 提供零污染、可一键启停的联调靶场脚本与配置（支持 SQLite 本地快速模式与 PostgreSQL+pgvector 容器模式，复用 Wave1 非 root 安全容器模式，严禁暴露不安全 demo 旁路）。
   - 提供确定性种子脚本 `seed_openbot_sandbox.py`：初始化 2 个租户、3 类空间（个人/团队/企业公开）、含显式 Deny 的文档、多版本文档、归档文档、1 个合法 `AgentProfile` 与 1 个“Agent 绑定了私密库但人类用户无权”的反例场景，输出联调用凭据配置说明（仅限本地测试密钥，绝不硬编码生产密钥）。
2. **TypeScript 参考映射与 CI 实检**：
   - 在 `docs/architecture/knowledge-sdk-alignment/contracts/` 下新增零外部依赖的 TypeScript 参考模块 `uri-mapping.ts`（实现 `kb:// <-> ku://` 双向确定性映射及非法 URI 拒绝）与配套测试 `uri-mapping.test.ts`。
   - 在 CI 工作流中新增轻量契约检验步骤：真实运行 TypeScript 类型检查（验证 `openbot-adapter-dto.d.ts` 与 `uri-mapping.ts` 无类型错误）与 OpenAPI 3.1 结构校验（如安装可选标准校验器或固化严格 JSON Schema 校验），并归档实跑日志。

### Task 3：普通 RRF 延迟回补与空间归档边界确认

1. **普通 RRF 路径性能回补**：
   - 核查 Wave1 中普通 RRF 路径 P50 轻微变慢（SQLite `1.873→1.916ms`、PG `9.628→10.106ms`）是否源于单次 `search()` 请求内重复读取同一 `IdentityPrincipal`。
   - 仅允许**单次请求作用域内**复用已验证的当前主体快照（严禁跨请求、跨租户或跨 `policy_generation` 缓存），重新运行同物理快照配对基准，记录优化前后 SQLite/PG 普通 RRF 与增强检索 P50/P95 实测对比。
2. **`archive_kb` / `restore_kb` Schema 影响书面确认**：
   - 核查当前 `knowledge_bases` 表在 Schema v5 下是否无 `status`/`archived` 列；若是，则在 `M1_DECISION_PACKAGE.md` 与交接报告中明确将其列为 Wave2（Schema v6）必需字段，本步不强行塞入变通字段。

---

## 四、Align-Wave1.5 验收门禁（L1 至 L5）

| 层级 | 硬性验收标准 |
|---|---|
| **L1** | `python3 -S -W error::ResourceWarning` 全量测试 0 失败、0 `ResourceWarning`；`pyproject.toml [project.dependencies] == []`；Schema 保持 `v5` 零 DDL 变更 |
| **L2** | SQLite + 真实 PostgreSQL+pgvector+RLS 双引擎全量通过；GitHub Actions 全作业全绿；既有 **115/115 黄金用例零修改 100% 通过** |
| **L3** | 联调靶场种子脚本 + 端到端冒烟验证日志（覆盖 `User ∩ Agent` 反例拒绝与 `/v1/ready`）；普通 RRF + 增强检索同快照延迟配对 JSON |
| **L4** | CI 实跑 TypeScript 契约编译/单测通过（`openbot-adapter-dto.d.ts` + `uri-mapping.ts`）+ `validate_assets.py` + `m1-freeze-manifest.json` 校验通过；若无 UI 变更则明确声明 |
| **L5** | 归档 `docs/acceptance/v2.1-align-wave1p5/ALIGN_WAVE1P5_HANDOFF_REPORT.md`；推送至 `feat/align-wave1p5-m1-readiness`；不动 `main`、`v2.0.0`、不自批 M1、不启动 Wave2 |

---

## 五、Wave2 解锁条件预告（待 M1 签认后正式下发）

一旦团队 A、团队 B 与架构 owner 基于 `M1_DECISION_PACKAGE.md` 完成 7 项决策书面签认，验收方将立即下发 **Align-Wave2（M2 Integration Ready 冲刺指令书）**，统一推进：
- Schema v5 -> v6 可回滚双引擎迁移（`version_id`/`version_label`、`knowledge_bases.status`、`documents.asset_type`/`source_kind`/`source_ref`/`domain_metadata`、`ingestion_jobs` 及经 M1 裁定的 `metadata_snapshot`）；
- 运行时标准 JSON `/v2/*` API 与稳定错误信封（同时 100% 保留 `/v1/*` 兼容）；
- 异步 `IngestionJob` 完整状态机与 `archive_kb`/`restore_kb`/受控 `purge_document`；
- 面向 M2 Integration Ready 的全套双引擎 + 三端权限 + OpenBot Adapter 联调验收。
