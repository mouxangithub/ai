# OpenClaw 借鉴笔记（op助手）— 更新版

参考：[OpenClaw](https://github.com/openclaw/openclaw) · [Architecture](https://docs.openclaw.ai/concepts/architecture)

## 已落地（完整）

| 能力 | 实现 |
|------|------|
| WS hello 快照、stateVersion、幂等、lane | `sync_hub`, `session_store`, `chat_jobs` |
| 多专员编排 | `agents/orchestrator.py` |
| 模型 failover | `model_router.py` + **设置 → 备用模型** UI |
| Plugin hooks | `hooks/registry.py` + `hooks/builtin.py`（行驶写保护、审计、Canvas、Sidecar） |
| WS 协议 v2 | `sync_protocol.py` connect 握手 + inbound/outbound 校验 |
| agent.wait + runId | `wait_for_job`, chat job API |
| 会话 compaction | `session_compaction.py` |
| Skills 快照 | `skills/snapshot.py` |
| Stuck 诊断 | `stuck_job_watchdog_loop` |
| Command queue | steer / followup / **collect（合并）** |
| Canvas | 筛选、Markdown、导出 JSON |
| Web 终端 + Sidecar | `terminal.py`, `sidecar_hub.py`, `terminal-sidecar.js` |
| **Heartbeat 巡检** | `workspace/HEARTBEAT.md` + `heartbeat.py` + scheduler `heartbeat_tick` |
| **SOUL/AGENTS/TOOLS 人设** | `workspace/*.md` 注入 system prompt + REST API |
| Usage 详情 API | `/api/ai/usage/detail` |
| 前端模块化 | `web-api.js`, `web-sync-ws.js`, `web-chat-jobs.js`, `session-sync.js`, … |
| **Gateway 会话同步** | 见 `SESSION_SYNC.md` — WS hello + stateVersion + 内存 SessionStore（无 localStorage 主存储） |
| 应用工厂 | `server/app_factory.py`（`aid.py` 薄入口） |

## 行驶中 Shell 策略

- **允许**：`run_shell` / `run_shell_command`、Web PTY 终端（诊断）
- **禁止**：转向/刹车/油门等控车命令（`shell.py` 正则 + hooks 永久拦截）
- **静止才允许**：write_param、restart 等写操作（非 admin）

## 刻意不做 / 低优先级

| OpenClaw 能力 | 说明 |
|---------------|------|
| 多通道 Ingress（WhatsApp/Telegram） | 聚焦车载 Web |
| MCP 插件生态 | 远期；已有内置 tools |
| Subagents 递归 | 扁平专员编排已够用 |
| Tailscale Gateway | 局域网优先 |

## Command queue 三种模式

| 模式 | 行为 |
|------|------|
| **steer（抢占）** | 行驶中立即取消当前 job，发送新消息 |
| **followup（排队）** | 当前 job 完成后，**逐条**处理队列 |
| **collect（合并）** | 行驶中多条消息**合并为一次**用户轮次再发送 |

## 配置

### 备用模型

设置 → 模型 → **备用模型（Failover）** → 添加行 → 保存

### Workspace 文件

`ai/workspace/SOUL.md`、`AGENTS.md`、`HEARTBEAT.md` 等；API：`GET/POST /api/ai/workspace`

## 验证清单

1. 主模型 API Key 错误时，备用模型自动接管（日志见 `resolvedModel`）
2. WS 连接先发 `connect`，收到 `connect_ack` + `hello`
3. 行驶 + 合并模式：连发 3 条 → 当前 job 结束后 1 次合并请求
4. 工具返回 `report` → Canvas 面板 + 可导出 JSON
5. AGNOS 上 Web 终端可交互 bash；行驶中仍可用；终端旁显示 tool sidecar
6. Scheduler「Heartbeat 巡检」每 30 分钟 tick
