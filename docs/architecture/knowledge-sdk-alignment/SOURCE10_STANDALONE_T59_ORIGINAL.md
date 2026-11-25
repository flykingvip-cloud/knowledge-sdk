# Align-Wave1.5 独立验收结论、延迟豁免裁定与 Align-Wave1.5b 契约收口指令

> 文档路径：`docs/architecture/knowledge-sdk-alignment/10_WAVE1P5_ACCEPTANCE_AND_DELTA_DIRECTIVE.md`
> 发文角色：团队 A 架构治理与独立验收统筹
> 抄送对象：团队 A 工程实施代理（主执行）、团队 B（`codex-knowledge`，进度同步）、架构决策负责人
> 发文日期：2026 年 11 月 25 日
> 验收标的：`feat/align-wave1p5-m1-readiness` @ `5775d424f112940199ff5cd292be1b9fc270d2bc`（GitHub Actions Run `45573187717`）
> 文档状态：**Wave1.5 原范围验收通过（含普通 RRF 延迟豁免）· 启动轻量 Wave1.5b 契约差量收口 · M1 仍为 Pending**

---

## 一、Align-Wave1.5 独立验收结论

### 1.1 总体结论

经架构治理侧独立拉仓复核 `feat/align-wave1p5-m1-readiness@5775d424f112940199ff5cd292be1b9fc270d2bc`，**正式宣布 Align-Wave1.5 原指令（`06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md`）范围独立验收通过，并对普通 RRF 微小延迟波动签发正式豁免（`Accept with Waiver`）**。

同时，因实施代理本次提交是在收到团队 B `08` / `09` 联调反馈前按原 `06` 范围完成的，`5775d424` 尚缺团队 B 在 `09` 中明确要求用于拼装 M1 冻结候选包的 5 项轻量契约差量资产。因此，本指令在批准 Wave1.5 退出的同时，紧接下发 **Align-Wave1.5b（Team B 08/09 契约差量收口）**——在同一分支追加 1 个轻量提交，**不再重跑性能优化循环**，完成即向团队 B 正式交付最终 40 位 Commit SHA 与逐文件 SHA-256 清单。

### 1.2 独立拉仓复核实证表

| 验收维度 | 独立复核命令或来源 | 实测结果 | 结论 |
|---|---|---|---|
| **远端引用与红线保护** | `git ls-remote` 与 `git diff 60b6436..5775d424` | `main@b953c992`、`v2.0.0@4afc1d71`、`feat/align-wave1-core-compat@60b6436e` 均零改动；`storage/migrations.py`、`tests/benchmark/`、`server/` 均为 0 变更；`runtime_v2_implemented=false` | **通过** |
| **四作业 GitHub CI** | GitHub Actions Run `45573187717` API 核查 | `core (3.12)`、`core (3.9)`、`http-and-package (3.12)`、`http-and-package (3.9)` 全部 `completed / success`，`head_sha=5775d424f112940199ff5cd292be1b9fc270d2bc` | **通过** |
| **回滚审计边界显式化** | 源码核查 `contracts/audit.py` 及测试 | `rollback_document` 审计事件已硬约束 `rollback_scope == "content_and_filename_only"` 且 `security_metadata_preserved is True` | **通过** |
| **黄金基准回归** | `PYTHONPATH=src python3 -S -W error::ResourceWarning -m unittest tests.benchmark.test_golden_benchmark` | 4 项测试 15.79s 全绿（原有 115 / 100 / 75 黄金用例全过，0 ResourceWarning） | **通过** |
| **纯标准库全量测试** | `PYTHONPATH=src python3 -S -W error::ResourceWarning -m unittest discover -s tests` | 共 966 项：650 通过、312 可选依赖跳过、0 ResourceWarning；本地 4 项 `SQLiteSandbox` 报错系审计容器以 `uid=0`（root）运行触发 `prepare_sandbox.py:12` 刻意设置的非 root 安全门禁，非代码缺陷（非 root CI 全依赖 962 通过、4 跳过） | **通过** |
| **TypeScript 严格编译与单测** | `tsc --strict --noEmit` + `npx tsx --test uri-mapping.test.ts` | `TSC_STRICT_PASSED`；`EXECUTED_TS_URI_MAPPING_PASSED`（44 条断言，`authority_granted: false`） | **通过** |
| **契约与 M1 清单校验器** | `validate_assets.py` 与 `validate_m1_manifest.py` | 设 `PYTHONPATH=src` 时 `DRAFT_ASSET_SELFCHECK_PASSED`（6 夹具、37 负例、23 路径、29 Schema）与 `WELL_FORMED_PENDING`（D1–D7，`freeze_authorized=false`）；**未设 `PYTHONPATH` 裸跑仍报 `ModuleNotFoundError`**（纳入 1.5b 一并修复） | **有条件通过** |

---

## 二、普通 RRF 延迟披露正式裁定

### 2.1 配对实测数据复核

独立核查交接包中的 `perf-paired-comparison.json` 与 `src/knowledge_sdk/` 改动（`_retrieval_principal_snapshot`、`_principal_mutation_epoch` 保守失效与 `_before_ranking` 实时重检）：

| 指标 | 基线（`60b6436`） | 本次（`5775d424`） | 绝对 / 相对变化 | 说明 |
|---|---|---|---|---|
| SQLite 普通 RRF P50 | `1.9081 ms` | `1.9462 ms` | `+0.0381 ms`（`+2.00%`） | 亚毫秒级抖动，无业务可感知退化 |
| PG 普通 RRF P50 | `9.1808 ms` | `9.3666 ms` | `+0.1858 ms`（`+2.02%`） | PG Mean 持平（`9.205 -> 9.206 ms`），PG P95 改善（`13.555 -> 13.426 ms`） |
| PG 增强检索 P50 | `75.543 ms` | `63.075 ms` | `-12.468 ms`（`-16.50%`） | 显著净收益 |
| SQLite 增强检索 P50 | `16.286 ms` | `16.667 ms` | `+0.381 ms`（`+2.34%`） | 固定集质量不变 |
| Principal 校验调用次数 | `1913` | `962` | `-951`（`-49.7%`） | 安全边界零降级前提下开销减半 |
| 质量与安全红线 | `NDCG/MRR=1.0`, `refusal=24/24`, `ACL=0` | 完全一致 | `0` 退化 | `implicit_model_calls=0` |

### 2.2 正式裁定结论

- **裁定结果**：签发 **正式豁免放行（`Accept with Waiver`）**。
- **裁定依据**：本次普通 RRF P50 差额仅为 SQLite `0.038 ms` / PG `0.186 ms`（约 2% 测量噪声），且 PG 均值持平、P95 反而下降、增强检索 P50 提升 16.5%、安全检查开销减半且零越权。实施代理诚实披露而非掩盖或削弱安全门禁，符合工程治理要求。
- **后续约束**：**明确禁止**团队 A 在 M1 冻结前再投入工时追逐亚毫秒级 RRF 抖动，更**严禁**为换取微弱延迟而放宽 `_before_ranking` 实时撤权重检或任何 ACL/RLS 安全边界。

---

## 三、给团队 A 工程实施代理的 Align-Wave1.5b 轻量收口指令

> **执行范围与硬边界**：
> - 基于当前 **`feat/align-wave1p5-m1-readiness`**（`5775d424f112940199ff5cd292be1b9fc270d2bc`）继续追加轻量提交，**无需切新分支**。
> - **只做下列 5 项契约与文档差量收口**，严禁再改检索引擎/性能代码、严禁修改 Schema v5、严禁修改 `main` 或 `v2.0.0`、严禁新增或上线 `/v2` 运行时路由、严禁将 M1 标为 `FROZEN`。

### Delta-1：补齐团队 B 08/09 要求的 5 组新契约夹具

在 `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/` 下新增以下 5 个 JSON 文件（所有已知向量均须逐字采纳 `08` / `09` 中经双方 Python + Node 双引擎复算通过的精确值，零真实密钥）：

1. **`identity-lifecycle-fixtures.json`**：覆盖 `(tenant_id, issuer, raw_sub)` 复合唯一键、显式 `identity.rebound` 事件、禁止跨 IdP 邮箱自动合并，以及主体停用/撤权负向用例。
2. **`policy-generation-cases.json`**：覆盖合法正整数 `1` 与 `9007199254740991`（`Number.MAX_SAFE_INTEGER`）、陈旧代际（stale）、以及全部拒绝负例：`0`、`-1`、字段缺失、`null`、`"1"`、`"abc"`、`true`、`1.5`、溢出 `9007199254740992`。
3. **`hash-vectors-utf8.json`**：收录全部 7 组实算向量（`08` 的 4 组 UTF-8/Unicode 向量 + `09` 2.1 节的 3 组 Python 29 码点空白边界向量：`py_ctrl_separators_001c_001f`、`py_nel_0085`、`bom_feff_preserved_in_python`），显式声明 `hash_algorithm: "sha256"` 与裸 64 位小写十六进制，并注记 `U+FEFF` 在 Python `str.isspace()` 中保留不折叠。
4. **`signed-request-canonicalization.json`**：收录全部 4 组实算签名向量（`08` 的 8 行基准向量 + `09` 2.2 节的 3 组边界向量：6 行 GET 含 `%2F` 原样查询串、8 行 POST 含查询串与非 ASCII UTF-8 正文、8 行仅 `X-KB-Purpose` 缺 `X-KB-Agent`），全部使用 `TEST_ONLY_DO_NOT_USE_IN_PROD_*` 测试伪密钥并显式标注仅限离线算法互验；同时附脱敏 HTTP `200` / `403` / `409` / `422` 请求与响应 wire 样例。
5. **`rollback-activation-cases.json`**：收录 `09` 2.3 节全部 8 组正负例，严格验证公式 `activated = (created_version === current_version) && (lifecycle_state === "published")`，覆盖全部 7 种合法生命周期态（`published` / `draft` / `in_review` / `approved` / `rejected` / `superseded` / `revoked`）及版本指针不一致负例。

### Delta-2：修订 openapi-v2-draft.yaml 与 openbot-adapter-dto.d.ts

保持 `x-contract-status: draft-pending-m1-freeze` 与 `runtime_v2_implemented: false`，完成以下 4 处精细对齐：

1. 显式分离 `hash_algorithm: "sha256"` 与裸 64 位小写十六进制哈希字段（`pattern: "^[0-9a-f]{64}$"`），确保零 `sha256:` 前缀残留。
2. `policy_generation` 在 OpenAPI 与 TS DTO 中统一约束为安全正整数 `1..9007199254740991`（并在注释/Schema 中明确拒绝非整数、字符串与大于 `2^53 - 1` 的数值）。
3. 写入与回滚响应 DTO 显式包含 5 字段：`created_version`、`current_version`、`lifecycle_state`（7 值枚举：`draft | in_review | approved | published | rejected | superseded | revoked`）、`activated`（严格采用 `published` 白名单语义）、`rollback_scope`（`"content_and_filename_only"`）。
4. 最小集成切片的同步写端点（`POST /v2/spaces`、`POST /v2/documents`）显式声明可选 `Idempotency-Key` 请求头与 `409 IDEMPOTENCY_CONFLICT` 错误响应。

### Delta-3：扩展 uri-mapping.ts 与 uri-mapping.test.ts

1. 在 `docs/architecture/knowledge-sdk-alignment/contracts/uri-mapping.ts` 中新增零依赖纯函数 `normalizeTextPythonCompat(input: string): string`，严格按 Python 全部 29 个 `str.isspace()` 码点折叠空白并保留 `U+FEFF`（**严禁使用 ECMAScript `/\s+/`**）。
2. 在 `uri-mapping.test.ts` 中读取 `contract-fixtures/hash-vectors-utf8.json`，在 Node / CI 中对全部 7 组 `raw_hash` 与 `semantic_hash` 实跑断言并通过 `tsc --strict --noEmit`。

### Delta-4：修复 validate_assets.py 零配置裸跑并覆盖新夹具

1. 在 `docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py` 顶部自动将仓库 `src/` 目录加入 `sys.path`，确保团队 B 与 CI 直接执行 `python3 docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py`（无需手动设置 `PYTHONPATH=src`）即可通过。
2. 在校验器中纳入上述 5 组新夹具的 Schema、向量一致性（用 Python `hashlib` 与 `hmac` 交叉复算 `hash-vectors-utf8.json` 和 `signed-request-canonicalization.json`）及 `rollback-activation-cases.json` 8 组公式复核。

### Delta-5：归档 06–10 文档并在 m1-freeze-manifest.json 钉住全契约文件 SHA-256

1. 将对齐文档 `06`、`07`、`08`、`09`、`10` 原样归档至 `docs/architecture/knowledge-sdk-alignment/`，并同步更新 `M1_DECISION_PACKAGE.md` 纳入团队 B 最小集成切片候选（10 项验收断言与 `Idempotency-Key` / 5 字段回滚 DTO 两项补强）。
2. 在 `docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json` 中：
   - 保持 `status: "pending_joint_signoff"`、`freeze_authorized: false`（严禁伪造 `FROZEN`）；
   - 新增 `contract_asset_hashes` 字段，按相对路径逐一列出 `openapi-v2-draft.yaml`、`openbot-adapter-dto.d.ts`、`uri-mapping.ts`、`M1_DECISION_PACKAGE.md` 以及全部 `contract-fixtures/*.json` 的精确裸 64 位小写 SHA-256，并由 `validate_m1_manifest.py` 100% 校验文件哈希与磁盘内容一致。

---

## 四、Wave1.5b 精简退出门禁与致团队 B 进度同步

### 4.1 Wave1.5b 退出门禁（L1–L4）

| 门禁 | 必达硬标准 |
|---|---|
| **L1 零配置契约与清单实检** | 裸跑 `python3 docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py`（不设 `PYTHONPATH`）全绿；`python3 docs/architecture/knowledge-sdk-alignment/validate_m1_manifest.py` 验证全部 `contract_asset_hashes` 100% 匹配磁盘文件且 `freeze_authorized=false`。 |
| **L2 TypeScript 实跑复算** | `tsc --strict --noEmit` 0 错误；`uri-mapping.test.ts` 实跑通过既有 44 项 URI 断言 + 新增全部 7 组 Python 29 码点 UTF-8 哈希向量断言。 |
| **L3 CI 与零退化回归** | 四作业 GitHub Actions CI 全绿；无任何 Schema v5、黄金基准或性能代码改动。 |
| **L4 交接归档** | 在 `docs/acceptance/v2.1-align-wave1p5/ALIGN_WAVE1P5B_DELTA_HANDOFF.md` 归档简短交接单，汇报新提交的完整 40 位 Commit SHA、四作业 CI 链接以及完整的 `contract_asset_hashes` 表，交由架构治理侧独立复核后正式提名移交团队 B。 |

### 4.2 致团队 B 的简短同步说明（可直接转发）

- **现状同步**：团队 A 工程实施代理已按原 `06` 范围交付 `feat/align-wave1p5-m1-readiness@5775d424f112940199ff5cd292be1b9fc270d2bc`（四作业 CI Run `45573187717` 全绿，已完成独立验收并豁免普通 RRF 0.04ms 级噪声）。
- **最后收口**：因 `5775d424` 在收到贵方 `08` / `09` 反馈前形成，团队 A 已立即在同一分支启动轻量收口 **Align-Wave1.5b**，专门补齐贵方 `09` 清单所需的 5 组差量契约夹具、`normalizeTextPythonCompat` 29 码点 TS 实现、`validate_assets.py` 零配置裸跑及 `m1-freeze-manifest.json` 逐契约文件裸 64 位 SHA-256。
- **下一步衔接**：Wave1.5b 提交并通过独立拉仓验收后，团队 A 将第一时间向贵方正式提名最终 40 位 Commit SHA 与全文件 SHA-256 清单，供贵方核对并拼装最终提交架构负责人审批的 M1 冻结候选包。在此之前双方继续保持 M1 `Pending`、严禁提前冻结或启动 Wave2 / M3。
