# Phase 3 接口、兼容与保守边界

本文件仅描述 Q1-M3 实现，不是架构师验收意见。版本保持 1.2.0；不解锁 Phase 4。

## URI / selectors

- 历史格式仍为 `kb://org/{quoted_org}/doc/{quoted_doc}@{version}`；chunk 为 `#chunk={quoted_chunk}`。历史 `parse_uri` 原正则和四元组语义保留，明确拒绝 anchor URI。
- 新 `parse_uri_v2` 返回 `ParsedKBURI`，增加 `#anchor={quoted_anchor}`；正整数版本、单一非空片段、严格 UTF-8 / 百分号编码，禁止原始保留字符和 `%41` 之类非规范别名。百分号十六进制大小写可等价；标识符仅解码一次，`%252F` 是不透明的字面 `%2F`，不会再次解码成路径。
- `build_uri` 保留第四个位置参数和历史空 chunk 行为；`anchor_id` 仅关键字。两种非空选择器冲突；非法类型 fail closed。
- `TEXT_OFFSET` 复用 `SectionQuoteSelector` 存放位置（任务没有定义独立 TextOffsetSelector）；PDF/table/section 各自使用指定 selector。quote 原始空白、大小写、阴性结论、阈值和单位不归一化。元数据深冻结，普通 JSON / tagged transport 都可恢复。

## 解析及重锚

- `ParserRegistry.parse` 保留历史正文；`parse_layout` 使用宿主扩展方法，否则调用旧 `parse(data)` 并包装段落，旧插件不必改签名。仅提供 layout 的插件也可由 `parse` 读取 full_text。
- txt 继续 TextParser；md/markdown 新增结构观察但 **full_text 仍是历史 UTF-8-sig 文本**，包含原始 Markdown 标记。HTML 仍采用历史提取正文，不引入 DOM/网络/渲染器。标题用于路径，不单独生成正文锚点。
- CSV 的 full_text 与历史 `parse` 完全相同，包含标题及空记录分隔；首个非空记录只作表头，每个后续非空数据记录一 span。行号按非空逻辑数据记录从 1 开始（不是物理行号）；Excel cell_ref 按标题行占第 1 行计算。quoted newline 在单元格内原样保留。UTF-8 BOM 在既有解码口径去除，布局表头额外去首列 BOM，不改写旧 full_text。
- **核心没有实现真实 PDF bbox/OCR**。B02 PDF 样例只由离线宿主 LayoutParser 注入确定性版面；测试载荷是 JSON fixture，绝不宣称 PDF 坐标解析器或 OCR 实证。既有 PDFParser.parse 未更改。
- 初次锚点 ID 取 org/doc/version/span 序号/范围/kind/quote hash 的 SHA256 前 32 个十六进制字符，同版本稳定且唯一；引用上下文各至多 48 字符。
- 同 quote 在新版唯一且结构一致，才自动 anchored 并保留原 ID；表头、章节路径或 PDF 页码变化一律 pending。对于同页 PDF，允许重叠 bbox 或唯一对应 span。**页码变化保守 pending**，解决任务中“唯一命中”与“页变需确认”的冲突。
- 只取前两次 exact 出现来证明重复，结合上下文挑选确定性候选；无论如何均 pending，不声称全局最佳候选。没有可验证的同 kind span 时 pending 不可确认；消失为 orphaned，保留原 quote 供授权后的影响追踪，不能强制确认。
- 已 pending/orphaned 的谱系不自动恢复 anchored；重新出现必须先成为可验证 pending，再显式确认。确认要求当前八步读权限和 WRITE_DOCUMENT 权限，校验对应版本实际 slice/hash，并在同一 SQLite 写事务内更新。仅有读权限或 agent 超范围不能确认。
- 新版本保留旧 ID；含有旧 quote / 与旧候选重叠的新增 span 保守不生成另一个自动 anchored 别名。这可能减少合并段落的“新增锚点”数量，防止绕过 pending。没有自动别名洗白，也没有额外工作台确认 UI。
- 不追溯解析历史数据库版本；迁移只建表。已有旧版本无 anchors 时保持无 anchors；相同语义上传仍按旧去重行为返回原版本，不借此静默重写历史。新的语义版本会建立 anchors。

## SQLite v2 / 权威查询

- schema 0/1 都在一个 BEGIN IMMEDIATE 事务内产生完整 v2：DDL、缺列 ALTER、索引/三表、原 JSON 回填八列、user_version=2 一次提交。未使用 executescript；回填失败会连 DDL / version 一起回滚，初始化失败立即关闭连接。未知版本（包括 3）拒绝。
- 回填不改写原 JSON；put_document / set_acl / put_kb 同步文档的八个派生列，与 JSON 更新处于同一写事务。旧空 access_level 仍表示 legacy ACL，不冒称 public。revoked 是生命周期 revoked 或 rights.revoked。
- 既有 document_versions 的主键本来就是 `(doc_id,version)`，可直接满足指定复合外键；doc_id 在现有库全局唯一。anchor 写入额外检查 org，交付端再核对 org/doc/version/anchor_id，不能仅信数据载荷。
- policy_rules 全局 rule_id 旧式主键按协议保留；同名跨租户写入 Conflict，跨租户 delete 不生效。表持久化 **不自动加载/替代构造注入的 engine rules**。evidence_issues 只预建表，没有反馈业务/API/UI。
- keyword_search 原签名/行为保留；pushdown 使用绑定参数，SQL 硬排 archived/revoked，允许 kb_ids/doc_ids IN。生命周期/有效期等仍由权威 engine 判断，不粗滤管理员可读 draft。

## 有界 Authorized Fetch

- 批次：去重后的 `min(max(limit*4,40),500)`、`min(max(limit*12,120),500)`、500；每源每批只取此前缀加 1 条身份 lookahead，最多请求 501 条。lookahead 仅判断“还有没有”，不查询第 501 个文档，不执行其 policy/redaction。
- 多通道以原加权 RRF 合并 ID；跨批 evaluated_keys 全局去重，最多评估 500 个 `(doc,version,chunk)`，每个仅 policy/redact 一次。查询 embedding（仅显式配置 vector/hybrid 时）每次 search 一次，本轮没有在线向量/embedding 调用。
- hits 达标即停止；各源已耗尽则提前停止；keyword 优先 pushdown，无此接口的 custom store 回退旧 keyword_search。全部候选仍回查 SQLite 当前 doc/kb/ACL/chunk/version，不信 vector 的正文/身份/状态。
- `candidate_budget_exhausted=True` 仅在不足 limit、已评估 500 且已知仍有未评估来源时。exact 500 且耗尽为 False；不回传拒绝数、标题或扫描计数。
- 这是有界前缀近似 RRF，不承诺无限召回/全局完整排名；同分 keyword 加身份排序以确定性复现。多源前缀、重复/非法 provider 身份可能降低召回，False 不是完整性证明。达到授权条数不继续拉取后续候选。

## 权限、脱敏、引用与 HTTP

- list/get/confirm/reference/consume/verify/attach 始终走当前八步策略，agent/purpose 只收窄。历史引用仍固定原 version，不将 v1 引用自动重绑到 v2 pending；当前文档撤回/rights 变更立即约束历史引用。
- 脱敏 quote.exact / prefix / suffix、所有 selector 字符串及 parser 描述；为防元数据 **键和值** 旁路，脱敏视图完全省略来源 metadata，仅留 `delivery_view=redacted`。几何/偏移仍表示原来源坐标；section paragraph_hash 清空，quote_sha256 则针对实际交付 quote 重算。原权威 anchor 不回写为脱敏视图。
- 缺 hook 为 redaction_hook_missing，异常/错型/空 quote 为 redaction_failed；无明文回退。anchor 引用只接受实际交付 quote，或包含它且确实位于交付正文中的 excerpt。允许“恰好等于独立交付 quote”的边界，兼容非幂等/上下文相关 hook，不用原文 hash 冒充交付一致性。
- anchor URI 和 KnowledgeRef.anchor_id 必须一致且无 chunk_ids。pending 消费 denied/anchor_drift_pending；orphaned unavailable/anchor_orphaned；anchored 复核原 slice 与实际交付内容/hash，回执 evidence_kind=anchor_excerpt。
- 新端点均 POST：`/v1/anchors/list`、`/v1/anchors/get`、`/v1/anchors/confirm`；Local / HttpKnowledgeClient / KnowledgeClient 均支持。reference/create_ref 新增关键字 anchor_id；所有新方法接受 agent/purpose/policy_context 的本地上下文契约。
- HTTP 保留旧六行 HMAC，扩展身份/用途只经可信签名头；body actor/self/agent/purpose/policy_context 均 400，非法强类型 agent 401。没有新增宿主登录 hook 或前端视觉。

## 未做 / 发布边界

所有数据库迁移仅发生在本轮隔离临时数据库，没有打开任何既有运行库。没有修改 Mac/生产/既有端口服务/Qdrant 集合；没有外部模型调用。真实在线语义/Qdrant、真实反代、浏览器未测，不能由单元或 HTTP 测试替代。B02/B07 供独立复核，不自封架构验收；MCP/Benchmark/Phase 4 未解锁。
