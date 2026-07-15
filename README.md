# Openpilot AI Agent（op助手）

**专为 openpilot 及社区 fork（Dragonpilot / SunnyPilot / Carrotpilot / IQPilot 等）设计的 AI Agent 助手。**

| 项目 | 说明 |
|------|------|
| 独立仓库 | https://github.com/mouxangithub/ai |
| 安装路径 | `<openpilot>/ai`（车机默认 `/data/openpilot/ai`） |
| 一键安装 | `curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/install.sh \| bash` |
| 自动集成 | 补丁 `params_keys.h` + `launch_chffrplus.sh` + 编译 `params_pyx.so` |
| 详细说明 | [docs/INSTALL.md](docs/INSTALL.md) |

---

# Openpilot AI Agent & Cabana Web

**统一入口：** `http://<c3-ip>:5090`  
**TSK（丰田 SecOC）：** `http://<c3-ip>:5090/?settings=secoc`（设置 → SecOC）  
**Cabana 入口：** 顶栏闪电图标，或 `http://<c3-ip>:5090/?cabana=1`（`/cabana` 会重定向）

本模块把 **op 助手**、**TSK Manager** 与 **Cabana CAN 分析仪** 集成到同一个 `aid` 服务与单页 Web UI。车机上由 `launch_chffrplus.sh` **在 manager 之前**后台启动 `python3 -m ai.aid`（SecOC 流程会 `pkill manager`，aid 需独立存活）。PC 开发机需手动 `python3 -m ai.aid`（只跑 manager 不会起 aid）。Cabana 以弹窗嵌入主界面。

> **品牌：** 已统一为 Openpilot，顶部使用 comma.ai 官方逗号 logo。

---

## 功能总览

| 能力 | 状态 | 说明 |
|------|------|------|
| AI 流式对话 | 已实现 | OpenAI 兼容 API，支持 content + reasoning_content 流式输出 |
| AI 工具调用 | 已实现 | get_vehicle_state / read_params / run_shell / restart_service / restart_ui |
| 工具/思考记录 | 已实现 | 聊天中可折叠显示 tool_calls 与 reasoning_content |
| 车辆状态注入 | 已实现 | 对话上下文自动带入 vEgo、enabled、started、ignition |
| 模型下拉选择 | 已实现 | 自动拉取 `/v1/models`，支持下拉或手动输入 |
| 高级参数配置 | 已实现 | system prompt / temperature / top_p / max_tokens / thinking |
| 保存时连接测试 | 已实现 | 保存配置后自动调用 `/api/ai/test_connection` |
| 聊天记录持久化 | 已实现 | localStorage 保存最近 200 条 |
| API 用量统计 | 已实现 | prompt / completion / total tokens |
| Web 配置弹窗 | 已实现 | Settings / Vehicle Status 两个独立弹窗 |
| 移动端适配 | 已实现 | 响应式布局、底部弹窗 |
| 通知中心 | 已实现 | 顶栏铃铛、未读角标、全部已读；定时任务 / onroad 事件写入队列 |
| Cabana 实时 CAN | 已实现 | 弹窗内 WebSocket 直连本车 `can` topic |
| Cabana 离线回放 | 已实现 | 弹窗「回放」标签：路线选择、播放/暂停/调速、进度 seek |
| Cabana DBC 解析 | 已实现 | 模糊搜索 DBC/车型；读取 `opendbc` 解析信号 |
| Cabana 信号绘图 | 已实现 | uPlot 绘制表格中选中的信号（回放时） |
| Cabana 视频同步 | 已实现 | 离线回放优先 `qcamera.ts`，与 CAN progress 对齐 |
| Cabana → 聊天 | 已实现 | 「发到聊天」「分析 route」携带 CAN 采样与路线摘要 |
| Cabana AI 解释 | 已实现 | 表格内逐信号 AI 说明（只读，行驶中可用） |
| 深色/亮色主题 | 已实现 | AI 与 Cabana 页面均支持 |
| 多语言 i18n | 已实现 | en / zh / ja / ko |
| TSK / SecOC | 已实现 | 设置 → SecOC + `/api/tsk/*`；offroad 屏告警引导打开 URL |
| TSK AI 工具 | 已实现 | 状态查询、查找安装/卸载密钥、CAN/DataFlash 作业（需 confirm） |
| 聊天 TSK 进度卡片 | 已实现 | 工具结果内嵌卡片，忙时轮询 `/api/tsk/summary` |

> **验证状态：** 代码已本地语法检查通过，但 **C3 实机验证仍为 pending**。

---

## AI Agent Web 功能

访问 `http://<c3-ip>:5090`。

### 1. 聊天优先界面
- 全屏聊天区域，输入框在底部。
- 顶部工具栏：车辆状态弹窗、设置弹窗、主题切换、状态 pill。
- 工具开关：可启用/禁用 AI 工具调用。
- 聊天记录自动保存到 localStorage，支持一键清空。

### 2. 流式聊天与工具调用
- `POST /api/ai/chat` 使用 SSE 流返回：
  - `content` 正常回复内容
  - `reasoning` 思考过程（Kimi k2.x 等模型）
  - `tool_call` / `tool_result` 工具调用记录
- 内置工具：
  - `get_vehicle_state`：读取车辆状态
  - `read_params`：读取 Params
  - `run_shell`：执行白名单 Shell 命令
  - `restart_service`：重启服务
  - `restart_ui`：重启 UI
- 工具结果与思考过程均可在聊天中折叠查看。

### 3. 设置弹窗
- Provider 选择（openrouter / openai / kimi / custom）
- Model 下拉自动拉取 `/v1/models`，也可切换手动输入
- API Key（保存后显示掩码）
- Base URL（custom 时显示）
- System Prompt、Temperature、Top P、Max Tokens
- Thinking / Reasoning 开关
- Save 后自动 Test Connection
- 底部显示 API 用量统计

### 4. 车辆状态弹窗
- 显示 vEgo / enabled / started / ignition 四宫格
- 完整 state JSON（含 carState、controlsState、onroadEvents 等）

### 5. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ai/status` | 运行状态与车辆状态 |
| GET | `/api/ai/providers` | provider 列表与默认模型 |
| GET | `/api/ai/config` | 读取配置（API key 已掩码） |
| POST | `/api/ai/config` | 保存配置 |
| GET | `/api/ai/models` | 拉取provider可用模型 |
| GET | `/api/ai/test_connection` | 测试连接与模型是否存在 |
| POST | `/api/ai/chat` | 流式聊天 |
| POST | `/api/ai/shell` | 直接执行白名单命令 |
| GET | `/api/ai/state` | 完整车辆状态 JSON |
| GET | `/api/ai/notifications` | 通知列表（`?unread=1` 仅未读） |
| POST | `/api/ai/notifications` | 全部标记已读 |

---

## TSK Manager（丰田 SecOC）

与 op 助手**同进程、同端口**；详细说明见 [`ai/docs/TSK_AND_AID.md`](docs/TSK_AND_AID.md)。

| 入口 | 说明 |
|------|------|
| `http://<IP>:5090/?settings=secoc` | 手动安装 / 一键提取 / CAN+DataFlash 查找 |
| `GET /api/tsk/summary` | 进度、密钥是否已装、`next_steps` |
| `GET /api/tsk/health` | 设备类型（tici/tizi/mici）、panda 后端、`dry_run` 等 |
| 设备 / pandad 对照 | [`docs/COMMA_DEVICES.md`](docs/COMMA_DEVICES.md) |
| `POST /api/tsk/can-collect` 等 | 与旧 `:11111` API 等价，前缀改为 `/api/tsk/` |

**Offroad 告警：** aid 后台 `offroad_alert_loop` 写入 `Offroad_NoFirmware`，comma 屏显示中文引导 + `%1` 替换为 TSK URL。

**AI 工具（行驶中仅只读）：** `get_tsk_manager_status`；写操作 offroad + `confirm=true`：`tsk_extract_key`、`tsk_install_secoc_key`、`tsk_find_and_install_key`、`tsk_start_can_collect`、`tsk_start_dataflash_dump`、`tsk_clear_cache`、`tsk_uninstall_key`。

> 遗留独立 TSK 服务（`:11111`、`tsk/web/`）已移除；请使用 `:5090` op 助手。

---

## Cabana 弹窗（主界面内）

顶栏 **闪电** 打开 CAN 分析弹窗；`/cabana` 重定向到 `/?cabana=1`。

### 实时 / 回放
- **实时**：`WS /api/cabana/ws`，表格展示解码后的报文与信号值。
- **回放**：`GET /api/cabana/routes` 选路线 → `WS /api/cabana/offline/ws?route=...`，支持 play/pause/speed/seek；`metadata.media` 提供 `qcamera.ts` 视频 URL。

### DBC、绘图、AI
- DBC 支持中文车型模糊搜索（`GET /api/cabana/dbcs` 含 catalog）。
- 回放时点击「绘图」用 uPlot 叠加信号曲线。
- 「AI 解释」逐信号说明；「发到聊天」「分析 route」把 CAN 采样 + 路线摘要送入主聊天。

### Cabana API（节选）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cabana/car` | CarParams 与建议 DBC |
| GET | `/api/cabana/dbcs` | DBC 列表 + 车型索引 |
| GET | `/api/cabana/routes` | 本地路线列表 |
| GET | `/api/cabana/route/{name}/media` | 路线内视频分段 |
| GET | `/api/cabana/route/{name}/summary` | 路线摘要 |
| WS | `/api/cabana/ws` | 实时 CAN |
| WS | `/api/cabana/offline/ws` | 离线 qlog 回放 |
| POST | `/api/cabana/explain` | 单信号 AI 解释 |

---

## 参数说明

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `ai_provider` | string | provider |
| `ai_model` | string | 模型 ID |
| `ai_api_key` | string | API Key |
| `ai_base_url` | string | 自定义 Base URL |
| `ai_system_prompt` | string | 系统提示词 |
| `ai_temperature` | string | 温度（思考模型自动忽略） |
| `ai_top_p` | string | Top P |
| `ai_max_tokens` | string | 最大 tokens |
| `ai_thinking_enabled` | bool | 思考模式开关 |
| `ai_thinking_keep` | string | Preserved Thinking（Kimi k2.6/k2.7） |
| `ai_usage_log` | string | API 用量日志 JSON |

---

## 已知限制

1. **C3/C3X/C4 实机验证 pending**：Windows 无法直接 import openpilot Python 包，运行时功能需 comma 设备验证。
2. **HEVC 浏览器播放**：离线回放优先 `qcamera.ts`；`fcamera.hevc` 等多数浏览器无法直接播放，仅作文件列表。
3. **模型下拉刷新**：依赖 provider `/v1/models` 接口可用。
4. **工具调用安全**：shell / restart 类工具仅在车辆静止时允许。

---

## C3 / C4 部署与自检

### 前置条件

1. **`common/params_keys.h` 与 `ai/common/params.py` 已包含全部 `ai_*` / `ai_embedding_*` 键**（本仓库已登记）；刷机后需完整编译 openpilot，否则 `Params.put` 会报 unknown param。
2. **车机启动 `ai.aid`**：`launch_chffrplus.sh` 在 manager 之前用 **`/usr/local/venv/bin/python`**（AGNOS 含 aiohttp）执行 `python -m ai.aid &`，日志 `/tmp/aid.log`。
3. **Python 依赖**：`aiohttp`（与 openpilot 主环境一致，无额外 pip 包）。
4. **网络**：云端对话 / embedding 需 WiFi；无网时 RAG 回退关键词，内置 FAQ 仍可用。

### 启用步骤（车机）

```bash
cd /data/openpilot
# 拉取含 ai/ 的 fork 后全量编译安装（按你方 Dragonpilot 流程）
# 正常开机后 launch_chffrplus.sh 会自动拉起 aid
pgrep -af 'ai.aid'   # 应看到进程
```

浏览器访问：`http://<设备IP>:5090`（SecOC：设置 → SecOC 或 `/?settings=secoc`）

### PC 开发（本地 aid + TSK）

```bash
cd openpilot && source .venv/bin/activate   # 或 tools/op.sh setup
python3 -m ai.aid
# 浏览器 http://127.0.0.1:5090  与  http://127.0.0.1:5090/?settings=secoc
```

非 AGNOS 上 TSK 为 `dry_run`（无真实 panda 作业）；可测页面、API 与助手 TSK 工具。真车 SecOC 必须在 comma 设备 offroad 操作。

### 首次启动自动行为

- 写入 **4 条内置知识库 FAQ**（SecOC / Engage 分诊 / 适配 SOP / 2024 Sienna 提示），仅一次；可在知识库删除。  
- 向量索引需配置 embedding 后点「重建向量索引」或上传新文档时自动 embed（需 WiFi + API Key）。

### 设备路径（可写）

| 路径 | 用途 |
|------|------|
| `/data/openpilot/ai_rag_vectors.json` | RAG 向量（自动创建） |
| `/data/openpilot/adaptation_drafts/` | 适配草稿（自动创建） |
| Params `ai_rag_documents` | 知识库元数据 |

### 常见报错与处理

| 现象 | 原因 | 处理 |
|------|------|------|
| `aid` 进程不存在 | 用了裸 `python3`（无 aiohttp）或 aid 崩溃 | `pgrep -af ai.aid`；`tail /tmp/aid.log`；应用 `/usr/local/venv/bin/python -m ai.aid` |
| 页面 502 / 连不上 | 防火墙或 aid 未起 | `pgrep -af ai.aid`；看 manager 日志 |
| 保存 embedding 配置失败 | 新 Param 未编译进固件 | 确认 `params_keys.h` 已更新并重新 build |
| 知识库 embed 失败 | 无 API Key / 无网 | 用关键词检索；配置 API 后重建索引 |
| Cabana 无 DBC | opendbc 未安装或路径异常 | 确认 fork 含 opendbc；看 aid 日志 |
| `trip_review` cereal 错误 | 非 onroad 无 CarParams | 正常；SecOC 提示可能为空 |
| 写草稿被拒绝 | 行驶中 | 停车后再 `save_adaptation_draft` |

### 安全提醒

- `SecOCKey`：**AI 不可写**；用户通过设置 → SecOC 或 TSK 工具（`tsk_extract_key` / `tsk_install_secoc_key` / `tsk_find_and_install_key`）安装，Dashy 可核对。  
- 行驶中：写 Param / shell / 草稿 均被 `safety.py` 拦截。  
- LAN 访问建议设置 **Web PIN**（`ai_web_pin`）。

> **验证状态**：模块已语法检查；C3/C3X/C4 实机请在停车 WiFi 下按上表自检一遍。
