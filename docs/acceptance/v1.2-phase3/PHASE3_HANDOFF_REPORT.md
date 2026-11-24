# PHASE3_HANDOFF_REPORT — Q1-M3

生成：2026-11-24T18:07:17.209692+08:00（Asia/Shanghai）

## 交付与真实基线

- 分支：`feat/phase3-anchors-storage-v2`
- Review branch：<https://github.com/flykingvip-cloud/knowledge-sdk/tree/feat/phase3-anchors-storage-v2>
- Compare：<https://github.com/flykingvip-cloud/knowledge-sdk/compare/feat/phase2-policy-engine...feat/phase3-anchors-storage-v2>
- 本报告：<https://github.com/flykingvip-cloud/knowledge-sdk/blob/feat/phase3-anchors-storage-v2/docs/acceptance/v1.2-phase3/PHASE3_HANDOFF_REPORT.md>
- **真实起点**（本地及 origin/Phase2 一致）：`eecb0252c77a6f058bc581d8b6f06ee1dc1a295d`。
- **实现终点**（最后 src/tests 提交，所有最终日志针对该源码）：`6a1cd89229528e7148d046d2e16a2c0e1f6f0d25`。
- **原始证据 SHA**（实现后的 docs-only 提交）：`5db095dfc446015f7adc7f542ac0de0d77f8896d`。
- **最终报告 SHA**：本文件所属的后继 docs-only commit；避免自引用假 hash，不把自身 hash 写入自身内容。精确命令 `git log -1 --format=%H -- docs/acceptance/v1.2-phase3/PHASE3_HANDOFF_REPORT.md`，最终交付消息另给完整值。最终 branch tip 与报告提交一并由远端核对。
- main / origin/main：`0ed15b93e2a6eed893369ca81524909c328c8b5c`，未改动。审计时远端 Phase3 不存在，无未知远端修改被覆盖。
- 本轮只在既有 box `/workspace/knowledge-sdk` 开发，没有 clone/cloud agent、Mac 工作树操作或既有服务操作。原未跟踪 `reports/` 保留且不提交。
- 仅正常推指定新 feature branch；不创建 PR、不合 main、不打 Tag/Release，不 force/no-verify/amend 已推提交。最终 push 结果及远端 tip 见交付输出，不用预填成功状态替代远端核对。

## 任务 1–5 映射

| 任务 | 实现与验证 |
|---|---|
| 1 URI/anchors/models | 严格 v2 URI 与旧四元组兼容；不可变 selectors/EvidenceAnchor、嵌套 JSON 与冻结；KnowledgeRef.anchor_id、严格 bool budget 标志；公共导出 |
| 2 Layout / reanchor | 保持历史全文的 CSV/Markdown/HTML 布局；legacy parser fallback；PDF 宿主离线版面插件；稳定旧 ID、anchored/pending/orphaned、保守合并 |
| 3 SQLite / fetch | 单事务 v0/v1→2、8 列回填与所有写路径同步、三表索引、租户隔离 rule/anchor API；pushdown + 有界授权补取，最多评估 500，布尔 lookahead 区分 exact500 |
| 4 全链路接入 | ingest 与 anchors 同事务；list/get/confirm；当前八步权限、不可绕过脱敏；anchor ref/consume/verify/attach；Local/Protocol/HTTP 签名头接口，无前端变更 |
| 5 测试/证据 | 新 44 个 unittest 方法（包括 7 个可选 HTTP 方法）；覆盖 B02 离线 PDF/科学 CSV、重锚状态、真实 schema1 迁移故障回滚、B07 120/500 边界、HTTP 信任边界；分层原始日志 |

实现和提交序列：

```text
d054ff1d0f3dcda3eb148d11c9eb082f2b2cadf1 feat(anchors): add precise immutable selectors and strict v2 URI parsing
0c94652e0268435a25d84c28a360bc31405d03e3 feat(anchors): add compatible layout parsers and conservative reanchoring
98a43a5743db9b874ab4c6d30a85f2d6840dc367 feat(storage): migrate atomically to schema v2 and bound authorized retrieval
bba79f67e28c31da0a5cd61f08cf4162c7f21f90 feat(client): enforce live policy and redaction for anchor references and confirmation
c610c85946361b40692e19a1f0e5af178d05969b test(phase3): cover B02 anchors, atomic migration and B07 bounded policy fetch
6a1cd89229528e7148d046d2e16a2c0e1f6f0d25 fix(anchors): recheck authoritative identity and roundtrip layout dictionaries
5db095dfc446015f7adc7f542ac0de0d77f8896d docs(phase3): archive separate L1-L5 evidence and precise interface boundaries
```

## 独立分层结果（不混合累计）

| 层/执行 | 实际状态 | passed | skipped | 原始路径 |
|---|---|---:|---:|---|
| L1 python3 -S unittest，ResourceWarning=error | 成功；395 方法 | 304 | 91 | `l1-stdlib-only.log` |
| L2 全依赖 unittest，ResourceWarning=error | 成功；395 方法 | 392 | 3 | `l2-full-and-build.log` |
| L2 独立 pytest | 成功；不与 unittest 累计 | 392 | 3 | 同上 pytest 段 |
| L2 build / AST / wheel / 阻断第三方 import | 成功；非额外测试方法总数 | — | — | 同上及 `verify_wheel.py` |
| L3 loopback 真实 HTTP | 本地独立 probe 成功，exit_code=0 | 不折算单测数 | — | `l3-local-http.log`、`l3-live-integration.md` |
| L3 在线 Qdrant / embedding / 语义 | SKIPPED，未配置隔离 live URL/model；无外部调用 | 0 | 既有 3 项 live tests | 同上与 L1/L2 skip 原文 |
| L3 真实反代 | NOT_RUN，未部署真实 proxy | — | — | `l3-live-integration.md` |
| L4 浏览器 | NOT_RUN，无本轮视觉变更、未操作浏览器 | — | — | `l4-browser.md` |
| L5 | **待独立验收架构师/专家复核**，不自封 PASS | — | — | `l5-review.md` |

- 既有 Phase2 351 方法 / 348 passed + 3 skipped 基线上新增 44 个方法；全依赖执行全部既有测试，无删除安全断言。L1 额外跳过缺失可选 HTTP 依赖的项目，skip 不计通过。
- pytest 原文还记录 **148 subtests passed / 1 warning**；subtest 不算额外方法、不与 unittest 合并。唯一 warning 为安装环境 Starlette/TestClient 对 httpx 的弃用提示，不是 license 或 ResourceWarning；未为消除提示新增依赖。
- L1/L2 均真实使用 `-W error::ResourceWarning`；三份原始执行日志复核无 ResourceWarning、Exception ignored 或 PytestUnraisableExceptionWarning；新建/失败初始化的连接确定性 close。
- 运行解释器实际为 Python **3.13.5**。所有 **50** 个 src Python 文件通过 Python 3.9 AST 语法解析；**不是实际 Python 3.9 runtime 实测**。
- `python -m build` 成功；SPDX MIT 无 license 弃用警告；核心 `dependencies=[]` 不变，wheel METADATA 无 core Requires-Dist。`-S` 阻断第三方 import 验证成功；独立临时解包 wheel 的 CSV→anchor→JSON→reference/receipt/schema2 运行成功；UI 四个静态资源及动态 1.2.0 仍在包中。
- wheel：`knowledge_sdk-1.2.0-py3-none-any.whl`；SHA256：`b5c30728e504940e8660d9dca731a10e79e696b77560df711d214a5b35972f1b`。二进制未提交，只记录文件名/hash。

## L3 实际边界

`live_http_probe.py` 使用新建临时业务库和独立 replay 库，空闲 loopback 端口；实际经 HttpKnowledgeClient 上传 CSV/MD、消费三种重锚状态、管理员确认、脱敏 hash 与 cell_ref、签名 Agent/Purpose、body 注入以及真实 HTTP nonce 重放。没有外部模型/embedding/Qdrant 调用；原始日志包括 shutdown 和临时文件清理。服务主动 SIGTERM 后 returncode=-15，probe 自身成功，不留常驻进程。

**不把本地 HTTP 成功改写成在线语义/真实代理/浏览器已通过；不把宿主离线 PDF fixture 冒称真实 PDF/OCR。** Phase1/2 已知空白继续保留。

## 偏差、风险和既有隐患

详细契约和决策见 `INTERFACE_AND_BOUNDARIES.md`。关键项：

1. TEXT_OFFSET 复用 SectionQuoteSelector 的偏移容器；PDF 页码变化保守 pending；重复 quote 只给确定性候选，不能自动确认。没有可靠同 kind span 的 pending 不能强制确认。
2. 新旧 span 重叠或包含旧 quote 时，不另造自动 anchored 别名；可能减少合并正文的新 anchor 数量，这是防 pending 绕过的保守取舍。历史库迁移不回填过去版本 anchors；语义未变上传保持旧 dedup，不静默重写历史。
3. 脱敏视图完全省略来源 metadata（连键也可能含敏感内容），selector 字符串也脱敏；原 geometry/offset 仍为来源坐标，section paragraph_hash 清空，交付 quote_sha256 重算；不污染权威 anchor。
4. 历史引用保持 version-pinned；不会将旧 anchored URI 自动重绑新版本 pending，但当前 rights/revocation/agent/purpose 始终实时约束历史读取。
5. Bounded prefix RRF 不保证无限召回/全局排名。每源最多请求 501 个身份作为 lookahead，但最多评估 500 个唯一候选；第 501 个不做权限/脱敏。False 不代表完整性认证，不向调用者返回拒绝数/标题。
6. 新业务 schema2 是本任务明确授权；只在隔离临时 DB 迁移。真实生产迁移/备份/回滚演练 **未做**，不得拿本轮结果授权直接打开线上库。policy_rules 保持构造注入兼容，不自动取代引擎规则；issues 仅表。
7. 旧 Phase1 `test_refuse_business_database` 仅将业务 schema 预期 1→2，认证独立库 user_version=0 断言未改。旧 Phase2 `test_schema_one_and_old_sqlite_json_reopen` 仅改 INSERT 为显式旧四列并将最终 schema 预期改 2，旧 JSON 加载及表不变断言保留。另有真正手造 schema1 fixture 验证迁移/回滚，未用“v2 改标签”冒充。
8. Python 3.9 只有 AST；真实在线 Qdrant/embedding、真实反代、真实 PDF bbox/OCR 和浏览器均未测。L5 仍待独立专家；本交付不自封关闭 B02/B07。

## git diff --stat / 文件清单

下列是起点到证据 SHA 的完整快照；最后后继报告 commit **仅新增本报告文件**，不改已测 src/tests。最终总差异另可执行 `git diff --stat eecb0252c77a6f058bc581d8b6f06ee1dc1a295d..HEAD`。

```text
.../v1.2-phase3/INTERFACE_AND_BOUNDARIES.md        |  52 ++
 docs/acceptance/v1.2-phase3/l1-stdlib-only.log     | 406 +++++++++++
 docs/acceptance/v1.2-phase3/l2-full-and-build.log  | 793 +++++++++++++++++++++
 docs/acceptance/v1.2-phase3/l3-live-integration.md |  28 +
 docs/acceptance/v1.2-phase3/l3-local-http.log      |  69 ++
 docs/acceptance/v1.2-phase3/l4-browser.md          |   5 +
 docs/acceptance/v1.2-phase3/l5-review.md           |   6 +
 docs/acceptance/v1.2-phase3/live_http_probe.py     | 122 ++++
 docs/acceptance/v1.2-phase3/verify_wheel.py        |  37 +
 src/knowledge_sdk/__init__.py                      |   6 +
 src/knowledge_sdk/client/anchors.py                |  36 +
 src/knowledge_sdk/client/base.py                   |  10 +-
 src/knowledge_sdk/client/http_client.py            |   1 +
 src/knowledge_sdk/client/local.py                  |  75 +-
 src/knowledge_sdk/contracts/anchors.py             | 159 +++++
 src/knowledge_sdk/contracts/models.py              |  14 +-
 src/knowledge_sdk/contracts/reanchor.py            | 106 +++
 src/knowledge_sdk/contracts/receipts.py            |  18 +-
 src/knowledge_sdk/contracts/uri.py                 |  64 +-
 src/knowledge_sdk/ingestion/parsers/__init__.py    |  21 +-
 src/knowledge_sdk/ingestion/parsers/builtin.py     | 120 +++-
 src/knowledge_sdk/ingestion/parsers/layout.py      |  70 ++
 src/knowledge_sdk/retrieval/hybrid.py              |  87 ++-
 src/knowledge_sdk/storage/base.py                  |   8 +
 src/knowledge_sdk/storage/sqlite_store.py          | 118 ++-
 tests/anchors/__init__.py                          |   0
 tests/anchors/test_phase3_anchors_and_reanchor.py  | 205 ++++++
 tests/permissions/test_phase2_policy_engine.py     |   4 +-
 tests/server/test_phase1_auth.py                   |   2 +-
 tests/server/test_phase3_anchors_http.py           |  55 ++
 tests/storage/test_phase3_sqlite_v2_and_fetch.py   | 139 ++++
 31 files changed, 2759 insertions(+), 77 deletions(-)
```

## 发布红线核对

版本仍 1.2.0、零核心第三方依赖；未改前端视觉/中英文合约，未提交 wheel/db/cache/venv/.env/密钥/原用户附件或 reports。未操作 Mac8091/8090/3000/3001/8000/8002、OpenBot/StratAI/既有 Qdrant 数据；未跑 official start/stop。没有 main 合并、自动 PR、Tag 或 Release。

**第三阶段实现与证据交付，等待独立复核；Phase4/MCP/60 黄金 Benchmark 仍未解锁。**
