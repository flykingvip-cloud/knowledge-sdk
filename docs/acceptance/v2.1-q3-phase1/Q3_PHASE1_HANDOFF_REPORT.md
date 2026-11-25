# Q3-M1 交接报告：Agent Knowledge Runtime / Schema v5

> 生成日期：2026-11-25，Asia/Shanghai。工程交付与独立退出验收分开记录。
> 最终日志已由归档脚本逐项断言核验；源码/测试冻结，归档提交只增加文档与证据。

## 1. 授权、起点与交付状态

* 仅实施 t53u 新授权的 Q3-M1；按明确覆盖继续在本地 box checkout 工作，未启动 CloudAgent。
* 基线精确为 `a5d1432b525dbb35cbd6e5018214886243ccc333`。
* 分支：`feat/q3-phase1-agent-runtime`。
* 最终源码/测试提交：`8acce646760da46f7c1797b83ea3b4fbd56a0d6e`；后续归档提交不改变运行时代码。
* 源码四作业 CI **全部成功**：
  https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45533545659
* 企业 / StratAI 接入与此前包交接保持 t52u **暂停**，未恢复。
* **不宣称 Q3-M1 已独立验收通过或解锁 M2**：Task 0 的 main/tag 收口仍等待显式确认，补充规范缺失待对齐，L5 独立复核待执行。

## 2. Task 0：CI 已修复，main/tag 未收口

首条独立提交 `f447fa4` 修复 runner 矩阵：Python 3.9 → ubuntu-22.04，3.12 → ubuntu-24.04。
真实 CI 又发现 -S 子进程 PYTHONPATH 与 Python 3.9 空 HTTPError 测试夹具问题，分别修复；未删除、过滤、跳过或弱化原测试。

Q2+CI 专用候选（尚无 Q3 代码）为 `b953c9922cc1096e0e88455dab6746c01a9d27f9`，
全矩阵成功：https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45531017247 。

只读核验：main 仍为 `0ed15b93e2a6eed893369ca81524909c328c8b5c`；GitHub 返回 protected=false、
required-check enforcement=off、rulesets=[]；远端未观察到任何 tag ref。**没有声称受分支保护阻塞，也未试写 main**。

完整且明确的待确认收口计划见 `task0-convergence.md`：重新核验 refs/规则/CI 后，另经显式确认，
才可考虑仅将 main 快进到上述 Q2+CI 候选、并在另获 tag 批准后创建 v2.0.0。绝不把本轮 Q3 head 当作 Q2 tag，
不移动既有 tag、不绕过规则。当前状态为 **PENDING_EXPLICIT_CONFIRMATION**，不是 Q2 Git 已全部收敛。

## 3. Tasks 1–4 实施清单

### Schema v5 与持久化

SQLite / PostgreSQL 均新增任务书四张精确表：agent_profiles、task_contexts、context_snapshots、task_revocations；
支持 v0..v4 → v5 保留既有数据、可重复打开。PG 四表均进入租户表清单并启用 ENABLE/FORCE RLS。
持久化覆盖档案、任务、快照、撤权及带索引的引用反查。SQL 冗余列与 JSON 相互核对；快照内容仅插入，撤权只改外部状态。
DR 工具真实覆盖 v5 四表种子、31 张表的备份恢复指纹及迁移中断事务回滚。

### 冻结契约、档案与严格交集

公开导出 ContextBudget / AgentProfile / TaskContext / SnapshotItem / ContextSnapshot / MidTaskRevocation，
支持严格 encode/decode 与 to_dict/from_dict；拒绝布尔整数别名、负预算、空标识、非法 Purpose，以及布尔时间戳/摘要别名。
仅 admin/manage_org 可注册、修改和停用档案；代际递增、AuditEvent、OutboxEvent 与任务失效原子提交。
Actor + 当前目录代际 + 档案 purpose/KB/space/clearance + task scope 取交集；空选择器和显式 none 不混淆。
未来代际也不能当作合法当前目录凭据。预算与 TTL 只会被 min 钳位，零预算不回退为无限。

### 不可变快照、HTTP 与 MCP

实现 create_task_context、create_context_snapshot、read_task_snapshot、complete_task_context；
以及档案查询/管理、任务撤权查询。Local/HttpKnowledgeClient 公开契约一致；/v1/runtime/* 全路由 no-store，
Actor 来自 HMAC/OIDC 服务端上下文。客户端不能指定任务所有者或提升预算/代际。

快照每个条目通过真实 PolicyEngine、RedactionRegistry、锚点健康校验，确定性预算截断，SHA-256 密封；
读取时全量实时复核目录、档案、资源、最新锚点与脱敏表示。UsageEvent.task_id 与 context_snapshot consumer_id 关联任务/快照。
正常文档修订保留旧快照 v1 文本，产生 SUPERSEDED 告警，不静默换成 v2。

MCP 四工具未提供 task_id 时保留旧行为；search/verify/getpack 提供 task_id/snapshot_id 时必须进入真实、当前且属于自己的任务。
未知任务不是自由 lineage 标签。旧黄金/线缆夹具只补“先注册真实任务”的准备步骤，原有行为断言保持不变。

### 六族实时撤权与并发一致性

覆盖 revoked、archive、ACL 收紧、drift/orphan、SCIM generation/deactivate、profile generation/disable。
写路径与 ImpactRadar/Outbox 都能主动写事件关联 task_revocations、撤销任务/快照、产出仅标识符的 task_context 告警；
读取/追加/绑定 MCP 在 dispatcher 刷新前即拒绝，DENY 审计在抛异常前提交保存。
锁顺序为 client._lock → store.runtime_transaction；PG 独立连接使用保守的数据库级运行时/策略写串行化边界，
不串行锁住 Outbox claim。独立连接插入期间的 SCIM/档案竞态及既有 SKIP LOCKED fencing 测试通过。

## 4. Task 5：实测门禁与证据

| 层 | 最终实际结果 | 证据 |
|---|---|---|
| L1 | 849 执行，588 通过、261 可选依赖/PG 跳过；0 失败、0 ResourceWarning、无隐式依赖 | l1-stdlib-only.log |
| L2 unittest | 849 执行，846 通过、3 跳过，0 失败 | l2-full-and-build.log |
| L2 pytest | 846 通过、3 跳过，另 220 subtests 通过；1 个第三方弃用警告，0 ResourceWarning | l2-full-and-build.log |
| Python 3.9 / 包 | 104 个源码/基准文件 AST 通过；build、Wheel RECORD、解包 -S 运行时/撤权冒烟通过 | l2-full-and-build.log |
| 黄金 SQLite | 默认 115/115；legacy75=75/75，legacy100=100/100 | benchmark-115-sqlite.json |
| 黄金真实 PG+pgvector | 默认 115/115；legacy75=75/75，legacy100=100/100 | benchmark-115-postgres.json |
| L3 | 每引擎 109 组真实 HTTP 断言；HMAC/OIDC/MCP 六族九变体、非超级用户 RLS、独立连接竞态、DR v5 通过 | l3-runtime-postgres-http.md |
| L4 | NOT_RUN_NO_UI_CHANGES；未改 UI、未启动浏览器；Q2 无头证明仅作历史记录 | l4-browser.md |
| L5 | PENDING_INDEPENDENT_REVIEW | 本报告 |

旧黄金文件 golden_cases_v1/v2、g6.py、golden_cases_v3_enterprise、g7_g8.py 字节级不变；
原 runner 60 个场景函数源码亦逐字比对不变。新 G9 独立 15 场景，未替代旧 100 条。
双引擎 ACL violation 分子均 0，security assertion failures=0，implicit_model_calls=0。
三个全依赖跳过项均为受安全边界禁止的真实在线 Qdrant 集成，不伪装为已测。
pytest 的唯一警告来自已安装 FastAPI/Starlette 的 httpx TestClient 弃用提示，不是 ResourceWarning，未屏蔽。

四作业 CI 的 3.9/3.12 × core/http-and-package 全部实际执行并成功，见 ci-four-job-matrix.json。
历史失败运行链接、修复过程与 Q2 专用候选证明保留在 task0-convergence.md；不会把早期失败写成通过。

## 5. 补充规范、实现假设与诚实边界

任务书引用的 **knowledgeos-q3-core-protocol-spec-v0.1.md** 与
**knowledgeos-strategy-architecture-v0.2.md** 未在仓库、/workspace/q3-task-inputs、/workspace/q2-task-inputs 中找到。
没有编造其字段或声称已遵循不可见规范。按已完整读取的详细任务书实现，默认预算、API 参数、canonical text、
空白名单、任务 none scope、保守 ACL/rights 更新失效和超预算 MCP 拒绝等补充选择均在 docs/agent-runtime.md 明列。
待补充规范到位后再独立核对差异。

未接真实企业 IdP/SCIM、收费模型/embedding、在线 Qdrant、真实 PDF/OCR 或外部 Claude Desktop/Cursor；
离线签名 IdP 夹具与本地实际 HTTP 不等于真实企业互通认证。PG RLS 仍依赖可信 app.current_org_id 应用边界；
数据库级保守串行化不构成吞吐/SLA 承诺；SHA 密封不是对抗拥有完整重算权限的 DBA 的外部签名。

核心 dependencies=[] 未改；包元数据仍是 1.2.0，明确为按精确分支 SHA 标识的未发布工程产物，未上传、发布或恢复企业包交接。

## 6. 安全清理与仍待完成事项

只使用本轮新建隔离数据库与动态回环端口；未操作现有服务、既有数据库/容器、Mac/OpenBot、StratAI start/stop、
.env.production 或保留端口。自有临时 HTTP 子进程均退出；自有 PG 集群已停止、临时 DB 数据已清理。
reports/ 保持未提交；旧测试自动重写的两份历史 L3 日志恢复为原始 Git 内容，未混入新证据。

仍待：
1. **显式确认后**才执行 Task 0 的 main/v2.0.0 收口，当前未合并/打 tag；
2. 补充 Q3 protocol/strategy 规范或由验收方明确确认本文已列的补充假设；
3. 独立复跑/代码审查与最终 Q3-M1 退出评审。

企业/StratAI 接入仍暂停；未创建 PR、未 force-push、未修改全局 Git 配置、未合并 main、未打/移动标签、未 release/deploy。
未提前实现 Q3-M2 reranker/evaluator、M3 claims/graph、M4 垂类包或 Q4 console/Helm/license。
