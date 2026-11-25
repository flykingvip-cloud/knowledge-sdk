# Q3-M2 / SDK-21 工程交接报告

> 2026-11-25，Asia/Shanghai。仅离线固定集工程实证；未取得本轮独立 L5 退出结论。
> 全部最终日志、双引擎基准、CI、哈希与自有基础设施清理已由归档脚本逐项断言核验。

## 1. 起点、授权与提交

- 按 t55u 新任务书（150 行完整读取）执行 Q3-M2，沿用明确 LOCAL BOX 覆盖，未启动 CloudAgent。
- 起点 `69b6c986251161ca02b1e77b0806e2c8861a30b6`，新分支 `feat/q3-phase2-rerank-eval`。
- **最终源码/测试 SHA：`a57a4b9adda74f3ef6e102e7179b80dd56280021`**。之后提交只归档文档/证据。
- 源码 Python 3.9/ubuntu-22.04 与 3.12/ubuntu-24.04 × core/http-and-package **四作业真实全绿**：
  https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45541282637 。
- 前一完整矩阵也成功（711701b）：https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45540769692 。
- 最终归档 HEAD 由本报告所在 Git 提交和外部 delivery-receipt / 回传给出；不在提交内容中伪造自引用 Git SHA。
- main 保持 `b953c9922cc1096e0e88455dab6746c01a9d27f9`；v2.0.0 对象保持
  `4afc1d71f9f5583d93c28f3f4380544a4e5fcc46`，peeled 为上述 main；Q3-M1 远端仍为 69b6c98。
  本轮没有修改这些 refs。t54u 的 M1 独立审计/假设接受是 **OWNER-PROVIDED**，不是本轮实施侧自称独立审计。

原子提交轨迹：36d7892（冻结候选/协议/双语重排）→ 923186d（独立校准/注册策略）→
1042e7c（受控检索/HTTP/MCP/Runtime）→ e21f41a（冻结数据/配置与真实成对评测）→
711701b（对抗/双引擎/真实 HTTP 测试）→ a57a4b9（内部检索入口阈值与有界得分序列 Fail-Closed）。

## 2. Tasks 1–3：实现及安全闭环

- `RerankCandidate` 仅任务书九字段、frozen、严格构造/序列化；Protocol.score 与 apply_reranker
  强制等长、有界 Sequence、有限 float，拒绝 bool/int/NaN/Inf，异常不回传 scorer 正文。
- 确定性双语词法重排使用共享英文/CJK tokenization、覆盖率、标题、短语/邻近、饱和密度与小幅名次先验；
  权重显式可校验，全序键 `(-score, doc_id, version, chunk_id)`；没有模型、网络或按 family/标签硬编码排序。
- 可选适配器仅显式本地 CallableRerankerAdapter，不带 URL、自动模型加载或隐式远程发送逻辑。
- 四通道独立冻结校准配置，支持 minmax / 稳定 sigmoid / 单调 piecewise_quantile 与严格 to_dict/from_dict；
  显式阈值仅统计已授权、已脱敏 accepted 的过滤数；零值和空集不被当作无限预算/全部范围。
- 顺序严格为既有批次 scope → current version/L2 published → 8 步 PolicyEngine → RedactionRegistry →
  make_excerpt → accepted window → 重排/校准/拒答。未把未授权对象、原始正文或 denied count 提供给 scorer。
- 不增强时保留旧 RRF/limit 语义；增强分数 raw/rerank/calibrated 的精确定义见 docs/rerank-evaluation.md。
  Window 受 500 cap 约束；无跨请求/租户/代际结果缓存；空候选不调用 scorer/calibrator。
- Local / HttpKnowledgeClient 搜索、Runtime 查询快照与 MCP search_evidence 支持命名策略；HTTP 仅注册名称，
  拒绝任意对象/代码/URL 和非法类型/阈值，即使 none scope / 无命中也拒绝；成功和错误均 no-store。
- HTTP 同时接受命名 calibrator_id，明确是消解任务书简短 HTTP 列表遗漏、遵循较早双客户端一致性要求的 M2 选择。
- Runtime/MCP 仍先验证任务所有者、scope、档案、主体代际及全部六族即时撤权，再进入任何打分；
  真实 HTTP 九变体均在 dispatcher 刷新前拒绝，计数 probe 证明撤权后未执行 ranker。

## 3. Task 4：防标签泄漏、真实排名与实际指标

`tests/retrieval/eval_dataset_q3_m2.jsonl`、独立 corpus 与全局 config 在 **e21f41a 首次测量前提交并 SHA 冻结**。
32 个不同 doc_family：train 4 / calibration 4 / evaluation 24；评测 18 个正例、6 个拒答例。
覆盖中英文、混排、编号/短语词序、长文关键词稀释、跨版本、低置信/无证、跨租户、deny_users、L2 草稿、高密 ACL。
数据与配置在测得增益后未改动；未用 eval 标签拟合权重、校准锚点或按 case 调阈值。
同一 .60 阈值、100-entry window 用于全部测量 case，family/相关性标签从未传给排序或校准函数。

两个 arm 对同一真实 corpus / index / Actor / Purpose 调用 LocalKnowledgeClient.search；
SQLite 实际 FTS5 + 本地真实 cosine，PG 实际 tsvector + pgvector，全部使用显式离线非语义 HashEmbedder。
Fixture 对实际向量记录做前后指纹相等校验；Evaluator 固定锁/事务视图并复核业务语料指纹。
不是 callback 伪造输出，也不是预设排序/指标；原生后端基线差异如实保留。

| 引擎 | NDCG@3 baseline → candidate | MRR baseline → candidate | ΔNDCG | wins/ties/losses（全部 24） |
|---|---|---|---|---|
| SQLite | 0.774457072 → 1.000000000 | 0.694444444 → 1.000000000 | +0.225542928 | 11/13/0 |
| PostgreSQL + pgvector | 0.794960974 → 1.000000000 | 0.722222222 → 1.000000000 | +0.205039026 | 10/14/0 |

两引擎共同实测：
- Recall@3：1.0 → 1.0（18 个有相关性标签正例）；
- Citation precision：0.281250 → 0.580645（18/64 → 18/31）；
- 所有返回引用的真实 reference + consume receipt/hash/policy 验证：baseline 64/64、candidate 31/31 有效授权；
- Refusal accuracy：19/24 = 0.791667 → 24/24 = 1.0；false refusal：0/18 → 0/18；
- ACL violations / forbidden hits：两 arm 均 0，分母分别为实际返回 64 / 31；
- implicit_model_calls：实际 provider/network 边界监测为 0，不是 report 中硬编码常量；
  负向对照实际尝试已拦截 urllib 调用并产生非零计数，验证 gate 必须失败；
- 两引擎 gate_passed=true，family_breakdown 与每 case 真实 doc_ids、指标、delta 均保留在 JSON。

搜索延迟实测（毫秒；不含随后引用检查时间；P50/P95 插值）：

| 引擎 | baseline P50/P95 | candidate P50/P95 |
|---|---|---|
| SQLite | 1.843/2.852 | 16.905/17.774 |
| PostgreSQL | 9.062/12.928 | 141.094/153.595 |

**候选更慢，不宣称性能提升**：受控候选池扩大导致更多授权/摘要/打分成本。
这些数据只适用于当前小型、特意包含词序/稀释挑战的固定离线集，不是泛化、线上模型、生产召回率或 SLA 证明。

指标分母：Recall/NDCG/MRR 排除没有 relevance label 的拒答案例；DCG 为分级相关性、同一文档首出现去重。
Citation precision 为相关且真实有效授权的引用 / 全部返回命中；Refusal accuracy 用全部 case，False refusal 用正例。
零分母明确记 0.0 并保留计数，不伪造完美得分。报告/配置/用例严格冻结序列化，to_dict 返回副本。

## 4. Task 5：门禁与归档

- L1：纯 `python3 -S -W error::ResourceWarning`，最终 894 项，617 通过、277 可选依赖/PG 跳过，0 失败、0 警告。
- L2：全依赖 unittest 894 项，891 通过、3 在线 Qdrant 跳过；pytest 同样 891 通过、3 跳过。
  pytest 的第三方 Starlette/httpx 弃用警告如最终日志记录，非 ResourceWarning，未通过隐藏警告伪称零警告。
- Python 3.9 AST 覆盖 175 个 src/tests/本阶段脚本；python -m build、Wheel RECORD、解包 -S 下
  重排/校准/拒答/Runtime/撤权冒烟全部通过。仅使用现有缓存 setuptools 构建依赖离线安装；没有为构建访问外网。
- 双引擎默认 115/115、legacy75=75/75、legacy100=100/100 全通过；原黄金七个文件 + runner.py
  与 69b6c98 字节级相同，未增加 G10、未替换原断言；核心 dependencies=[] 与整个存储/schema 文件未修改。
- L3：每引擎 80 组真实 loopback 签名 HTTP 搜索、MCP、Runtime 及全部六族九变体撤权断言；
  非超级用户四张 v5 表 foreign context 0 行、ENABLE/FORCE RLS 通过。旧 Runtime/并发/权限回归随全套测试复跑。
- L4：NOT_RUN_NO_UI_CHANGES；未改 UI，未跑 box 浏览器；历史 Q2 浏览器/DR 证据未重标成本轮新实测。
- L5：**PENDING_INDEPENDENT_REVIEW**，本轮不自授独立验收，也不解锁 M3。

任务书要求的 l1-stdlib-only.log、l2-full-and-build.log、pairwise-eval-{sqlite,postgres}.json、
benchmark-115-{sqlite,postgres}.json、l3-rerank-postgres-http.md、l4-browser.md 与本报告全部归档。
额外保留 legacy 原始 JSON、冻结 manifest、CI 作业、真实 HTTP JSON、包 hash 与可执行复现脚本。

## 5. 规范、边界与清理

上位两份文件 knowledgeos-q3-core-protocol-spec-v0.1.md / knowledgeos-strategy-architecture-v0.2.md
在 checkout 与 /workspace/q2-task-inputs、/workspace/q3-task-inputs 中仍未找到。
仅报告 owner 说已在 Workbench 发布，不声称已读取/独立符合不可见条款；按详细任务书实施，
M2 补充选择在 docs/rerank-evaluation.md 明列，待资料副本与独立字段复核。

没有真实企业 IdP/SCIM 接入、在线 Qdrant、模型/embedding 服务、收费调用或生产流量实验。
监测器是明确离线过程内已知 SDK provider/urllib/socket 边界的计数拦截，不冒称任意恶意代码 sandbox；
local callable 是可信主机显式注入，PG RLS 的 app.current_org_id 仍为可信应用边界。

仅使用本轮全新 socket-only 隔离 PG17 集群与动态回环端口；未使用保留端口或既有 DB/服务/容器。
自有 HTTP 线程/连接全部退出，PG 集群已停止删除；只恢复测试生成的两份历史 L3 日志，reports/ 未触碰。
未改 main/tag、未创建 PR、未 force-push、未绕 hooks、未发布包/Release/部署、未改全局 Git 配置；
未碰 Mac/OpenBot/StratAI/.env.production。Enterprise/StratAI 继续暂停。

尚待本轮独立 L5 审查及上位规范副本/新增 M2 选择对齐；没有新的 M3 实施任务书前不启动 M3/B09、Claim/Graph/Schema6、垂类包或 Q4。
