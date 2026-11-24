# Q2-M2 PostgreSQL + pgvector — Handoff

- 编写时间：2026-11-25T04:35:58.632633+08:00（Asia/Shanghai，UTC+8）。
- 分支：`feat/q2-phase2-postgres-pgvector`；起点精确为 `6fc5b194f6508770c7760f3712e17f3b553dd4e8`。
- 实施/测试说明提交：`ebd9278d76e9bf0b997455d6d9a829e34460ee35`；最后运行时代码修改为 `d16e199`，随后仅修正 benchmark 报告文案。最终证据提交与远端 SHA 见交付消息 / 分支历史（避免报告自引用 SHA）。
- 按既有明确本地覆盖指令在 box `/workspace/knowledge-sdk` 实施；未使用 CloudAgent、未访问 Mac。开始时 tracked 状态干净，仅有既存 untracked `reports/`，其内容未提交。
- 已完整阅读 staged Q2-M2 任务书与 Q2 core protocol v0.1。上游 strategy architecture v0.2 未在 staged 输入、目标仓库或 deliverables 找到，不能声称已读。
- **M1 架构师独立验收通过是任务书提供的前置事实，不是本执行者取得的独立实证。Q2-M2 的 L5 仍待独立复跑。**

## 1. Tasks 0–4 实施结果

| Task | 实现 / 约束 | 主要证据 |
|---|---|---|
| 0 | 核心 `dependencies = []` 原样保留；`postgres = ["psycopg[binary]>=3.1,<4"]`；默认路径不导入驱动；缺失驱动明确报安装 extra；迁移 console entry point + SQL 资源完整入 Wheel | L1、白盒、build/wheel |
| 1 | 原生参数化 psycopg SQL 的完整 MetadataStore；Schema v3 + schema_migrations；派生列/索引、预留空表；所有 payload/child 表显式 org 绑定 + 默认 ENABLE/FORCE RLS；局部 set_config、嵌套 savepoint、连接关闭；advisory xact audit lock；CJK 单字/bigram + tsvector GIN + 原有有界授权补取 | 双引擎 76 契约/每引擎、RLS/并发、migrate CLI |
| 2 | metadata-only PgVectorIndex 精确余弦；回源原有 8 步策略与 fail-closed 脱敏；共享原子 TTL replay（兼容现有 nonce/ttl 与显式 org/nonce/expires_at）；create_app / CLI / DSN env；可选本地非语义 HashEmbedder；凭据脱敏/数据库错误 detail-free | 真实 pgvector stale-policy、nonce 竞态、双进程 CLI HTTP |
| 3 | SKIP LOCKED 原子领取 + 60 秒租约 + attempt fencing；处理锁持有至 handler/status 事务结束；四 Worker 独立连接真实 loopback webhook；保留退避/死信/幂等约束；共享同一 75 原始黄金断言及额外中英混合隔离契约 | specialized / parity / 双引擎 JSON |
| 4 | 两个新空库实际 pg_dump custom + pg_restore；24 表、103 行 rowcount + canonical SHA-256 完全一致；真实 DDL 中断回滚后重复 apply；还原 audit/ACL/锚点/绑定/usage/impact/旧版本引用；五层证据与边界归档 | dr-report / l3-dr / 本报告 |

兼容性说明：旧 MetadataStore 的无 org 全局 ID 路径通过最小 `resource_directory(kind,id,tenant)` 定位后进入租户上下文；它只有身份路由元数据、没有 payload，不是授权接口。`org_id=` 可 pin 单租户实例；提供 org 的过滤查询不做不必要的全局定位，跨租户过滤与 SQLite 同样返回空。不要向不受信任调用者提供 SQL/DSN/set_config 权限。生产运行角色不得 Superuser/BYPASSRLS；迁移角色与运行角色分离建议见 `docs/postgres.md`。

## 2. 实测总表（不把 skip / subtests 计作方法通过）

| 层次 | 真实结果 |
|---|---|
| L1 `python3 -S -W error::ResourceWarning -m unittest discover -v` | 666 方法：**485 passed，181 skipped，0 failures，0 ResourceWarning**。skip = 98 既有可选/真实外部能力 + 76 PG parity + 7 PG-only live；无 DSN/无驱动时清楚跳过 PG，未冒充通过 |
| L2 full-deps unittest，配置真实 PG | 666 方法：**663 passed，3 skipped，0 failures** |
| L2 full-deps pytest，配置真实 PG | **663 passed，3 skipped，200 subtests passed**；另有 1 条可选 FastAPI/Starlette TestClient 的 httpx 弃用警告，不是 ResourceWarning；未隐藏它 |
| L2 Python 3.9 AST / PEP517 build / extracted Wheel | src 74 文件 + benchmark 5 文件 AST3.9 通过；sdist/Wheel 成功；解包后 `-S` SQLite/lazy-driver 与真实 PG/pgvector/replay smoke 均通过 |
| 双引擎黄金 | SQLite **75/75**，真实 PG + pgvector fixture **75/75**；G1–G6 原始 JSONL、g6.py 字节未变；runner 仅装配/诊断 probe/transport/replay/文案参数化，未削弱断言 |
| L3 非 Superuser / 并发 | RLS 原生跨租户读/写被挡；4 连接 160 worker audit commits + 1 setup，4 次回滚，不冲突/不分叉/无序号空洞；4 replay 实例同 nonce 仅 1 成功、TTL 过期可复用 |
| L3 Outbox | **4 Worker，96 事件全部 dispatched，64 次实收且签名有效的 POST，64 唯一 delivery IDs，32 影响告警**，各 Worker 均处理任务、无死锁；过期锁行 SKIP、旧 attempt 被 fence |
| L3 HTTP | 两个真实 CLI 进程：显式 `--dsn` 与 DSN 环境变量；中英检索/向量候选/锚点/receipt/usage/impact/ACL；跨实例同签名 nonce **200 → 401**，未签名 **401**，正常关闭 |
| L3 DR | **24 表 / 103 行**指纹全同；每租户恢复 22 条 audit 链有效、v1 pin/锚点/绑定/usage/alert 可读，既有拒绝 ACL 生效；迁移中断回滚与幂等重迁通过 |
| L4 | **NOT_RUN**，UI 未变；没有浏览器/真实反向代理/宿主登录/CSRF 实测 |
| L5 | **PENDING independent review**，本报告不是独立验收批准 |

两种引擎各自黄金安全指标：ACL 违规 **0/20**、隐式模型调用 **0**、MCP 注入阻断 **36/36**、审计篡改/删行探针检出 **19/19**、影响目标完整度 **45/45**、多余目标 **0**。

运行环境：Linux x86_64，Python **3.13.5**，PostgreSQL **17.12**，pgvector **0.8.0**，psycopg/binary **3.3.9**。实际未运行 Python 3.9 解释器；3.9 证据是 AST，不冒充运行时矩阵。更多依赖精确版本在 environment.log。构建器另有 NO_COLOR/FORCE_COLOR 配置提醒，不影响产物，未冒充零所有警告。

## 3. Evidence index / 复跑

- `l1-stdlib-only.log` / `l1-pg-whitebox.log`
- `l2-full-unittest.log` / `l2-full-pytest.log` / `l2-build-wheel.log`，汇编为 `l2-full-and-build.log`
- `benchmark-75-sqlite.json` / `benchmark-75-postgres.json` 及对应 `.log`
- `l3-pg-specialized.log` / `l3-cjk-shared.log` / `l3-pg-http.log` / 两份 CLI process logs
- `l3-dr.log` / `dr-report.json` / `migrate-cli.log`，连同最终 parity 输出汇编为 `l3-pg-parity-concurrency-dr.log`
- `original75-preservation.log` / `security-and-scope.log` / `environment.log` / `cleanup.log`
- `live_pg_http_probe.py` / `verify_wheel.py`；DR 可执行 `python -m knowledge_sdk.storage.dr_drill --confirm-disposable`（只接受两新空 sdk_dr_* DB）
- 复跑环境与运维安全步骤：`docs/postgres.md`。`KNOWLEDGE_SDK_TEST_PG_DSN` 必须是独立可丢弃 DB，提前由 DBA 安装 vector。

`development-*` 保留真实早期失败及修正历史，不作为最终通过依据：包括误填 WebhookSubscription 参数、测试对象 encode/审计 setup 数量、PG ImpactRadar 中残留 SQLite placeholder、public schema 还原壳冲突、DR 缺少显式 bind_consumer、future annotations 约定以及意外重复 unittest alias。最终命名日志均已独立重跑通过。

## 4. 明确的未测边界与生产限制

1. **不是 universal exactly-once**：健康运行压测零重复；接收端成功、发送端提交前崩溃仍可能重发，接收方必须按 X-KB-Webhook-Id 去重。没有宣称崩溃窗口/网络分区全覆盖。
2. 单连接/实例，多实例并发；不是生产集群容量/HA/PITR/failover 验证。精确 pgvector cosine，不声称 ANN/语义质量或性能提升。
3. 本次仅临时 loopback/Unix socket trust 测试，**未使用口令/生产凭据**。真实受控凭据、TLS/代理拓扑、安全团队准入需宿主环境验证。RLS 以应用设置可信 tenant 为边界，不抵御持有 DB owner/SQL 权限的恶意人；链式 audit 也不是独立外部签封/对任意 DBA 全链截断的绝对证明。
4. DR 是隔离空库的 table-owner 操作；临时 NO FORCE 备份后恢复 FORCE。回滚证明是事务 DDL 中断回滚 + v3 幂等重迁，不是破坏性的 v3→v2 降级，也不是生产备份自动化。
5. `HashEmbedder` 是显式本地词法 hash，不调用真实 Embedding 服务；黄金的 adversarial vector stub 保留原设计；真正 cosine/撤权/脱敏另有 PG 实测。
6. Q1 未闭环的在线 Qdrant + 真实 Embedding / 语义检索、真实反向代理 + 登录态/CSRF + 浏览器、真实 PDF/OCR、外部设计伙伴 Claude Desktop/Cursor 10 分钟接入门禁，**均未被本轮通过结果隐含关闭**。
7. M3 审批/纠偏处置/EvidencePack 构建导出、M4 OIDC/SCIM/connector 同步、Q3 均未提前实现；保留空表，未启动原有服务、未动 Qdrant/常驻 DB/受禁端口/.env.production/Mac/OpenBot/StratAI 脚本。
8. 提交按模块拆分；交付仅普通 push 新 feature 分支，**不 merge main、不建 PR、不 tag/release/deploy、不强推、不改全局 git config**。独立 L5 后由 owner/架构师判断下一门禁。

## 5. 资源收尾

`cleanup.log` 记录：本轮创建的 test schema 全部清理、其它应用连接为 0；只停止本轮 initdb 的隔离 cluster，并移除 apt 本轮新建且从未启动/使用的默认 17/main。临时 HTTP/CLI receiver 均 finally 退出。停止后的隔离数据目录及测试 venv 留作复现，没有遗留本轮运行中的 PG listener；未触碰已有服务/DB。
