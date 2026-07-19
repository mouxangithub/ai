# TSK Manager 与 op 助手（aid）合并架构

## 来源说明

本仓库 **TSK Web（丰田 SecOC 管理界面）** 及 `:5090` 上 **设置 → SecOC** 相关能力，源自社区项目：

**https://github.com/optskug/openpilot**

代码已迁入 `ai/tsk/` 并与 op助手共用 `ai.aid` 进程。使用或再分发时请保留对 optskug 社区的致谢。

---

## 为什么合并

丰田 SecOC 提取流程会 **停止 manager**（`pkill manager`），若 TSK 与 manager 同生命周期，网页与 API 会一起消失。因此 **TSK 与 op 助手共用 `ai.aid` 进程**，并在 `launch_chffrplus.sh` 里 **先于 manager** 启动（但在 `build.py` 编译完成之后）。

| 服务 | 端口 | 说明 |
|------|------|------|
| Dashy | 5088 | 行车设置 UI，保持独立 |
| **op 助手 + TSK** | **5090** | 同一 `aid`：聊天 + 设置 → SecOC + `/api/tsk/*` |

顶层 **`tsk/` 目录已删除**；唯一代码位置为 **`ai/tsk/`**。

## 车机启动顺序

`launch_chffrplus.sh`（节选）：

1. 准备 `/cache/tsk` 等目录  
2. `cd system/manager && ./build.py`（无 `prebuilt` 时）— 编译 `params_pyx` 等原生模块  
3. `python3.12 -m ai.aid`（`PYTHONPATH` 含 openpilot 根 + venv site-packages）  
4. 看门狗每 45s 检查 aid 是否存活  
5. 启动 openpilot manager  

`system/manager/process_config.py` **不再** `always_run` aid。

## URL 与路由

| 路径 | 用途 |
|------|------|
| `http://<IP>:5090/` | op 助手主界面 |
| `http://<IP>:5090/?settings=secoc` | SecOC 设置（手动安装 / 一键提取 / CAN+DF 查找） |
| `http://<IP>:5090/tsk/` | 重定向到 `/?settings=secoc`（兼容旧书签） |
| `GET /api/tsk/health` | 健康检查、`device_type`（C3/C3X/C4）、panda 后端 |
| `GET /api/tsk/summary` | 密钥状态、CAN/DataFlash 进度、`install_options` |
| `POST /api/tsk/extract` | UDS 一键提取 |
| `POST /api/tsk/install-key` | 手动安装 hex 密钥 |
| `POST /api/tsk/can-collect` | 开始 CAN 采集 |
| `POST /api/tsk/dataflash-dump` | 开始 DataFlash 导出 |
| `POST /api/tsk/match` | 查找并安装密钥 |
| `POST /api/tsk/uninstall` | 卸载密钥 |
| `POST /api/tsk/clear-cache` | 清除 CAN/DF 缓存 |

实现：`ai/tsk_routes.py` 注册路由；业务逻辑在 `ai/tsk/service.py`（锁、作业线程、offroad 告警）。

## Offroad 屏告警

TSK 后台循环写入 Param **`Offroad_NoFirmware`**（manager 启动时会清掉，循环会重写）：

```json
{
  "text": "丰田 SecOC 安全密钥\n用手机浏览器打开 %1（op助手 → 设置 → SecOC）",
  "severity": 0,
  "extra": "http://192.168.x.x:5090/?settings=secoc"
}
```

## Panda / Comma 设备适配

完整对照与 API 字段见 **[`COMMA_DEVICES.md`](COMMA_DEVICES.md)**。

| 产品 | `device_type` | 内部 panda MCU | `panda_backend` | `pandad` 进程 | F4 固件路径 |
|------|---------------|----------------|-----------------|---------------|-------------|
| comma three（C3） | `tici` | F4 (DOS) | `panda_tici`† | `pandad_tici`† | `panda/board/obj/panda.bin.signed` |
| comma threeX（C3X） | `tizi` | H7 | `panda` | `pandad` | — |
| comma four（C4） | `mici` | H7 | `panda` | `pandad` | — |

† tici 栈存在时；**F4 固件文件仍来自 `panda/`**，见 [`PANDA_FLASH.md`](PANDA_FLASH.md)。

检测顺序：`TICI_DOS` / `TICI_TRES` 环境变量 → `/persist/sp_dev_panda_mcu_type`（或 legacy `dp_dev_panda_mcu_type`）→ devicetree `device_type`（tici→DOS，tizi/mici→TRES）→ 查询 panda MCU。

由 `ai/tsk/lib/panda_connect.py` 选择模块；停止/重启时 **只** 操作当前设备对应的 `selfdrive.pandad*.pandad` 进程。

## op 助手 AI 工具

见 `ai/skills/secoc-toyota/SKILL.md`（SecOC）与 `ai/skills/c3-dos-panda/SKILL.md`（C3 DOS/黑熊刷机）。工具直连 `ai.tsk.service` 或 `ai.tools.panda_flash_tools`，不经 HTTP 回环。

| 工具 | 用途 |
|------|------|
| `panda_status` / `list_f4_pandas` | 诊断 Panda 连接与 F4 列表 |
| `panda_recovery_hint` | NO PANDA 推荐步骤 |
| `recover_dos_panda` | 刷 `panda/` F4 固件（`confirm=true`，offroad） |
| `rebuild_pandad_tici` | `updated` 后重链 pandad 二进制 |
| `tsk_restart_pandad` | 重启当前设备的 pandad 进程 |

文档：[`PANDA_FLASH.md`](PANDA_FLASH.md)、[`COMMA_DEVICES.md`](COMMA_DEVICES.md)。

## PC 本地开发

```bash
cd openpilot
tools/op.sh setup && source .venv/bin/activate
python3 -m ai.aid
```

- 助手：`http://127.0.0.1:5090`  
- SecOC：`http://127.0.0.1:5090/?settings=secoc`  

## 相关文件

| 文件 | 职责 |
|------|------|
| `ai/aid.py` | HTTP 服务入口 |
| `ai/tsk_routes.py` | `/api/tsk/*` 与 `/tsk/` 重定向 |
| `ai/tsk/service.py` | 状态、作业 API、offroad 告警 |
| `ai/tsk/lib/*` | CAN/DataFlash/匹配/panda 底层 |
| `ai/tools/panda_flash_tools.py` | `recover_dos_panda` / `list_f4_pandas` 工具实现 |
| `tools/recover_dos_panda.py` | CLI 刷 F4 固件 |
| `ai/web/static/js/tsk-panel.js` | 设置侧边栏 SecOC UI |
| `launch_chffrplus.sh` | build 后启动 aid + 看门狗 |
| `ai/scripts/start_aid.sh` | 手动启动 aid（调试用） |
