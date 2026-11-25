# OpenBot × Knowledge SDK 双团队前置并行执行指令（Pre-v7 非破坏性准备与补证波次）

> **指令状态**：基于《项目负责人建议裁决意见》（2026-11-25，`PENDING OWNER RULING`）第四节《当前执行授权》下发
> **适用团队**：团队 A（Knowledge SDK 执行代理）× 团队 B（OpenBot / `openbot-vp` 执行代理）
> **冻结联调基线**：`knowledge-sdk@9940818b962ccb186c0dfb0158de6bd9bd49057b`（Schema v6 + `/v2/spaces` 保持锁定不动）
> **严格红线**：**`schema_v7_ddl_authorized: false`** · **`migration_authorized: false`** · **`prod_shadow_or_cutover_authorized: false`** · **`final_alignment_frozen: false`**。本波次仅执行经授权的 7 项非破坏性并行工作，严禁突破 8 项禁止红线。

---

## 一、总授权边界（7 项允许 vs 8 项禁止）

| 分类 | 具体条款 |
|---|---|
| **本波次允许执行（7 项）** | 1. 继续 M2-B 非生产联调；<br>2. 固定 `9940818b` Schema v6 与现有 `/v2/spaces` 语义；<br>3. 完成 B3 安全补丁回归与代码审查；<br>4. 推进 `PRE-01` 至 `PRE-04` 补证；<br>5. 进行新 Space 模型、DTO、API、撤权 SLA 与迁移/回滚方案的非破坏性设计；<br>6. 编写隔离沙箱中的 SQLite 与 PostgreSQL 双引擎测试原型；<br>7. 对 `SPACE-C01` 至 `SPACE-C10` 契约包进行正式评审准备。 |
| **本波次严格禁止（8 项）** | 1. 任何 Schema v7 不可逆 DDL 合入主表/主分支；<br>2. 任何历史数据迁移（含 `tenantId=null` 自动迁移）；<br>3. 生产影子流量；<br>4. 生产切流；<br>5. 静默改变或破坏现有 `/v2/spaces` 兼容语义；<br>6. 未经审批删除旧表、旧 RPC、旧索引或历史迁移记录；<br>7. 将新增 `T-18` 至 `T-27` 描述为已经通过；<br>8. 未经 `PRE-02` 与 `PRE-04` 书面签认启用个人分享或离职交接规则。 |

---

## 二、团队 A（Knowledge SDK）前置并行任务指令

**分支与保护约束**：严禁改动 `main`、`v2.0.0`、`feat/align-wave1p5-m1-readiness@07f5d39f`、`feat/align-wave2-m2-min-slice@9940818b` 及现有 `migrations/`（Schema v6 逐字节保持不变）。可基于 `9940818b` 切出独立非破坏性设计/原型分支（例如 `feat/space-alignment-v1-design-proto`）执行以下 4 项任务：

1. **TA-1｜全套 Space-Alignment v1 非破坏性契约与设计定稿准备（对应 SPACE-C01–C10）**
   - 补齐 `SDK_SPACE_LIFECYCLE.md`（覆盖 Enterprise / Team / Personal 生命周期状态机、负责人移交、归档与冻结；个人分享与离职交接显式标记 `GATED_BY_PRE02_PRE04`）。
   - 补齐 `SDK_SCHEMA_V7_MIGRATION_PROPOSAL.md`（双引擎 SQLite + PostgreSQL `FORCE ROW LEVEL SECURITY` 目标 Schema 草案、只读 Dry-Run 存量统计与别名/`null`/名称碰撞报告器规格、可逆回滚与异常处置方案）。
   - 按建议裁决逐项校准既有 6 份文档与 `space-alignment-v1` 契约草案：
     - `SPACE-C01`：扁平三层 `Tenant -> Space -> KB`，明确关闭 `parent_space_id` 与一期跨 Space 移动；
     - `SPACE-C04`：`Space.org_id == KB.org_id` 强校验、`1 Space : N KB`、`detach` 绝不隐式 `archive`；
     - `SPACE-C05`：8 动作独立权限矩阵、多层上限相交 + 显式 Deny 优先、事务 Outbox + `policy_generation` + 读时权威校验，**补充撤权延迟目标与异常处理 SLA 安全验收标准**；
     - `SPACE-C06`：Favorites 调整为 OpenBot 单写主 + 多态 `target_type in ('kb', 'asset')` + SDK 批量实时 ACL 水合 DTO；
     - `SPACE-C08`：`AgentProfile` 保留 Space 上限 ∩ `KB / knowledge-file / deliverable / folder` 细粒度消费范围 ∩ `User` 实时读权；
     - `SPACE-C09`：明确一级 Space 采用独立路径或契约版本协商（如 `/v3/spaces` 或 `/v2/knowledge-spaces`），确保 `9940818b` `/v2/spaces` 零语义变更；
     - `SPACE-C10`：定义统一 `Asset` Envelope，显式区分 `uploaded_document`、`agent_deliverable`（5 分态）、`enterprise_materialized_ref`（含 `projection_id / scope_applied / masked_fields / trace_refs / freshness / publication_state (complete|partial) / cursor / Tombstone`）与 `data_capability` Tool 边界（不暴露数据源凭据给普通文档 Agent）。
2. **TA-2｜跨语言契约夹具包（`contracts/space-alignment-v1/`）**
   - 输出 OpenAPI 片段、TypeScript DTO 草案及脱敏 JSON 测试向量（覆盖多态收藏批量 ACL 水合、三类供给 DTO、外部引用权限失效/Tombstone、`SPACE-C01–C10` 独立命名空间标识），绝不覆盖 M1 已冻结 `contracts/` 下的 28 项资产（`verify_frozen.py` 必须继续 100% 零漂移通过）。
3. **TA-3｜隔离沙箱 SQLite + PostgreSQL 双引擎测试原型**
   - 在独立原型/沙箱测试目录（不修改生产表迁移序列，不触发 Schema v6 -> v7 升级）实现 SQLite 与 PG `FORCE ROW LEVEL SECURITY` 双引擎验证原型，预演 `Tenant -> Space -> KB` 隔离、企业管理员不可读员工个人空间、同租户双协作小组隔离、外部引用撤权 Fail-Closed 等核心不变量，并明确区分**沙箱原型验证结果**与**正式 T-01–T-27 验收门槛**（严禁宣称 `T-18`–`T-27` 已通过正式验收）。
4. **TA-4｜只读 Dry-Run 碰撞预检脚本原型**
   - 编写纯只读迁移 Dry-Run 分析器原型（接收团队 B `PRE-03` 脱敏输入格式），可输出租户数、`null` 存量、`legacy_kb -> space + kb` 映射碰撞与告警清单。

---

## 三、团队 B（OpenBot）前置并行任务指令

**分支与保护约束**：继续锁定 `knowledge-sdk@9940818b` 只读镜像联调，保持 `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED=false` 默认关闭，严禁接入 Gateway 默认路由、严禁删除旧表/旧 RPC/旧索引、严禁启动生产影子或切流。同步推进两条并行工作流：

1. **TB-1｜M2-B 非生产联调闭环与 B3 安全补丁收口（高优收尾）**
   - 在 `codex/openbot/knowledge-sdk-v2-min-slice-adapter` 上完成基于 `9940818b` 的**全部 10 项最小切片断言**（SQLite + PostgreSQL 双引擎实弹验证）。
   - 完成 B3 安全补丁（`User 读权 ∩ robotBinding ∩ tenant`，成员读取仅认稳定 `userId`）的全量回归测试与代码审查准备（审查合并前继续如实标记为“未合入生产”）。
   - 保持 M1 冻结记录、授权记录与归属冲突的规范入库准备。
2. **TB-2｜前置阻断缺项 `PRE-01`、`PRE-02`、`PRE-03` 实证补齐**
   - **`PRE-01`（团队 B + 产品负责人）**：交付 OpenBot 组织 Team 唯一权威主表、稳定主键格式、成员增删/负责人移交/团队解散真实事件链路源码证据，并取得产品负责人关于“1 业务 Team = 1 Space”还是“1:N”及 `collaboration_group` 映射规则的书面确认。
   - **`PRE-02`（团队 B + 安全/产品）**：交付个人空间/单篇文档/单个 KB/整空间及跨租户分享的全部管理入口、存储入口与前端入口审计清单（含旧邮箱成员兼容路径的处置建议）。
   - **`PRE-03`（团队 B + 运维/DBA）**：协同运维/DBA 出具只读脱敏存量统计与别名/`null` 碰撞预检报告（严禁读取或外泄原始业务正文）。
3. **TB-3｜OpenBot 侧契约评审准备（对应 SPACE-C05 / C06 / C10）**
   - 梳理 OpenBot 现有 `knowledge.*` RPC 从粗粒度 `read / write / admin` 到 8 动作（`SPACE-C05`）的逐处理器映射草案；
   - 设计浏览器 `localStorage` KB 收藏升级为 OpenBot 服务端轻量收藏写主的迁移隔离方案（按 `tenant_id + user_id`）并提请产品负责人确认不可访问占位 UX（`SPACE-C06`）；
   - 与团队 A 对齐企业物化 Feed 席位/源权限实时水合回调或令牌断言协议与 Tombstone 刷新语义（`SPACE-C10`）。

---

## 四、项目、产品、法务与架构负责人并行门禁动作

1. **书面定调与正式签认**：审阅并将《项目负责人建议裁决意见》（`PENDING OWNER RULING`）升级为正式书面决议（同步确认 `SPACE-C03` 映射基数、`SPACE-C06` 占位 UX 与 `SPACE-C05` 撤权 SLA）。
2. **`PRE-04` 书面审批**：由产品 + 法务 + 架构负责人签署员工离职身份冻结、个人空间保留期、工作成果双人审批交接边界及个人正文不可继承规则的书面合规审批。

---

## 五、进入 Schema v7+ 实施的八项硬退出门槛（缺一不可）

仅当以下 **8 项全部满足**，双团队方可生成 `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` 并申请进入 Schema v7+ 工程实施：

1. `SPACE-C01` 至 `SPACE-C10` 已有明确书面决议；
2. `PRE-01` 至 `PRE-04` 全部形成实证记录并完成书面签认；
3. 双引擎 Schema 设计与只读迁移 Dry-Run 完成；
4. 迁移碰撞与异常处置方案明确；
5. SQLite、PostgreSQL `FORCE ROW LEVEL SECURITY`、HTTP、Python、MCP 契约测试计划（含 `T-01`–`T-27`）完成评审；
6. 个人空间、Team 隔离、Agent 权限及外部引用实时撤权测试原型通过；
7. 完整回滚方案通过评审；
8. 项目负责人**另行签发** Schema v7 正式实施授权（以及相应的法务、安全与生产变更审批）。
