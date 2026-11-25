# Align-Wave1.5 合并执行指令与团队 B 09 回执确认函

> 文档路径：`docs/architecture/knowledge-sdk-alignment/09_WAVE1P5_CONSOLIDATED_EXECUTION_DIRECTIVE.md`
> 发文角色：团队 A 架构治理与独立验收统筹
> 抄送对象：团队 A 工程实施代理（主执行）、团队 B（`codex-knowledge`，知会与边界确认）、架构决策负责人
> 发文日期：2026 年 11 月 25 日
> 文档状态：**团队 A 实施指令生效（Align-Wave1.5 Consolidated）· M1 仍保持 Pending** — 本文合并 `06`（Wave1.5 基础指令）、`08`（团队 B 7 项差异补充）与 `09`（团队 B 四项边界核验反馈），供团队 A 工程实施代理一次性交付 Wave1.5，并在独立验收通过后向团队 B 交付完整 40 位 Commit SHA 与全文件 SHA-256 冻结输入清单。严禁单方标注 M1 为 `Frozen`，严禁修改 Schema v5、主干 `main` 或提前上线 `/v2` 运行时路由。

---

## 一、致团队 B（09 回执确认与边界补齐）

1. **认可独立复算与诚实冻结立场**：确认团队 B 已用 Python 与 Node 独立复算通过 `08` 中的 4 组 UTF-8/Unicode 哈希向量与 8 行 HMAC 签名向量（无需重做），并完全认同“不拿 `60b6436` 旧草案哈希冒充 Wave1.5 最终 Schema 哈希、待 Wave1.5 精确 SHA 与独立验收齐备后再生成可审阅冻结候选 manifest”的严谨纪律。
2. **完全采纳团队 B 09 提出的四项精细技术边界**（已合入下方 Wave1.5 合并指令一次落地）：
   - **Python 空白集合精确边界**：锚定 Python `str.isspace()` 全部 29 个码点（`U+0009–000D`、`U+001C–001F`、`U+0020`、`U+0085`、`U+00A0`、`U+1680`、`U+2000–200A`、`U+2028–2029`、`U+202F`、`U+205F`、`U+3000`），明确 `U+001C–001F` 与 `U+0085` 参与折叠，而 `U+FEFF`（BOM）**不属于** Python 空白、必须原样保留；禁止 TypeScript 侧用 ECMAScript `/\s+/` 冒充等价实现。
   - **查询串签名、6/8 行切换与非 ASCII 编码规则**（锚定 `src/knowledge_sdk/server/app.py:89-90` 与 `server/auth.py:145-179`）：
     - 规范化消息第 2 行固定为 `target = raw_path + ("?" + raw_query if raw_query else "")`（原样保留 wire 层的 percent-encoding，如 `%2F` 不得解码后再签名；无查询串时不含 `?`）；
     - 仅当 `X-KB-Agent` 与 `X-KB-Purpose` 两者均缺席时为 **6 行**；任一存在时为 **8 行**（缺席的一项为空串 `""`）；
     - 请求体摘要对**实际传输的原始 UTF-8 字节流**计算 `sha256`（与 JSON 是否转义非 ASCII 无关，但发送端与验签端必须针对同一 wire 字节序列）；`X-KB-Actor`/`X-KB-Agent` 验签按请求头原 Base64 字符串参与签名且服务端可解析任意合法 UTF-8 JSON（`auth.py:163` 默认生成 `\uXXXX` ASCII 转义 JSON）。
   - **`activated` 改为显式发布态白名单（废止“不等于 draft”写法）**：锚定 `contracts/models.py:88` 与 `contracts/governance.py:44` 全部 7 种合法生命周期态（`draft`、`in_review`、`approved`、`published`、`rejected`、`superseded`、`revoked`），冻结判定公式为 **`activated = (created_version === current_version) && (lifecycle_state === "published")`**。所有其余 6 种状态（含 `approved` 尚未发布前）或版本号不等时，`activated` 必须为 `false`。
   - **历史时间戳与算法向量定位声明**：明确所有静态签名夹具仅用于离线算法互验（使用 `TEST_ONLY_DO_NOT_USE_IN_PROD_*` 伪密钥与固定历史时间戳），绝不作为在线请求或真实重放/鉴权验收替代品。

---

## 二、立即交付给团队 B 的新增实算边界向量

### 2.1 Python 空白集合边界哈希向量（含 U+001C–001F、U+0085 与 U+FEFF 保留）

```json
[
  {
    "id": "py_ctrl_separators_001c_001f",
    "raw": "A\u001cB\u001dC\u001eD\u001fE",
    "normalized": "A B C D E",
    "hash_algorithm": "sha256",
    "raw_hash": "1902c113c19f820c2edeea205b85f7e6b786194f0f56575e78442a8fc772aada",
    "semantic_hash": "f527687229a42ecd273f976a7c0b7ddde0050230e3729c77a41c1d59c54eabb3"
  },
  {
    "id": "py_nel_0085",
    "raw": "Line1\u0085Line2",
    "normalized": "Line1 Line2",
    "hash_algorithm": "sha256",
    "raw_hash": "c7e544aa69e9821c6be96cb3cb9db2b136fe9efda6444fe42786362183db7220",
    "semantic_hash": "9f30309951a3b354c1750172c5cbd4172c8c5b25d16a9ffbb37c164d071c1f6c"
  },
  {
    "id": "bom_feff_preserved_in_python",
    "raw": "\ufeffTitle\ufeffBody",
    "normalized": "\ufeffTitle\ufeffBody",
    "hash_algorithm": "sha256",
    "raw_hash": "0ce2b52edb11ced21d072bf80a55d2c281c1637f3982398e6db313beaab61153",
    "semantic_hash": "0ce2b52edb11ced21d072bf80a55d2c281c1637f3982398e6db313beaab61153"
  }
]
```

### 2.2 签名 6 行 / 8 行、查询串与非 ASCII UTF-8 正文向量（测试专用伪密钥，复用 08 同一 X-KB-Actor 与 X-KB-Agent）

公共测试输入：
- `test_only_secret`: `"TEST_ONLY_DO_NOT_USE_IN_PROD_0123456789abcdef"`
- `X-KB-Timestamp`: `"1795478400"`（仅离线算法校验，禁止用于在线请求）
- `X-KB-Actor`: `"eyJhbmNlc3Rvcl9kZXBhcnRtZW50X2lkcyI6W10sImNsZWFyYW5jZV9sZXZlbCI6IiIsImNsZWFyYW5jZV90YWdzIjpbXSwiZGVwYXJ0bWVudF9pZHMiOlsiZGVwdC1yZCJdLCJtYW5hZ2VkX2RlcGFydG1lbnRfaWRzIjpbXSwib3JnX2lkIjoidGVuYW50LXNhbmRib3gtMDEiLCJvcmdfcm9sZXMiOltdLCJwb2xpY3lfZ2VuZXJhdGlvbiI6IjEiLCJwdWJsaWNfa2JfYWRtaW4iOmZhbHNlLCJyb2xlcyI6WyJtZW1iZXIiXSwic2Vzc2lvbl9pZCI6InNlc3MtdGVzdC0wMDEiLCJ1c2VyX2lkIjoidXNyLTAxOTRmMDAwLTAwMDEifQ=="`
- `X-KB-Agent`（仅第 2 组携带）: `"eyJhZ2VudF9pZCI6ImFnZW50LW9wZW5ib3QtMDEiLCJvcmdfaWQiOiJ0ZW5hbnQtc2FuZGJveC0wMSJ9"`

```json
[
  {
    "id": "sign_6line_get_raw_query_percent_encoded",
    "method": "GET",
    "signed_target": "/v1/documents?kb_id=kb-001&archived_only=true&cursor=abc%2F123",
    "nonce": "nonce-6line-0123456789abcdef",
    "agent_header_present": false,
    "purpose_header_present": false,
    "body_utf8": "",
    "body_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "canonical_lines_count": 6,
    "signature": "5eab9b43445499e1ae701d898ae3765e015c313d4c0206fba5ccd894c5c84565"
  },
  {
    "id": "sign_8line_post_query_non_ascii_utf8_body",
    "method": "POST",
    "signed_target": "/v1/search?locale=zh-CN",
    "nonce": "nonce-utf8-0123456789abcdef0",
    "agent_header_present": true,
    "purpose": "ground_internal_llm",
    "body_utf8": "{\"kb_id\":\"kb-001\",\"query\":\"\u4e34\u5e8a\u8bd5\u9a8c Caf\u00e9\"}",
    "body_sha256": "ca1a85aec981ba758df8c1c51aa7112f036337179334c9c22dde09e7c8f9293f",
    "canonical_lines_count": 8,
    "signature": "02322bdceb89638d56165548ff1bce4a7e5a7f44da99daf49c0cd4760e4eb728"
  },
  {
    "id": "sign_8line_purpose_only_empty_agent_line",
    "method": "GET",
    "signed_target": "/v1/ready",
    "nonce": "nonce-purp-0123456789abcdef0",
    "agent_header_present": false,
    "purpose": "read",
    "body_utf8": "",
    "body_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "canonical_lines_count": 8,
    "signature": "30483a24628e1708a8f49125310028f9447c40bf9aefceda815329da858f5e17"
  }
]
```

### 2.3 activated 显式发布态白名单与受控负例矩阵

判定公式：`activated = (created_version === current_version) && (lifecycle_state === "published")`

| 用例 ID | `created_version` | `current_version` | `lifecycle_state` | 预期 `activated` | 语义说明 |
|---|---|---|---|---|---|
| `act_l1_published` | `3` | `3` | `published` | `true` | L1 写入/回滚立即激活 |
| `neg_l2_draft` | `3` | `2` | `draft` | `false` | L2 受控草稿，不得冒充当前发布版 |
| `neg_l2_in_review` | `3` | `2` | `in_review` | `false` | 评审中版本未激活 |
| `neg_l2_approved_unpub` | `3` | `2` | `approved` | `false` | 已批未发布，仍非当前发布版 |
| `neg_l2_rejected` | `3` | `2` | `rejected` | `false` | 已驳回版本绝不激活 |
| `neg_revoked_same_ver` | `3` | `3` | `revoked` | `false` | 即便版本指针相等，撤权态亦必须为 `false` |
| `neg_superseded` | `2` | `3` | `superseded` | `false` | 已被新版本取代 |
| `neg_pointer_mismatch` | `3` | `2` | `published` | `false` | 指针未切换至新建版本时不可标为激活 |

---

## 三、给团队 A 工程实施代理的 Align-Wave1.5 完整合并执行指令

> **执行基线与分支纪律**：
> - 从 `feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888` 切出新分支 **`feat/align-wave1p5-m1-readiness`**（若已存在则基于该分支继续迭代）。
> - **严禁触碰**：禁止修改 `main` / `v2.0.0` 标签、禁止修改 SQLite/PostgreSQL Schema v5、禁止新增或上线 `/v2/*` 运行时路由、禁止将 M1 标为 `Frozen`、禁止修改 OpenBot 仓库、禁止破坏既有 115/115、100/100、75/75 黄金基准。

### Task 1：文档归档与回滚审计边界显式化（合入 06/07/08/09）

1. 将对齐文档 `06`、`07`、`08`、`09` 原样归档至 `docs/architecture/knowledge-sdk-alignment/`，确保与团队 B 收发记录一一对应。
2. 在 `src/knowledge_sdk/client/compat.py` 的 `rollback_document(...)` 中：
   - 保持 Schema v5 兼容边界（append-only 恢复目标版本 `text` 与 `filename`，永久保留当前 ACL/Rights/Validity/Archive/业务元数据）；
   - 在审计事件 `details` 中显式写入 `rollback_scope: "content_and_filename_only"` 与 `security_metadata_preserved: true`，并补充 SQLite + PostgreSQL 回归测试断言（含 L1 立即激活与 L2 创建 `draft` 不改 `current_version` 双场景）。

### Task 2：修订 v2 契约草案与补齐团队 B 全部 9 项联调夹具

1. **修订 `openapi-v2-draft.yaml` 与 `openbot-adapter-dto.d.ts`**（仍显式标注 `x-contract-status: draft-pending-m1-freeze` 与 `runtime_v2_implemented: false`）：
   - 全量移除示例中的 `sha256:` 前缀，统一分离 `hash_algorithm: "sha256"` 与裸 64 位小写十六进制（`^[0-9a-f]{64}$`）；
   - `policy_generation` 严格约束为整数 `1..9007199254740991`；
   - 写入/回滚响应 DTO 显式定义五字段：`created_version`、`current_version`、`lifecycle_state`（7 值枚举）、`activated`（严格遵循 `created_version === current_version && lifecycle_state === "published"`）、`rollback_scope`；
   - 最小切片同步写端点（创建空间、同步摄取文档）显式声明可选 `Idempotency-Key` 请求头与 `409 IDEMPOTENCY_CONFLICT` 响应。
2. **新增/更新契约夹具与校验器**（位于 `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/`）：
   - `identity-lifecycle-fixtures.json`：`(tenant_id, issuer, raw_sub)` 唯一性、显式 `identity.rebound`、禁止跨 IdP 邮箱自动关联及撤权负向用例；
   - `policy-generation-cases.json`：正常、陈旧、`0`、负数、缺失、`null`、字符串/布尔/浮点、溢出（`2^53`）全量用例；
   - `hash-vectors-utf8.json`：收录 `08` 的 4 组已复算向量 + 本文 2.1 节的 3 组 Python 空白边界向量（共 7 组，明示 29 个 Python `str.isspace()` 码点与 `U+FEFF` 差异）；
   - `signed-request-canonicalization.json`：收录 `08` 的 8 行基准向量 + 本文 2.2 节的 3 组边界向量（6 行含查询串、8 行含查询串及非 ASCII UTF-8 正文、8 行仅 purpose 缺 agent），并附真实脱敏 HTTP `200`/`403`/`409`/`422` 请求/响应样例（零真实密钥，显著标注测试伪密钥与离线算法用途）；
   - `rollback-activation-cases.json`：收录本文 2.3 节全部 8 组正负例（覆盖 `published`/`draft`/`in_review`/`approved`/`rejected`/`superseded`/`revoked` 及版本指针不一致）；
   - 更新 `validate_assets.py`，自动校验上述全部新夹具并确保在纯标准库下可执行（脚本开头自动兼容仓库 `src/` 路径，避免裸跑 `python3 validate_assets.py` 因缺 `PYTHONPATH` 报错）。

### Task 3：单页可签署 M1 决策包与全文件 SHA-256 冻结输入清单

1. 交付 `docs/architecture/knowledge-sdk-alignment/M1_DECISION_PACKAGE.md`：一页汇总 6 项 `Pending` 架构裁决选项（含团队 A/B 共识推荐项、风险对比、签字栏）与最小集成切片（含全部 10 项验收标准及两项补强）。
2. 交付 `docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json`：
   - 状态显式标记为 `freeze_status: "PENDING_ARCHITECT_APPROVAL"`（严禁写成 `FROZEN`）；
   - 列出本分支中 `openapi-v2-draft.yaml`、`openbot-adapter-dto.d.ts`、全部 `contract-fixtures/*.json`、`uri-mapping.ts` 及 `M1_DECISION_PACKAGE.md` 的**精确文件级 SHA-256（裸 64 位小写十六进制）**，供团队 B 拉仓核对并拼装最终冻结候选包。

### Task 4：团队 B 5 分钟双模式联调靶场与零依赖 TS 工具参考

1. 交付 `deploy/openbot-sandbox/`（含 `docker-compose.yml`、`README.md`、一键启动脚本与离线签名校验示例），支持 SQLite / PostgreSQL 双模式 5 分钟拉起当前 `/v1` 兼容服务供团队 B 做非生产预研与 `/v1/ready` 探针验证（明确标注 `/v2` 尚未上线）。
2. 交付零依赖 TypeScript 参考文件 `docs/architecture/knowledge-sdk-alignment/contracts/uri-mapping.ts`（含 `normalizeTextPythonCompat` 严格按 29 码点实现 + `ku:// <-> kb://` 显式持久化映射校验与缺失失败错误码），并在 CI 中用 `tsc --strict --noEmit` + Node 实跑复验全部 7 组哈希向量与 URI 映射测试。

### Task 5：普通 RRF 延迟轻微回补

1. 排查 Wave1 引入的普通 RRF P50 轻微变慢（SQLite `+0.043ms`、PG `+0.478ms`），通过请求内对象/策略上下文复用回补至持平或更优，不改排序结果与零越权语义，附同快照配对延迟对比报告。

---

## 四、Wave1.5 验收门禁（L1–L5）与交接报告要求

| 门禁 | 必达硬标准 |
|---|---|
| **L1 静态与契约实检** | `python3 docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py`（无需手动设 `PYTHONPATH` 亦可通过）全绿；CI 实跑 `tsc --strict --noEmit` 与 Node 向量复算全绿；`m1-freeze-manifest.json` 逐文件 SHA-256 100% 匹配。 |
| **L2 纯标准库与双引擎全依赖** | `python3 -S -W error::ResourceWarning` 0 失败、0 ResourceWarning；四作业 CI（SQLite + PG+pgvector+RLS）全绿；既有 115/115、100/100、75/75 黄金基准 0 修改全过。 |
| **L3 边界行为实证** | 新增测试覆盖 L1/L2 `rollback_document` 审计与 `activated` 8 组状态矩阵、7 组 Unicode 空白/哈希向量、4 组 6/8 行+查询串+非 ASCII 签名向量及脱敏 wire 捕获。 |
| **L4 沙箱与延迟对比** | CI 实跑 `deploy/openbot-sandbox` 容器健康检查通过；同快照配对延迟报告显示普通 RRF P50 回补且增强检索质量不变。 |
| **L5 边界与红线核查** | `git status` 干净；`main` 与 `v2.0.0` 零改动；Schema v5 零改动；无 `/v2` 运行时抢跑；`m1-freeze-manifest.json` 严禁伪造 `FROZEN`。 |

完成后请推送分支 `feat/align-wave1p5-m1-readiness`，归档交接报告 `docs/acceptance/v2.1-align-wave1p5/ALIGN_WAVE1P5_HANDOFF_REPORT.md`，汇报**完整 40 位 Commit SHA** 与四作业 CI 链接，交由团队 A 架构统筹完成独立拉仓验收后正式提名移交团队 B。
