# Phase 1 / v1.2.0 交接报告

状态：本阶段工程实现与证据归档完成；**不是五层全部验收通过**。
L4 未执行，L5 待验收架构师复核（B08收口），Phase 2 未解锁。

## 分支、真实起点与终点

- 分支：`feat/phase1-v1.2-baseline`
- 仓库：<https://github.com/flykingvip-cloud/knowledge-sdk>
- 分支：<https://github.com/flykingvip-cloud/knowledge-sdk/tree/feat/phase1-v1.2-baseline>
- 审查差异：<https://github.com/flykingvip-cloud/knowledge-sdk/compare/main...feat/phase1-v1.2-baseline>
- 真实起点：`0ed15b93e2a6eed893369ca81524909c328c8b5c`（已核对 origin/main、原本地 main，无受跟踪差异）。
- **实现终点完整 hash：`1e0b427dd470a5f07cd398ff2461d2318dd1dc68`**。
- 交接终点：本文件及原始日志作为实现终点之后的纯证据提交；为避免自引用
  假 hash，本文件不预造包含自身的提交号。交付分支最终 SHA 用
  `git rev-parse feat/phase1-v1.2-baseline` 获取，最终执行回执会单独列出。
- 实现终点已正常推送到上述独立分支；证据提交随后正常推送。
  未创建 PR、未合并 main、未建 tag/Release，未强推、未跳过 hooks。
- 历史任务书的 `6a32bc6` 已被真实起点替代；中英文切换及布局是起点已提交
  能力，予以保留，绝不倒退或冒称本阶段新实现。

## 任务 1–4 实施映射

| 任务 | 交付 | 提交 |
|---|---|---|
| 1 工作树审计与版本冻结 | BASELINE_AUDIT.md；版本 1.2.0；应用及 UI 动态读取版本；已有语言布局保留 | b811792 |
| 2 认证与上下文 | Actor policy_generation/session_id；共享 ReplayStore；锁内存/独立 WAL SQLite 原子防重放；fallback 轮换；可签名 Agent/Purpose；CLI 安全加载 | 31e835c |
| 3 子路径与生产门禁 | 可配置 ui_prefix；静态/配置/模块及 API 独立 base；可信 root_path 和原始目标契约；demo 默认404；初始HTML身份控件禁用；安全头/CSP；宿主清单 | 6f33358 |
| 4 验收与修复 | 42 项新增确定性方法；跨进程单赢家；默认/子路径/代理和安全测试；复现实证脚本与分层原始日志；修复静态挂载作用域及重复认证头歧义 | 1e0b427 + 后继证据提交 |

实现提交按任务顺序原子拆分；任务4测试暴露的挂载/安全问题在任务4修复并完整复测。

### 保留的兼容与约束

- 旧 Actor 两参数及旧 JSON 可读；新字段必须是字符串，JSON 可往返。
  默认新字段从签名载荷省略，维持 v1.1 默认 Actor 和六行签名逐字节兼容；
  非默认新字段仍签名。verify_headers 返回 Actor 不变，旧 seen 接口保留。
- ReplayStore 优先于 seen；每 app 默认独立内存 store。SQLite 通过真实六进程
  竞态及两个实例共享测试。数据库错误/容量满失败关闭，无效请求不抢占 nonce。
  未来时间戳覆盖全可接受窗口；业务 SQLite schema 保持 user_version=1。
- X-KB-Agent/Purpose 缺失保留旧消息；存在任一时追加两行，防移除/添加降级；
  Agent 大小/JSON/类型/租户校验，Purpose 白名单，重复认证头拒绝。
- ui_prefix 不是 API 前缀。`/kb/ui` 默认仍消费 `/v1/*`；可信 root_path 显式
  反映在配置中，签名仍以实际收到的原始 path+query 为准。反代契约见宿主文档。
- 默认演示身份与签名器禁用。无 inline、CDN、字体或自动模型调用。
  UI 语言切换不改变用户原文、摘录与元数据；旧确定性语言测试全部继续运行。

## 五层证据：分别统计，不相加

| 层 | 实际结果 | 原始证据 |
|---|---|---|
| L1 stdlib-only unittest | **210 passed / 67 skipped / 0 failed**；发现方法总数277 | l1-stdlib-only.log |
| L2 完整依赖 unittest | **274 passed / 3 skipped / 0 failed**；发现方法总数277 | l2-full-and-build.log |
| L2 独立 pytest 运行 | **274 passed / 3 skipped / 0 failed**；另76 subtests，不加入方法总数 | 同上 |
| L2 打包/静态检查 | build成功；43个源文件3.9 AST通过；核心 -S 阻断第三方导入通过；JS模块语法/差异检查通过 | 同上、verify_environment.py |
| L3 实际集成 | 本机临时 HTTP **PASS**；真实 Qdrant/embedding/语义链路 **SKIPPED 未配置**；真实反代 NOT_RUN | l3-live-integration.md、l3-local-http.log |
| L4 真实浏览器 | **NOT_RUN**，无真实浏览器操作；不冒充截图/点击验收 | l4-browser.md（精确复现及断点） |
| L5 架构复核 | **待验收架构师复核（B08收口）** | l5-architect-review.md |

运行解释器：Python 3.13.5。3.9检查是 AST 语法兼容，不是3.9运行时验证。
L2有一个 Starlette/httpx 测试客户端弃用告警，不是运行失败；未因此新增依赖。
67项L1跳过为64项HTTP可选依赖测试加3项未配置的live测试；不算通过。
原232项基线测试无回归；L2新增42项通过。不同工具/层/子测试统计不得累计成总分。

Wheel：`knowledge_sdk-1.2.0-py3-none-any.whl`

SHA256：`64af36e5fbe9394b065a9c35d0138fbca2ea5ab377fbfa5fc213a97862e0b000`

Wheel内四类静态资源、1.2.0版本和零核心依赖已核验。二进制产物不提交。
所有临时签名密钥随机生成且不输出；未读取任何现有 .env/凭据文件。

## 遗留偏差、原隐患与部署限制

1. L4和L5未完成，故仅提交验收，不宣称“全面验收通过”。附浏览器补测命令，
   不留常驻服务。Qdrant/在线语义/真实反代需要后续隔离环境补测。
2. 默认内存防重放限一个 app/worker。多worker必须明确共享 SQLite/ReplayStore；
   SQLite限同机本地文件系统，不提供多主机分布式保证。目录需受限权限，禁止
   在仍有效的认证窗口内删除/轮换掉防重放数据库。详见宿主契约。
3. 旧 seen 字典只为兼容保留，不提供并发保证；生产必须用 ReplayStore。
   dev_insecure 是既有显式不安全本地模式，不应用于生产。
4. Actor两字段、Agent/Purpose只保留可信签名上下文，不具备完整策略引擎、
   撤销或训练授权语义；不能把 purpose=eval_and_train 当成数据授权。
5. 正式宿主会话/目录 Actor hook、CSRF及失效机制只给接入清单，未越界实施。
   现有OpenAPI/docs公开行为保留，生产可在网关禁用；不是本阶段扩展的登录系统。
6. 为避免歧义，UI路径拒绝根、点段、空白、编码分隔、空段、/v1及子路径，
   同时拒绝与内置/docs、/redoc入口重叠；允许尾斜线后归一化。
7. 原有未跟踪 reports/ui-workbench/wheels/knowledge_sdk-1.1.0-py3-none-any.whl
   及ignored build/dist/venv保留但未提交。没有改动Mac、StratAI、OpenBot或
   3000/3001/8000/8002/8090/8091；没有碰任何已有Qdrant集合。
8. 撤回的历史105/27及在线PDF清零报告不构成本次证据。

## git diff --stat 与文件清单（相对真实起点）

```text
 docs/acceptance/v1.2/BASELINE_AUDIT.md        |   7 +
 docs/acceptance/v1.2/PHASE1_HANDOFF_REPORT.md | 150 +++++
 docs/acceptance/v1.2/l1-stdlib-only.log       | 398 +++++++++++++
 docs/acceptance/v1.2/l2-full-and-build.log    | 814 ++++++++++++++++++++++++++
 docs/acceptance/v1.2/l3-live-integration.md   |  21 +
 docs/acceptance/v1.2/l3-local-http.log        |  53 ++
 docs/acceptance/v1.2/l4-browser.md            |  47 ++
 docs/acceptance/v1.2/l5-architect-review.md   |  19 +
 docs/acceptance/v1.2/live_http_probe.py       | 107 ++++
 docs/acceptance/v1.2/verify_environment.py    |  47 ++
 docs/phase1-host-integration.md               | 100 ++++
 pyproject.toml                                |   2 +-
 src/knowledge_sdk/__init__.py                 |   2 +-
 src/knowledge_sdk/contracts/models.py         |   4 +
 src/knowledge_sdk/server/app.py               |  36 +-
 src/knowledge_sdk/server/auth.py              | 233 +++++++-
 src/knowledge_sdk/server/cli.py               |   8 +-
 src/knowledge_sdk/ui/routes.py                |  76 ++-
 src/knowledge_sdk/ui/static/workbench.js      |  10 +-
 tests/server/test_phase1_auth.py              | 291 +++++++++
 tests/server/test_phase1_mount.py             | 189 ++++++
 tests/ui/locale_harness.cjs                   |   2 +
 22 files changed, 2554 insertions(+), 62 deletions(-)
```

```text
docs/acceptance/v1.2/BASELINE_AUDIT.md
docs/acceptance/v1.2/PHASE1_HANDOFF_REPORT.md
docs/acceptance/v1.2/l1-stdlib-only.log
docs/acceptance/v1.2/l2-full-and-build.log
docs/acceptance/v1.2/l3-live-integration.md
docs/acceptance/v1.2/l3-local-http.log
docs/acceptance/v1.2/l4-browser.md
docs/acceptance/v1.2/l5-architect-review.md
docs/acceptance/v1.2/live_http_probe.py
docs/acceptance/v1.2/verify_environment.py
docs/phase1-host-integration.md
pyproject.toml
src/knowledge_sdk/__init__.py
src/knowledge_sdk/contracts/models.py
src/knowledge_sdk/server/app.py
src/knowledge_sdk/server/auth.py
src/knowledge_sdk/server/cli.py
src/knowledge_sdk/ui/routes.py
src/knowledge_sdk/ui/static/workbench.js
tests/server/test_phase1_auth.py
tests/server/test_phase1_mount.py
tests/ui/locale_harness.cjs
```

## 评审后才能继续

- 请专家审核原始证据和差异，独立裁决B08收口及缺口接受条件。
- 本轮没有实现 KnowledgePolicyEngine/PolicyRule、documents Schema v2、
  EvidenceAnchor/LayoutParser、MCP 或60条Benchmark，无新增核心runtime依赖。
- **Phase 2未解锁，不自动合main、不升级现有Mac服务、不创建生产发布。**
