# Q1-M2 / Phase 2 交接报告 — Knowledge Policy Engine

状态：工程实施、分层自测与实证归档完成，提交独立验收；**不是五层全部通过**。
版本仍 **1.2.0**。L5待架构师独立复核，第三阶段仍未解锁。

## 1. 授权、分支与完整 SHA

本轮依据用户“阅读附件，按照这个执行”的第二阶段授权；任务书记载的
Phase 1独立工程验收PASS是Q1-M2执行门禁，不改变历史在线语义/反代/浏览器缺口。

- 原 Phase 1 基线：`602373fce3b40ba87b7d94894a5b85cc634e5ac9`。
- Task 0 功能收尾原子提交：`8d8c97d779bb193dc90b7d6a3dac18d9f016b919`。
- Phase 1 收尾最终提交（仅追加最终证据）：`8cbd769afb2e22b2f317ba7a1fb3b265ae35651b`。
- Phase 2 真实起点：`8cbd769afb2e22b2f317ba7a1fb3b265ae35651b`，与最终 Phase 1 分支一致。
- Phase 2 **实现终点**：`dcb8a53da36e6ebf695e3613fa3c577e3a531e56`。
- Phase 2 **最终原始证据归档 SHA**：`38c84ff973ce397a21eafdd9c7efbe28623b8941`。
- 本报告是上述证据之后的纯报告提交；不编造包含自身的循环 hash。
  交付分支最终HEAD以最终执行回执及 `git rev-parse feat/phase2-policy-engine`
  为准；它与证据SHA的差异仅为本报告，不是实现变更。
- main：`0ed15b93e2a6eed893369ca81524909c328c8b5c`，保持不动。

分支链接：
- <https://github.com/flykingvip-cloud/knowledge-sdk/tree/feat/phase1-v1.2-baseline>
- <https://github.com/flykingvip-cloud/knowledge-sdk/tree/feat/phase2-policy-engine>

Phase 2审查差异：
<https://github.com/flykingvip-cloud/knowledge-sdk/compare/feat%2Fphase1-v1.2-baseline...feat%2Fphase2-policy-engine>

未创建PR、未合main、未建生产Tag/Release、未强推或跳过hooks。

## 2. Task 0 收尾与顺序说明

先在Phase 1分支修补、回归、提交并普通push `8d8c97d`，然后开展Phase 2。
修补包括Replay SQLite连接确定性关闭、bool参数拒绝、大小写扩展头与重复头、
health动态版本、模块docstring恢复和SPDX license。构建工具setuptools最低版本
由61提高到77.0.3以支持PEP 639；这是构建依赖，不是核心运行时依赖。

最初L1和L2快照在gc.collect()时发现**原Phase 1测试自身**的两处SQLite连接未关闭，
测试连接也在原子功能提交中修好；最终L2已以ResourceWarning=error完整通过。
初始日志保留，不伪装为无告警。后来追加单独严格L1最终记录，作为纯证据提交
`8cbd769` 正常push；仅将**尚未推送**的Phase 2实现提交重放到该最新基线。
没有重写任何已推提交，没有覆盖未知工作树。Task 0因此为“原子功能修补+证据补交”
两个提交，而不是把补充记录悄悄塞进已推提交。

最终收尾证据（旧docs/acceptance/v1.2/历史不覆盖）：
- `docs/acceptance/v1.2-closeout/l1-final-warning-strict.log`：215 passed / 68 skipped；
  -S、ResourceWarning=error、gc回归，无ResourceWarning/unraisable输出。
- `docs/acceptance/v1.2-closeout/l2-full-and-build.log`：unittest 280 passed / 3 skipped；
  独立pytest 280 passed / 3 skipped，不累计；完整构建成功，无license表弃用告警。
- 初始带原测试资源告警的L1/L2日志仍保留且在README明确标记为初始快照。

## 3. 任务 1–4 映射

| 任务 | 实现与边界 | 提交 |
|---|---|---|
| 1 契约 | Purpose/Action/Effect/Tier、冻结Agent/Rights/Rule/Context/Decision；严格字段/时区/不可变快照；KB与Doc增量JSON字段；公开导出及编解码 | df399cc |
| 2 决策与脱敏 | 八步短路、显式deny优先、空间硬边界、个人ACL红线、Agent收窄、用途/权利取交集、所有脱敏约束保序合并；派生交集；无明文降级Registry/可选Regex | 2bbc50a |
| 3 全链路 | Local/Http Client、SEARCH候选SQLite复核、所有正文/历史/块/元数据交付、引用/回执、ask生成前复核、可信HMAC上下文注入与body禁入 | 4f0d53c |
| 4 矩阵、回归与修复 | 新增68项确定性方法；严格Agent在nonce消耗前预检；文档级WRITE deny；公共Protocol补齐；实际HTTP探针；同优先级规则保配置顺序 | dcb8a53 |
| 最终实证 | 分开的L1/L2、wheel/AST/-S导入钩子、真实临时HTTP、L3/L4缺口与L5待审说明 | 38c84ff |

完整接入说明：`docs/phase2-policy-contract.md`。任务4验证发现的边界加固已复测。

### 默认 rights 冲突裁决

任务书前段的“两purpose默认”与Step 7明示修正不一致。本实现**遵循后文明示修正**：
默认READ + GROUND_INTERNAL_LLM + EXPORT，allow_export=True；外发与训练默认拒绝。
显式allowed_purposes和各bool仍取交集，单设allow_external_llm=True不自动放开用途。
相应契约、引擎与HTTP测试均覆盖，未借此授权实际外发或训练。

## 4. 五层结果（每次运行独立，不合并统计）

| 层 | 原始结果 | 日志/证据 |
|---|---|---|
| L1 stdlib-only unittest | **267 passed / 84 skipped / 0 failed**；方法总数351 | l1-stdlib-only.log |
| L2 全依赖 unittest | **348 passed / 3 skipped / 0 failed**；方法总数351，ResourceWarning=error | l2-full-and-build.log |
| L2 独立pytest | **348 passed / 3 skipped / 0 failed**；另126 subtests，不并入方法数、不累加unittest | 同上 |
| L2 构建/依赖/语法 | wheel成功；46个src源文件3.9 AST通过；核心-S禁止第三方导入钩子通过；METADATA无核心依赖 | 同上 |
| L3 真实集成 | 本地空闲端口53287真实HTTP策略/脱敏通过，进程已停止；在线Qdrant/embedding/语义 **SKIPPED 未配置**；真实反代 **NOT_RUN** | l3-live-integration.md / l3-local-http.log / live_http_probe.py |
| L4 真实浏览器 | **NOT_RUN**，本轮无视觉功能改版；既有Node VM/HTTP测试不冒充浏览器 | l4-browser.md |
| L5 架构审查 | **待验收架构师独立复核**，不自封通过 | l5-architect-review.md |

L1跳过：81项可选HTTP方法+3项未配置live方法；跳过不计通过。
Phase 1的274项行为回归继续覆盖，Task 0加6项、Phase 2加68项；这只是方法来源说明，
不是把不同层/不同工具分数相加。原Phase 1人工探针中一项request.state测试的预期JSON
按Q1-M2强类型要求更新为AgentIdentity的完整默认字段；未删除任何拒绝/隔离断言。

运行解释器Python 3.13.5；3.9仅AST语法兼容验证，**未声称执行3.9运行时测试**。
唯一测试告警为既有Starlette/httpx测试客户端弃用提示；没有ResourceWarning或SPDX
license表弃用告警。没有为消告警新增运行依赖。核心 dependencies=[] 保持。

Wheel：`knowledge_sdk-1.2.0-py3-none-any.whl`

SHA256：`2a63dfd2e8b8ef2a900df0ccbd0bd4d5564850a3ac6deeaeda7285f5c97f97b1`

Wheel版本/静态资源/零核心依赖已验证；二进制不提交，保存文件名/hash即可。

## 5. 关键安全保证与明确偏差/限制

1. 无业务新表或迁移；user_version=1。规则由内存/构造参数注入；旧无新增字段JSON
   可读。Schema v2、EvidenceAnchor/LayoutParser、PDF/CSV锚点、MCP、60黄金Benchmark、
   IterativeAuthorizedFetch和Workbench新视图均未实现。
2. 所有签名agent/purpose只从HMAC头进入；保留旧六行签名和verify_headers返回Actor。
   强Agent预检在nonce消费前，未知字段/非法类型401；body五种可信字段注入400。
   签名密钥未进入响应/日志，没有读取任何已有.env或凭据文件。
3. 缺脱敏hook时search不返候选、直接读抛明确拒绝、consume回执denied且reason准确、
   ask拒答且不调generator。hook异常/错型不回明文，不链出含敏感文本的原异常。
   正文、历史版本、chunks、标题/文件名/描述性元数据均检查；原文存储不被覆盖。
4. 脱敏视图中的hash/offset描述实际交付内容，不伪称原始上传指纹；blob路径不返回。
   引用/回执以当前脱敏来源验真，旧明文ref不能绕过新权利。管理rights接口不变更ACL，
   且抑制正文相关描述字段，不能借管理响应读取本不可见内容。
5. 上传与读取分离：可成功保存当前不可交付资源，但上传响应仅返回内容字段清空的
   版本回执（包括text/hash/filename/blob），不因失败脱敏而回明文。正常旧上传行为不变。
   普通上传者不能设置rights/发布/有效窗；受控库新语义版本默认draft；未提供控制字段
   保留旧值，None表示不更新，不提供隐式清空有效窗的旁路。
6. 规则优先级只解决同层匹配顺序；所有有效脱敏约束保留。personal_only不被规则放开；
   legacy private额外授权保守要求明确doc+user。未知条件直接拒绝定义，没有条件DSL。
   DENY规则required_clearance不提供低密级豁免；规则部门只匹配直属，旧细ACL继承保留。
7. ask对所有来源交集、按当前SQLite重新构造安全证据并在hooks后立即再次检查决策；
   搜索到生成前撤权/改rights/副作用hook均测试不调用generator。若SEARCH与READ的
   脱敏表示无法共同通过引用验真，保守拒答，不删除某项义务。真实分布式并发事务、
   插件运行中的撤权不能“撤回已调用的模型”；生成后也复核并抑制失权答案。
8. hooks和既有parser/embedding/vector插件是可信宿主代码，不是沙箱；必须确定性、
   无副作用、摘要安全、regex经审核。未配置真实模型/向量后端；没有认证任意外部
   embedding提供商的数据治理能力，也不把purpose当成训练同意或药研合规证明。
9. Phase 1原L3/L4缺口不改写。无新真实浏览器/反代/线上语义证据；Task 0补证顺序和
   一项内部typed-state断言适配已透明记录。L5由独立架构师裁决。
10. 仅既有box仓库本地开发；未clone、未用云端。Mac工作树/8091/PID、Docker8090、
    StratAI/OpenBot、3000/3001/8000/8002及任何既有Qdrant集合均未触碰。
    原未跟踪reports/及wheel保留但未提交；构建产物/venv/临时DB/密钥未入库。

## 6. Phase 2差异文件清单

相对最终Phase 1收尾基线 `8cbd769afb2e22b2f317ba7a1fb3b265ae35651b` 的staged diff：

```text
 .../v1.2-phase2/PHASE2_HANDOFF_REPORT.md           | 194 ++++++
 docs/acceptance/v1.2-phase2/l1-stdlib-only.log     | 362 +++++++++++
 docs/acceptance/v1.2-phase2/l2-full-and-build.log  | 722 +++++++++++++++++++++
 docs/acceptance/v1.2-phase2/l3-live-integration.md |  34 +
 docs/acceptance/v1.2-phase2/l3-local-http.log      |  69 ++
 docs/acceptance/v1.2-phase2/l4-browser.md          |   9 +
 docs/acceptance/v1.2-phase2/l5-architect-review.md |  23 +
 docs/acceptance/v1.2-phase2/live_http_probe.py     | 157 +++++
 docs/phase2-policy-contract.md                     | 145 +++++
 src/knowledge_sdk/__init__.py                      |   4 +
 src/knowledge_sdk/client/base.py                   | 130 +++-
 src/knowledge_sdk/client/http_client.py            |  17 +-
 src/knowledge_sdk/client/local.py                  | 343 +++++++---
 src/knowledge_sdk/contracts/models.py              |  27 +-
 src/knowledge_sdk/contracts/policy.py              | 241 +++++++
 src/knowledge_sdk/contracts/receipts.py            |  28 +-
 src/knowledge_sdk/permissions/engine.py            | 157 +++++
 src/knowledge_sdk/permissions/redaction.py         |  72 ++
 src/knowledge_sdk/retrieval/hybrid.py              |  24 +-
 src/knowledge_sdk/server/app.py                    |  38 +-
 src/knowledge_sdk/server/auth.py                   |   3 +-
 tests/permissions/test_phase2_policy_engine.py     | 513 +++++++++++++++
 tests/server/test_phase1_mount.py                  |   4 +-
 tests/server/test_phase2_policy_http.py            | 153 +++++
 24 files changed, 3304 insertions(+), 165 deletions(-)
```

```text
docs/acceptance/v1.2-phase2/PHASE2_HANDOFF_REPORT.md
docs/acceptance/v1.2-phase2/l1-stdlib-only.log
docs/acceptance/v1.2-phase2/l2-full-and-build.log
docs/acceptance/v1.2-phase2/l3-live-integration.md
docs/acceptance/v1.2-phase2/l3-local-http.log
docs/acceptance/v1.2-phase2/l4-browser.md
docs/acceptance/v1.2-phase2/l5-architect-review.md
docs/acceptance/v1.2-phase2/live_http_probe.py
docs/phase2-policy-contract.md
src/knowledge_sdk/__init__.py
src/knowledge_sdk/client/base.py
src/knowledge_sdk/client/http_client.py
src/knowledge_sdk/client/local.py
src/knowledge_sdk/contracts/models.py
src/knowledge_sdk/contracts/policy.py
src/knowledge_sdk/contracts/receipts.py
src/knowledge_sdk/permissions/engine.py
src/knowledge_sdk/permissions/redaction.py
src/knowledge_sdk/retrieval/hybrid.py
src/knowledge_sdk/server/app.py
src/knowledge_sdk/server/auth.py
tests/permissions/test_phase2_policy_engine.py
tests/server/test_phase1_mount.py
tests/server/test_phase2_policy_http.py
```

## 7. 后续门禁

请专家依据源码与各层原始日志独立验收Q1-M2/B03，并明确真实在线/浏览器缺口的
接受条件。没有自动合并、生产升级或后续阶段自动实施；**第三阶段仍未解锁**。
