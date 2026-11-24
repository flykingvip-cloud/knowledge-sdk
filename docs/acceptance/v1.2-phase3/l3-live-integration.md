# L3 — 实际执行与明确空白

执行时间见 `l3-local-http.log`（Asia/Shanghai）。

## 本地真实 HTTP：已执行

命令：

```sh
PYTHONPATH=src .venv-http/bin/python -W error::ResourceWarning docs/acceptance/v1.2-phase3/live_http_probe.py
```

原始证据：`l3-local-http.log`，不是 TestClient/mock/浏览器替代物。脚本绑定系统分配的空闲 loopback 端口，业务 v2 库及独立 SQLiteReplayStore 均位于新建临时目录，随机签名密钥只注入子进程环境且不输出，不读 .env。

实测：MD/CSV 经 HttpKnowledgeClient 真实上传；list/get/reference/consume；重复/章节移动 pending、普通用户/限域 agent 不得确认、管理员确认后可消费；删除 orphaned 不可强制确认；CSV 单位/阈值与脱敏后 quote/hash/cell_ref；签名 external 默认 403、明确 rights 后 200；agent 范围 403；缺 hook 403/denied；SQLite nonce 重放 200→401；body agent/purpose/policy_context 注入 400；既有 `/kb/ui` 与静态 i18n 的 HTTP 合约。

脚本 finally 发送 SIGTERM 并 wait 子进程退出；原始日志有完整 Uvicorn shutdown。returncode=-15 是主动终止所启动的专用进程（不是遗留服务）；业务/replay 临时库随后删除。probe 自身 exit_code=0，无常驻服务。没有调用外部模型/embedding/Qdrant，未触及既有集合。

## 不能声称通过的部分

| 分项 | 状态 | 原因 |
|---|---|---|
| 在线 Qdrant / 实际向量服务 | SKIPPED | 未配置隔离 live URL；3 项旧 live tests 跳过 |
| 在线 embedding / 语义质量 | SKIPPED | 未配置隔离 URL/model，无模型调用 |
| 真实反向代理/root_path 部署 | NOT_RUN | 未部署真实代理，不用本地 HTTP 冒充 |
| 真实 PDF bbox/OCR | NOT_RUN | B02 只有宿主离线 layout fixture；没有新增核心 PDF/OCR 实现 |

本地 HTTP 成功不抹平 Phase1/2 的在线语义/反代/浏览器空白，不合并五层统计。
