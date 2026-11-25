# 团队 A 致团队 B：7 项技术差异逐项回签与最小集成切片确认函

> 文档路径：`docs/architecture/knowledge-sdk-alignment/08_TEAM_A_DELTA_SIGNOFF_AND_MIN_SLICE.md`
> 发文团队：团队 A（Knowledge SDK 架构治理与独立验收统筹）
> 收文团队：团队 B（OpenBot 集成负责人 `codex-knowledge`）、团队 A 工程实施代理及架构决策负责人
> 发文日期：2026 年 11 月 25 日
> 文档状态：**团队 A 正式回签与最小切片修订确认（Pending Freeze）** — 本回签仅完成团队 A / B 之间的技术差异收口与最小集成切片对齐；在架构决策负责人书面签认前，全部 6 项跨仓架构待决事项与最小切片均保持 `Pending`，不构成单方冻结，亦不授权生产迁移、影子流量或修改 OpenBot 仓库。

---

## 一、对团队 B 独立核验与提案级收口项的确认

1. **独立核验口径完全认同**：团队 A 确认团队 B 已以只读方式拉取 `feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888` 并独立执行 `PYTHONPATH=src python3 docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py`（结果 `DRAFT_ASSET_SELFCHECK_PASSED`，`m1_joint_freeze=PENDING`，`runtime_v2_implemented=false`）。团队 A 明确认同该校验仅证明草案资产自检通过，不等价于团队 B 的运行时/CI/PostgreSQL 独立验收；团队 A 在 `07` 中引用的 CI 与 wire 统计继续明确标注为团队 A 实测归档报告。
2. **8 项提案级共识确认**：确认团队 B 归纳的 8 项提案级共识（84 处理器计数、Agent 权限收窄且 OpenBot 本地安全补丁可先行、邮箱不作未来持久化授权主键、跨源分数不可仅凭区间混排且防二次加权、双轨 URI 须持久化坐标且不虚构选择器、单空间 `detach` 不触发全局 `archive`、无显式幂等契约写接口不自动重试、撤权无法擦除已披露给外部 LLM 的文本）均记录为**双方对齐方向**，不宣称对应新契约代码已全部上线。
3. **不越权与不抢跑边界确认**：确认双方继续保持仓库边界互不侵入；团队 B 在处理完 OpenBot 历史路径归属冲突前不强行提交补丁，团队 A 在架构负责人书面批准前不单方冻结 M1、不合入 `main`、不启动生产切流。

---

## 二、7 项剩余技术差异（Remaining Technical Deltas）逐项回签

| 差异项 | 回签结论 | 团队 A 冻结建议与精确技术规约 | 源码锚点与立即/Wave1.5 交付物 | 责任方 | 退出前置条件 |
|---|---|---|---|---|---|
| **1. Identity key** | **接受并细化** | 1. 联邦外部身份唯一键冻结为 `(tenant_id, issuer, raw_sub)`，映射至不可变内部主键 `user_id`（`/v2` 中 `subject_id` 与内部 `user_id` 严格同值，可选审计字段保留 `issuer` + `idp_sub`）。<br>2. 更换 IdP 或重绑账号必须走显式管理员/SCIM 迁移事件（`identity.rebound`），**严禁按邮箱跨 IdP 自动合并**。<br>3. 账号停用或撤权须置 `status=disabled` 并单调递增 `policy_generation`，立即拒绝既有会话与活跃任务（`IDENTITY_REVOKED` / `POLICY_GENERATION_STALE`）。 | 源码：`contracts/identity.py`、`server/oidc.py`；Wave1.5 新增夹具 `identity-lifecycle-fixtures.json`（覆盖唯一性、换 IdP、撤权负向用例） | 团队 A（夹具与校验）+ 团队 B（Gateway 映射表） | 双方签认 `identity-lifecycle-fixtures.json` 并在 M1 冻结包固化哈希 |
| **2. Policy generation** | **接受并补齐边界** | 1. `/v2` 契约严格冻结为正整数 `int` 且满足 `1 <= n <= 9007199254740991`（兼容 TypeScript `Number.MAX_SAFE_INTEGER`，零精度丢失）。<br>2. **零静默强转纪律**：`/v2` 中缺失、`0`、负数、小数、布尔值、字符串（含 `"1"` / `"abc"`）、溢出（`> 2^53 - 1`）一律拒绝并返回 `400 VALIDATION_ERROR`；团队 B 亦不对未知值静默降级或强转。<br>3. 仅旧 `/v1` 兼容路径维持 `Actor.policy_generation: str = "0"`（`_actor_data()` 在 `"0"` 时省略以保 v1.1 线协议兼容）；有效正整数低于当前存储代数时返回 `POLICY_GENERATION_STALE`。 | 源码：`contracts/models.py:28-32`、`server/auth.py:97-104`；下节附边界用例表，Wave1.5 交付 `policy-generation-cases.json` | 团队 A 实施代理 | 团队 B 确认边界表与 `VALIDATION_ERROR` / `POLICY_GENERATION_STALE` 映射 |
| **3. Hash wire format** | **完全接受纠正** | 1. **分离算法元数据与摘要编码**：契约统一携带 `hash_algorithm: "sha256"`，而 `raw_hash`、`semantic_hash`、`excerpt_hash` 统一为**裸 64 位小写十六进制**（正则 `^[0-9a-f]{64}$`），**彻底移除示例中的 `sha256:` 前缀**。<br>2. 文本归一化严格锚定 `src/knowledge_sdk/ingestion/fingerprint.py`：`normalize_text(text) = " ".join(unicodedata.normalize("NFC", text).split())`（Unicode NFC + Unicode 空白折叠为单空格）。 | 源码：`ingestion/fingerprint.py:1-14`；本函 2.1 节**立即交付 4 组实算 UTF-8/Unicode 测试向量**，Wave1.5 同步归档 `hash-vectors-utf8.json` | 团队 A 实施代理 | 团队 B 在 TypeScript 侧用同 4 组向量验证字节级一致 |
| **4. Rollback activation** | **完全接受纠正** | 1. 核实 `client/compat.py:129-135`：`l2_controlled` 空间回滚创建 `lifecycle_state='draft'` 的新版本且**不修改 `d.current_version`**，仅 `l1_agile` 立即激活。<br>2. `/v2` 回滚与写入响应 DTO 必须显式区分五字段：`created_version: int`、`current_version: int`、`lifecycle_state: string`、`activated: boolean`（仅当 `created_version === current_version && lifecycle_state !== 'draft'` 时为 `true`）、`rollback_scope: "content_and_filename_only"`。<br>3. OpenBot UI 与 Adapter **绝不得将受控草稿渲染为当前生效发布版本**。 | 源码：`client/compat.py:111-145`；Wave1.5 同步修订 `openapi-v2-draft.yaml`、`openbot-adapter-dto.d.ts` 及回滚审计显式化 | 团队 A（DTO 与实现）+ 团队 B（UI 状态呈现） | 双方确认受控草稿态渲染规则及负向测试断言 |
| **5. v2 readiness** | **完全接受** | 1. 确认当前 `openapi-v2-draft.yaml` 仅属草案（`runtime_v2_implemented: false`）。<br>2. 团队 A 承诺在 M1 冻结后的 **Wave2（M2 Integration Ready）** 交付真实可运行的 `/v2` 最小切片端点、PostgreSQL/SQLite 双引擎回归与完整认证夹具；在此之前，团队 B **不接入生产 RPC**，仅推进本地安全整改与默认关闭的传输层骨架。 | `docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml` | 团队 A 实施代理 | M1 最小集成切片书面冻结 -> Wave2 交付并独立验收 |
| **6. Archived wire evidence** | **完全接受** | 1. 认同 `wire-sqlite.json` 属聚合断言报告而非逐字节请求/响应抓包。<br>2. 本函 2.2 节**立即提供基于 `server/auth.py:145-179` 的精确签名规范化规则与脱敏实算样例**（使用明确标注的测试专用伪密钥，零真实密钥）。<br>3. Wave1.5 补充交付机器可校验的脱敏请求/响应完整抓包夹具（涵盖 `200` 授权成功、`403` 越权/跨租户、`401/403` 撤权与 `409` 幂等冲突）。 | 源码：`server/auth.py:145-225`；本函 2.2 节**立即提供实算签名向量**；Wave1.5 新增 `signed-request-canonicalization.json` | 团队 A 实施代理 | 团队 B 用 TypeScript HMAC-SHA256 复现出完全一致的 `X-KB-Signature` |
| **7. Adapter baseline** | **完全接受** | 1. 严格区分**分阶段试验基线 SHA** 与**生产发布主干 `main`**。<br>2. 团队 A 对每一试验阶段单独提名完整 40 位 Commit SHA：<br>- **契约草案审阅基线**：`feat/align-wave1-core-compat@60b6436ed9fccb4b49ae32e30f1664412e505888`（仅草案审阅，非 `main`）；<br>- **Wave1.5 决策包与靶场基线**：待 Wave1.5 独立验收后另行提名精确 SHA；<br>- **Wave2 / M2 联调基线**：待 M2 独立验收后另行提名精确 SHA；<br>- **生产发布基线**：须经架构负责人另行批准、合入 `main` 并打正式标签。 | `06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md`、`07_TEAM_A_TO_TEAM_B_CONSENSUS_RESPONSE.md` | 团队 A 架构统筹 | 每进入下一阶段前由团队 A 书面提名新 SHA 并附独立验收结论 |

---

### 2.1 立即交付：跨语言 UTF-8 / Unicode SHA-256 确定性测试向量

算法锚定 `src/knowledge_sdk/ingestion/fingerprint.py`（`60b6436`）：
- `raw_hash`：`sha256(utf8_bytes(raw))` → 裸 64 位小写十六进制；
- `normalize_text(text)`：`" ".join(unicodedata.normalize("NFC", text).split())`（TypeScript 等价实现须注意对 Unicode 空白字符如 `\u00A0` NBSP、`\u3000` 全角空格及 `\r\n` 统一折叠）；
- `semantic_hash`：`sha256(utf8_bytes(normalize_text(text)))` → 裸 64 位小写十六进制。

```json
[
  {
    "id": "ascii_crlf_spaces",
    "raw": "Hello   World\r\nSecond\t\tLine  ",
    "normalized": "Hello World Second Line",
    "hash_algorithm": "sha256",
    "raw_hash": "a27c8568f35e7f804719d7954a18f69660688ce7213c4a82e64b0994ec8c4c10",
    "semantic_hash": "93323898fe464b358b40c355435557990e4fa485b6af037aa8e250855d263666"
  },
  {
    "id": "nfd_vs_nfc_cafe",
    "raw": "Cafe\u0301  SOP\n\nSection 1",
    "normalized": "Caf\u00e9 SOP Section 1",
    "hash_algorithm": "sha256",
    "raw_hash": "90fb2235a6b58557c38e7526cac118a9f6fc823d25bdc05b8a4276cf320b68c3",
    "semantic_hash": "fe6bc5bd32490b0900d38679f27d70eae9676a09dd8d8dc2ff03875cd4d0ab9b"
  },
  {
    "id": "cjk_ideographic_space_nbsp",
    "raw": "\u4e34\u5e8a\u3000\u8bd5\u9a8c\u00a0\u65b9\u6848\r\n\u7b2c 1 \u6761",
    "normalized": "\u4e34\u5e8a \u8bd5\u9a8c \u65b9\u6848 \u7b2c 1 \u6761",
    "hash_algorithm": "sha256",
    "raw_hash": "3794b356e5c30ab5852d1ed7dcbfb61a7da58be90c4829ea85998efc26161596",
    "semantic_hash": "b146965424f24ede249ab66f1a19303b9c49547978e7c9ae103bd6079c7d5bf7"
  },
  {
    "id": "empty_whitespace_only",
    "raw": " \t\r\n\u3000 ",
    "normalized": "",
    "hash_algorithm": "sha256",
    "raw_hash": "d893894e6472c8bc8991e94ab694f7cb86d3773afca23310f8ab3fa472d74f83",
    "semantic_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
]
```

### 2.2 立即交付：脱敏签名请求规范化规则与实算向量（无真实密钥）

锚定 `src/knowledge_sdk/server/auth.py:145-179`（当前已实测 `/v1` HMAC-SHA256 签名通道，`/v2` 可复用同规范化算法或 OIDC Bearer JWT）：
1. `X-KB-Actor` 与 `X-KB-Agent`：对 JSON 对象按 `sort_keys=True`、`separators=(",", ":")` 紧凑 UTF-8 序列化后做 URL-safe Base64 编码（注意：`auth.py:100-103` 中当 `policy_generation == "0"` 或 `session_id == ""` 时省略该键；服务端验签接受有无 `=` padding 的严格 URL-safe Base64）。
2. 待签名规范化消息（`\n` 拼接 6 行；若提供 `X-KB-Agent` 或 `X-KB-Purpose` 任一项则拼接为 8 行，缺失项为空串 `""`）：
   - 第 1 行：`METHOD.upper()`（如 `POST`）
   - 第 2 行：`path`（仅路径不含域名，如 `/v1/search`）
   - 第 3 行：`X-KB-Actor` 原值
   - 第 4 行：`X-KB-Timestamp`（Unix 秒整数字符串，窗口校验 `abs(now - int(stamp)) <= max_age`，默认 `300s`）
   - 第 5 行：`X-KB-Nonce`（长度 `16..128`，重放窗口保留 `2 * max_age + 1` 秒）
   - 第 6 行：`sha256(raw_request_body_bytes).hexdigest()`（裸 64 位小写十六进制）
   - 第 7 行（可选扩展）：`X-KB-Agent` 原值或 `""`
   - 第 8 行（可选扩展）：`X-KB-Purpose` 原值或 `""`
3. `X-KB-Signature`：`HMAC-SHA256(secret_utf8, canonical_message_utf8).hexdigest()`（密钥最小长度 32 字节）。

以下为脱敏测试专用向量（`TEST_ONLY_DO_NOT_USE_IN_PROD_*`，经 Python 实算验证，供团队 B TypeScript 侧直接单测复现）：

```json
{
  "test_only_secret": "TEST_ONLY_DO_NOT_USE_IN_PROD_0123456789abcdef",
  "method": "POST",
  "path": "/v1/search",
  "body_utf8": "{\"query\":\"clinical protocol\",\"kb_id\":\"kb-001\",\"top_k\":5}",
  "body_sha256": "67bafaa708c0e69fee5a7d91f4fe5b6887991bed828967aeeabd6592f983fc95",
  "canonical_lines_count": 8,
  "headers": {
    "X-KB-Actor": "eyJhbmNlc3Rvcl9kZXBhcnRtZW50X2lkcyI6W10sImNsZWFyYW5jZV9sZXZlbCI6IiIsImNsZWFyYW5jZV90YWdzIjpbXSwiZGVwYXJ0bWVudF9pZHMiOlsiZGVwdC1yZCJdLCJtYW5hZ2VkX2RlcGFydG1lbnRfaWRzIjpbXSwib3JnX2lkIjoidGVuYW50LXNhbmRib3gtMDEiLCJvcmdfcm9sZXMiOltdLCJwb2xpY3lfZ2VuZXJhdGlvbiI6IjEiLCJwdWJsaWNfa2JfYWRtaW4iOmZhbHNlLCJyb2xlcyI6WyJtZW1iZXIiXSwic2Vzc2lvbl9pZCI6InNlc3MtdGVzdC0wMDEiLCJ1c2VyX2lkIjoidXNyLTAxOTRmMDAwLTAwMDEifQ==",
    "X-KB-Agent": "eyJhZ2VudF9pZCI6ImFnZW50LW9wZW5ib3QtMDEiLCJvcmdfaWQiOiJ0ZW5hbnQtc2FuZGJveC0wMSJ9",
    "X-KB-Purpose": "ground_internal_llm",
    "X-KB-Timestamp": "1795478400",
    "X-KB-Nonce": "nonce-test-0123456789abcdef",
    "X-KB-Signature": "b968dc3d58e70523a9818da596703ac7a4c23110a90bd339d64a14a604b4716e"
  }
}
```

### 2.3 立即交付：policy_generation 边界用例表（v2 契约严格 fail-closed）

| 输入样例 | `/v2` 预期结果 | 错误码 | 说明 |
|---|---|---|---|
| `1`（等于或大于存储代数） | 允许进入策略校验 | — | 正常基线 |
| `9007199254740991`（`2^53 - 1`） | 允许进入策略校验 | — | JS/TS 安全整数上限 |
| `1`（存储代数已推进至 `2`） | 拒绝（HTTP `401`/`403`） | `POLICY_GENERATION_STALE` | 撤权或权限变更后旧令牌失效 |
| `0` / `-1` | 拒绝（HTTP `400`） | `VALIDATION_ERROR` | 非正整数严禁接受 |
| 缺失 / `null` | 拒绝（HTTP `400`） | `VALIDATION_ERROR` | `/v2` 禁止隐式默认 |
| `"1"` / `"abc"` / `true` / `1.5` | 拒绝（HTTP `400`） | `VALIDATION_ERROR` | 禁止字符串/布尔/浮点静默强转 |
| `9007199254740992`（`2^53`） | 拒绝（HTTP `400`） | `VALIDATION_ERROR` | 超过安全整数上限溢出拒绝 |

---

## 三、对最小集成切片候选（Minimum Slice Candidate）的正式回签

**总体结论：确认接受团队 B 提出的最小集成切片范围、数据流、排除项与全部 10 项验收条件，并附两项精准契约补强以确保验收项可机器闭环验证：**

1. **切片范围确认**：完全同意限定在**隔离的非生产企业租户**（已有显式成员关系）+ 1 名人类用户操作 1 个已授权 Agent + 1 个主空间与小文档；不推断任何默认个人租户策略；旧生产引擎保持唯一权威，不启用生产影子或双写。
2. **显式排除项确认**：完全同意首切片排除 `purge`、异步 `IngestionJob`、跨空间引用、`service` 主体与自动历史迁移。
3. **补强一（闭环验收第 10 项“写重试不重复生成版本”）**：
   - 虽然首切片排除了异步 `IngestionJob` 并采用同步文档摄取，但为使验收条件 10（`mutation retry cannot duplicate versions`）在 HTTP 重试场景下可严格成立，建议在最小切片的同步写接口（创建空间、同步摄取文档）中**显式支持 `Idempotency-Key` 请求头**：
     - 作用域：`(tenant_id, endpoint, idempotency_key)` + 规范化请求载荷 SHA-256；
     - 同键同载荷重试：幂等返回首次结果（不新增空间、不递增版本号）；
     - 同键异载荷重试：返回 `409 IDEMPOTENCY_CONFLICT`；
     - 未携带 `Idempotency-Key` 的写请求：客户端严格禁止自动重试。
4. **补强二（闭环验收第 7、8、9 项证据与受控草稿约束）**：
   - `verify_citation` / 版本锁定证据校验在首切片中明确按裸 64 位小写十六进制 `excerpt_hash` + `(tenant_id, doc_id, version, anchor_id/chunk_id)` 在实时权限与撤权校验下执行：摘要篡改返回 `TAMPERED_EXCERPT`，历史映射缺失返回 `ANCHOR_UNRESOLVABLE` / `RESOURCE_NOT_FOUND`，绝不降级猜测；
   - 写入/回滚响应强制返回 `created_version`、`current_version`、`lifecycle_state` 与 `activated`，确保受控 `l2_controlled` 草稿绝不被误呈为当前发布内容。
5. **验收条件确认**：完整接受团队 B 全部 10 项验收断言（无权用户+绑定 Agent 拒绝、有权用户+未绑定 Agent 拒绝、缺失/歧义身份或租户拒绝、跨租户拒绝、成员/Profile/Principal 撤权拒绝、SDK 不可用时绝不回退至更宽松数据源、证据哈希与版本保真、历史映射缺失显式失败、受控草稿不冒充当前发布版、写重试不重复生成版本）。

---

## 四、团队 A Wave1.5 补充要求（同步并入 `feat/align-wave1p5-m1-readiness`）

为无缝响应团队 B 上述 7 项技术差异并支撑团队 B 产出最终冻结候选包，团队 A 工程实施代理在当前 **Align-Wave1.5** 分支交付物中补充纳入以下 5 项轻量契约资产（仍不改动 Schema v5、不抢跑 `/v2` 运行时、不触碰 `main`）：

1. `contracts/contract-fixtures/identity-lifecycle-fixtures.json`：`(tenant_id, issuer, raw_sub)` 唯一性、换 IdP 显式迁移、禁止跨 IdP 邮箱自动关联及撤权负向夹具。
2. `contracts/contract-fixtures/policy-generation-cases.json`：覆盖正常、陈旧、`0`、负数、缺失、类型错误、安全整数溢出全部 7 类边界用例。
3. `contracts/contract-fixtures/hash-vectors-utf8.json`：归档本函 2.1 节 4 组实算 UTF-8/Unicode 向量（裸 64 位小写十六进制 + `hash_algorithm: "sha256"`），并同步移除 `openapi-v2-draft.yaml` 及既有夹具中残留的 `sha256:` 前缀示例。
4. `contracts/contract-fixtures/signed-request-canonicalization.json` + 脱敏请求/响应样例：归档本函 2.2 节签名规范化规则与 `200`/`403`/`409`/`422` 脱敏 HTTP 线协议完整请求/响应捕获（零真实密钥）。
5. 修订 `openapi-v2-draft.yaml` 与 `openbot-adapter-dto.d.ts`：补齐回滚/写入 DTO 的 `created_version`、`current_version`、`lifecycle_state`、`activated`、`rollback_scope` 五字段，以及首切片同步写接口可选 `Idempotency-Key` 请求头定义与 `validate_assets.py` 校验覆盖。

---

## 五、6 项 Pending 架构待决事项与下一轮冻结交接路径

1. **6 项架构待决事项仍全量保持 `Pending`**（仅架构决策负责人书面签认方可变更为 `Frozen`）：
   - 个人空间租户归属（企业内 `space_type=personal` vs 独立 `personal:<user_id>`）与多组织切换/离职交接；
   - 单权威主空间 + 独立引用关系模型（确认单空间 `detach` 绝不全局归档）；
   - `service` 主体独立授权策略；
   - 最终 HTTP API 演进方案（双方一致建议保留 `/v1` 并行新增标准 JSON `/v2`）与本最小集成切片冻结边界；
   - 生产影子、历史迁移与切流门槛；
   - Schema v6 是否持久化非安全业务元数据快照 `document_versions.metadata_snapshot`（安全元数据永久不回滚已成定论）。
2. **下一轮交接动作**：
   - **团队 B**：依据本回签与 2.1–2.3 节精确规约，整理带 Schema 哈希与测试夹具的 **M1 精确冻结候选包**，同时继续推进 OpenBot 全调用链审计与安全补丁收口；
   - **团队 A**：完成并独立验收 **Align-Wave1.5**（交付 `M1_DECISION_PACKAGE.md`、`m1-freeze-manifest.json`、上述 5 项补充夹具、TS `uri-mapping.ts` 参考实现与 `deploy/openbot-sandbox/`），并提名 Wave1.5 精确 Commit SHA；
   - **架构决策负责人**：审阅双方会合后的单页 `M1_DECISION_PACKAGE.md` 与最小切片冻结候选包，完成 6 项裁决书面拍板，随后正式启动团队 A **Wave2（M2 Integration Ready）** 与团队 B Adapter 接入联调。
