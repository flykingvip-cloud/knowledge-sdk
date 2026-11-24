# PHASE4_HANDOFF_REPORT — Q1-M4 交接（以 t37u 唯一执行任务书为准）

## 1. 分支与可核验来源

- Review branch: `feat/phase4-mcp-benchmark`。
- 预期 Branch URL（**推送被远端拒绝，尚未创建，不是可访问交付链接**）: https://github.com/flykingvip-cloud/knowledge-sdk/tree/feat/phase4-mcp-benchmark
- 真正起点 / 已过审 Phase3: `83f4a0dd6b859905dbb73003d366a37017c6eea6`。
- 实现与测试代码终点: `502cf6e87943dfca55f21eddd8a5e58759af9d07`。
- 本轮最终原始证据提交: `234b95fb97b16d79316f881882bde7231e467ba8`。
- 最终报告提交: 本文件最后交接修订提交；不在文件内伪造自引用 hash。
  精确解析命令：`git log -1 --format=%H -- docs/acceptance/v1.2-phase4/PHASE4_HANDOFF_REPORT.md`。
  对外最终交付另给该完整 SHA；报告/证据后继提交不改变已实测 src/tests 代码。
- main 审计仍为 `0ed15b93e2a6eed893369ca81524909c328c8b5c`；不合 main、不建 PR、无 tag/release/部署。
- 从真实本地已有仓库开发，无 clone/cloud coding。原有未知 `reports/` 保留且不提交。
- 实现文件清单、`git diff --stat` 和完整提交序列：[implementation-diff-stat.txt](implementation-diff-stat.txt)。

### 指令优先级修正与历史保留

t37u 唯一任务书覆盖先前父代理派工中的 SDK/默认用途/整包拒绝建议。
收到修正前的未推送实验及其原始日志保留在 Git 历史和
`superseded-parent-brief/`，该目录明确标为 **SUPERSEDED**，不参与本轮统计。
当前内核没有第三方 MCP SDK，默认 internal + keyword，pack 采用安全子集与统一 excluded_count，
并按新任务书提供强类型 EvidenceIssue 和双传输。修正完成前没有推送旧架构。
当前验收使用全新 `.venv-phase4`，确认未安装外部 `mcp` distribution。

## 2. 任务0–4实施映射

| 任务 | 已实现与实际验证 | 主要提交 |
|---|---|---|
| 0 scope/DDL收口 | filters/scope/additional_scope 的 KB/doc 交集及 space_types 传入绑定 SQL；空交集不查询；550其他KB+3目标全召回且预算未耗尽；原8步与Python双scope复核保留；_DERIVED 两静态列 DEFAULT ''，backfill/sync不改 | `3527589` + `7ec59ce` |
| 1 流内纠偏 | frozen PolicyContract EvidenceIssue/IssueType、拒非法类型/控制字符/状态/UTC时间/URI；encode/decode/公共导出；put/get/list_issue tenant安全；report/list Local/Http；POST /v1/issues 与 /v1/issues/list；逐条实时READ与脱敏；只写队列表 | `4fb0d82` + 后续安全收口 |
| 2 可选MCP | tools/protocol/gateway/server/__main__/__init__；stdlib JSON-RPC2；真实换行stdio与可选HTTP /v1/mcp；可信HMAC+轮换+shared ReplayStore；服务端default_mcp_purpose internal；强Agent；严格未知参数拒绝；真实引用回执；子集pack | `c985adb` + `cf30cf2` |
| 3 exactly60黄金与CI | golden_cases_v1.jsonl 五字段、精确20/10/10/10/10；runner.py --json；test_golden_benchmark.py；现有CI显式硬门禁；强ACL/范围SQL/RRF/500预算/锚点/身份注入/stdio真实子进程 | `3e8856d` + `502cf6e` |
| 4 分层证据与交接 | 本目录L1–L5、60case报告、真实HTTP/stdio探针、wheel独立解包入口验证；docs/mcp-integration.md提供<=10min沙箱配置与生产安全手册 | 本证据提交 + 本报告 |

版本仍1.2.0；业务 schema仍2；核心 dependencies=[]。
`mcp` extra 精确为 `fastapi>=0.100,<1`、`uvicorn>=0.23,<1`。
console script 为 `knowledge-sdk-mcp = knowledge_sdk.mcp.server:main`。
未增加业务表/列或迁移版本，未改前端视觉/语言契约。

## 3. 分层真实结果（不混计、不把skip算pass）

| 层 / runner | Passed | Skipped / 未测 | 真实原始证据 |
|---|---:|---|---|
| L1 unittest, python3 -S -W error::ResourceWarning | 350 | 96；446 discovered | l1-stdlib-only.log |
| L2 全依赖 unittest, 同严格ResourceWarning | 443 | 3 live Qdrant；446 discovered | l2-full-and-build.log |
| 独立 pytest | 443 | 3；另167 subtests，不加入方法数 | l2-full-and-build.log |
| 独立60黄金 CLI | 60/60 | 0；不是60个unittest方法 | benchmark-60-run.log / benchmark-60-report.json |
| L2 build / AST / -S blocker / wheel入口 | PASS | 实际Python3.9 runtime未运行 | l2-full-and-build.log / verify_wheel.py |
| L3 本地真实HTTP + stdio | SELF_TESTED PASS | 在线语义/真实proxy/外部人工client另列未运行 | l3-local-http-stdio.log / l3-live-integration.md |
| L4 browser | NOT_RUN | 无前端改动、未使用browser/DOM mock | l4-browser.md |
| L5 | PENDING_EXTERNAL | 待独立架构师验收，不自封B06/Q1全面关闭 | l5-independent-review.md |

L1 skips =92个可选HTTP方法 +1个可选真实HTTP-wire方法 +3个live Qdrant方法。
L2仅跳过3个未在本次隔离环境启用的live Qdrant方法；不触碰现有collections。
全回归保留Phase3既有395方法/392passed3skipped基线，新增51方法；没有删除旧安全断言。
无 ResourceWarning / Exception ignored / unraisable 诊断，无 license弃用build告警。
完整依赖环境有1类已安装 Starlette/httpx TestClient 弃用告警，原样记录，未压制或声称全零告警。

### 命令与兼容性

```sh
PYTHONPATH=src python3 -S -W error::ResourceWarning -m unittest discover -s tests -t . -v
PYTHONPATH=src .venv-phase4/bin/python -W error::ResourceWarning -m unittest discover -s tests -t . -v
PYTHONPATH=src .venv-phase4/bin/python -W error::ResourceWarning -m pytest -q
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.runner --json
.venv-phase4/bin/python -m build
.venv-phase4/bin/python docs/acceptance/v1.2-phase4/verify_wheel.py
PYTHONPATH=src .venv-phase4/bin/python -W error::ResourceWarning docs/acceptance/v1.2-phase4/live_mcp_probe.py
```

原始日志含准确实际命令、实现SHA、Asia/Shanghai时间和退出码；测试进程显式不启用live URL/model变量。
实际Python3.13.5；57个src文件与4个tests/benchmark文件通过Python3.9 AST，**不冒称真实3.9运行**。
独立解包wheel在 -S + 第三方导入阻断钩子下运行四工具和真正console-entrypoint stdio。
wheel资源包含6个MCP模块与原UI资源；不含已移除的官方SDK handlers/transport文件。

Wheel: `knowledge_sdk-1.2.0-py3-none-any.whl`，二进制不提交。
SHA256: `68b73729a05382b2e6a0c978581da32bf787cb6036458584cddcceb1eaddcfc4`。原始证据文件hash见 [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)。
GitHub现有CI已在本地代码接硬门禁；因OAuth workflow权限不足推送被拒，远端未接收该修改，未运行本分支CI。

## 4. exactly60 离线黄金指标

| 指标（明确被测分母） | 实测 |
|---|---|
| case / groups | 60/60；G1 20/20，其余G2–G5各10/10；0skip |
| acl_violation_rate | 0/20 G1安全场景 =0 |
| refusal_accuracy | 10/10 G2指定无证场景 =100% |
| implicit_model_calls | 0；G1缺hook ask及G2真实spy调用计数 |
| reanchor_accuracy | 10/10 G4离线fixture场景 =100% |
| mcp_pass_rate | 10/10 G5协议/回执/队列/鉴权/stdio场景 =100% |
| 运行时身份注入 | 36/36 blocked：9字段×4个带合法必填参数的tool，含正例控制 |
| 正例误拒 / 安全断言失败 | 0 / 0 |
| 固定fixture Recall@requested_k | 7个适用fixture均1.0；550噪声场景k=3，其余k=5；不宣称在线语义收益 |

G2为：空库、无关内容、有匹配但无权、仅archive、仅revoked、仅L2draft、仅过期、仅缺hook、
低于min_score、检索后生成前撤权。额外有权有效extractive正例，不能靠一律拒绝通过。
G3包含90%拒绝、混合撤回/归档、scope SQL真实下推、hybrid stub/RRF确定性、预算及脱敏limit；
跨批evaluated_keys只评估一次，硬500+身份lookahead不扩大。
G4 PDF仅宿主离线bbox插件，不是实际PDF/OCR；CSV科学原文/列与单位保真、重锚三状态、人工权限、
quote hash与敏感metadata、历史version pin与撤权均实际运行。
G5在 -S 中的HTTP鉴权case复用生产GatewayAuthenticator.authorize_http真实HMAC/重放决策，
不是写死401的mock；真正FastAPI HTTP wire独立在L3验证。
完整每case结果：[benchmark-60-report.json](benchmark-60-report.json)。

## 5. 接口与安全选择 / 已知边界

- HTTP默认不开放MCP，enable_mcp=True方有路由；无签名/重放401+no-store。Agent强类型预检，
  LLM body中的actor/self/agent/purpose/policy_context以及其他未知工具字段均拒绝。
- 缺签名Purpose用服务端internal；云端必须配置external，可信网关不得把LLM用途转为签名头。
  已签合法Purpose优先；仍与当前Agent/document rights相交，不会触发模型调用。
- stdio必须合法环境Actor，无默认admin；可选Agent同租户；固定单用户沙箱不是宿主SSO实现。
- search默认keyword；vector/hybrid无后端明确错误。没有query rewrite/隐式embedding/model。
  receipts来自真正reference/consume/attach；consumer=mcp_agent，可信agent_id或mcp_stdio；
  used_by_stage=task_id。标题/quote/selector/metadata遵从当前脱敏视图。
- pack按唯一任务书保留安全子集，全部拒绝原因只汇总excluded_count，不返回被剔URI/标题。
  只有入选源参与派生交集；所有必要profile顺序合并，缺hook不回退明文。
  普通excerpt按总预算截断后生成真实新回执；不足容纳完整quote的anchor整条省略并truncated，
  不虚称消费残缺anchor。预算省略不计权限排除数；无实际返回item则no_authorized_evidence。
  不提供pack_id存储或Q2不可变EvidencePack。
- verify无hash仅证明当前可用/完整性，不证明用户理解；无权/不存在/撤回统一denied与null latest，
  不形成存在性oracle。历史/新版本与脱敏后的hash实时复核。
- report仅写evidence_issues(status=open)，返回queued_for_review说明未改正式知识；
  descriptions是数据，不执行/不训练/不自动发消息。list逐条实时READ+description脱敏，缺hook过滤，
  冲突来源撤权也过滤；不借反馈接口获其他租户正文。
- 重试新nonce可能产生重复待办，未承诺exactly-once。同步Local薄委托与有界预算是Q1范围，
  未新增SSE/resumption/OAuth或超出任务书子集的广泛MCP一致性认证。
- scope已对SQLite关键词通道做KB/doc/space type粗滤；custom MetadataStore保留旧接口fallback。
  向量后端无原生scope过滤接口时不虚构能力，仍受当前SQLite权威、scope复核与500上限；
  不宣称已解决任意外部vector-only后端的scope外候选饥饿或在线性能。
- same-origin宿主登录/CSRF/会话失效映射是集成方责任；proxy签名必须匹配rewrite后的真实ASGI target。
  多worker必须相同独立replay DB与轮换链，非多主机NFS方案。详见 [MCP integration](../../mcp-integration.md)。

## 6. Q1退出门禁六项真实核对（工程自测 ≠ 外部全面验收）

| 核对项 | 本轮状态 | 尚待外部证据 |
|---|---|---|
| 1 权限/租户/治理硬边界，ACL违规0 | COMPLETED / SELF_TESTED，G1及既有矩阵 | 独立安全/架构师复核 |
| 2 无证拒答100%、零隐式模型 | COMPLETED / SELF_TESTED，10指定场景+正例 | 不推论所有真实业务问题 |
| 3 强ACL补取、scope下推与有界预算 | COMPLETED / SELF_TESTED，G3 | 在线语义/真实向量性能未测 |
| 4 物理anchor/重锚状态与受控确认 | COMPLETED / SELF_TESTED，离线G4 | 真实PDF/OCR能力未证实 |
| 5 MCP四工具、零LLM身份、真实回执、队列不改正式文档 | COMPLETED / SELF_TESTED，G5+真实HTTP/stdio | B06/L5独立验收待审 |
| 6 外部设计伙伴/企业真实客户端<=10min及真实环境 | PENDING_EXTERNAL / NOT_RUN | 外部Claude/Cursor人工操作、伙伴/企业接入及生产proxy证据缺失 |

L4 NOT_RUN；L5待独立专家。没有把用户批准推进阶段当成本轮通过，也没有自封Q1全面PASS。
无在线Qdrant/embedding/外部模型调用；没有改生产数据库或任何Mac/既有服务，临时worker已全部停止。
main/Release/Tag/生产部署未操作；MCP以外统一来源选择器UI、Q2治理/审批/不可变pack、Outbox/Postgres、
模型训练等仍未解锁。本次仅尝试正常推送指定独立审查分支，但因下述权限门禁被拒，当前仅本地交付。


## 7. 交付阻塞：GitHub workflow权限（未绕过）

2026-11-24 21:14 Asia/Shanghai，唯一一次正常push：
`GIT_TERMINAL_PROMPT=0 git push -u origin HEAD:refs/heads/feat/phase4-mcp-benchmark`
被GitHub远端拒绝：

> refusing to allow an OAuth App to create or update workflow `.github/workflows/tests.yml` without `workflow` scope

原始错误见 [push-blocked.log](push-blocked.log)。只读复查确认main/Phase3未变且Phase4远端分支尚不存在。
没有删掉CI门禁来逃避权限、没有重写提交、没有换API/SSH/Mac身份重试，也没有抓取凭据。
当前全部实现、测试、原始证据与报告完整保留在本地 `/workspace/knowledge-sdk` 的独立分支。
本报告GitHub链接均是待成功推送后的预期地址，不能当作已经发布的URL。
需要具有合法workflow写权限的正常GitHub授权，并在用户确认后才可重试该同一分支push；
本执行器在已知远端权限拒绝处停止，未扩大权限或改动主分支。
