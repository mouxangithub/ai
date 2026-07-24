# Comma 设备与 Panda / Pandad 对照

> **单一事实来源**：`ai/tsk/lib/panda_connect.py` 与本文档。技能、工具描述、Web UI 均以此为准。

## 产品映射

| 产品 | `device_type` | 内部 panda MCU | `panda_backend` | `pandad_process` | `pandad_module` |
|------|---------------|----------------|-----------------|------------------|-----------------|
| comma three（**C3**） | `tici` | F4 (DOS) | `panda_tici`† | `pandad_tici`† | `selfdrive.pandad_tici.pandad`† |
| comma threeX（**C3X**） | `tizi` | H7 | `panda` | `pandad` | `selfdrive.pandad.pandad` |
| comma four（**C4**） | `mici` | H7 | `panda` | `pandad` | `selfdrive.pandad.pandad` |

† 仅当仓库中 **同时** 存在 `panda_tici` 与 `selfdrive/pandad_tici` 时使用；缺任一则 F4 也回退 `panda` + `pandad`。

**常见误区（已纠正）：**

- C3X **不是** F4；C3X（`tizi`）与 C4（`mici`）同为 H7 / `TICI_TRES`，使用 `panda` + `pandad`。
- C3（`tici` / F4）在 tici 栈存在时用 **`pandad_tici` 进程**，但 **F4 固件文件来自 `panda/`**，不是 `panda_tici/`（详见 [`PANDA_FLASH.md`](PANDA_FLASH.md)）。
- **红熊（H7）** 外接由 `panda_tici` 自动刷机；**黑熊 / DOS（F4）** 不自动刷，用 `recover_dos_panda`。

## sunnypilot C3 DOS 固件（必读）

| Panda | 固件路径 | 自动刷机 | 手动工具 |
|-------|----------|----------|----------|
| 内置 DOS (F4) | `panda/board/obj/panda.bin.signed` | 否（DOS 快速路径） | `recover_dos_panda(internal=true)` |
| 外接黑熊 (F4) | 同上 | 否 | `recover_dos_panda(external=true)` |
| 外接红熊 (H7) | `panda_tici/board/obj/panda*.bin.signed` | 是（`pandad_tici`） | 一般不需手动 |

CLI：`ai/scripts/recover_dos_panda.py`；op 助手技能：`c3-dos-panda`。

## 检测顺序

1. 环境变量 `TICI_DOS` / `TICI_TRES`（`launch_chffrplus.sh` 或 `ensure_tici_env()`）
2. `/persist/sp_dev_panda_mcu_type`（`F4` / `H7`）；若无则回退 `/persist/dp_dev_panda_mcu_type`（openpilot/dragonpilot 遗留）
3. devicetree：`/sys/firmware/devicetree/base/model` → `comma tici|tizi|mici`
4. 查询内部 panda MCU（兜底）

**PC 开发机**：无 devicetree 时，`get_host_environment` 会调用 `probe_pc_panda()`，优先经已安装的 **`panda_tici`**（否则 `panda`）读取 MCU（F4→C3 类，H7→C3X/C4 类）；后端选择同样要求 tici 包成对存在。

## API 字段

| 接口 / 工具 | 字段 |
|-------------|------|
| `GET /api/tsk/health` | `device_type`, `product_label`, `pandad_process`, `panda_backend`, … |
| `get_tsk_manager_status` | 同上（嵌套在 `tici` 对象，历史命名） |
| `get_host_environment` | `hardware_profile`（含 `comma_device` 别名）、`host_kind_label`、Panda MCU、进程状态 |
| `device_health` | `board` = `device_type` |
| `panda_status` | `pandas`, `usb_all`, `usb_f4`, `usb_h7`, `multi_panda`, `pandad_snapshot`, `firmware_path`, `dos_note` |
| `list_all_pandas` | 全部 Panda、`hw_type_name`、`multi_panda.scenario`、`pandad` 进程 |
| `list_f4_pandas` | `f4_pandas`, `internal`, `firmware_exists`（含 `list_all_pandas` 子集） |
| `recover_dos_panda` | 刷 F4 固件（`confirm=true`） |

## TSK / 黑屏相关行为

- CAN 采集、DataFlash 导出、UDS 提取前会 `stop_manager_and_pandad()`，**只杀当前设备对应的 pandad 模块**，不会 `pkill pandad` 误伤另一变体。
- `tsk_restart_pandad` / 设置页「重启 pandad」：按 `pandad_module` 实际选择（可能为 `pandad` 或 `pandad_tici`）。
- PC 开发（非 AGNOS）上 TSK 为 `dry_run`，无真实 panda；`panda_backend` 默认为 `panda`。
- 刷 F4 固件后：建议 `rebuild_pandad_tici` + reboot（`updated` 可能删除编译产物）。
- **C3 DOS + 外接红熊（F4 + H7 双 USB）**：需 `pandad_tici` 同时打开两只设备；详见 [`PANDA_FLASH.md`](PANDA_FLASH.md)「异构双 Panda」。

## 相关文档

- [`PANDA_FLASH.md`](PANDA_FLASH.md) — DOS/黑熊刷机流程与禁忌
- [`TSK_AND_AID.md`](TSK_AND_AID.md) — TSK 与 op 助手集成
- [`VEHICLE_ADAPTATION_GUIDE.md`](VEHICLE_ADAPTATION_GUIDE.md) — 车辆适配与 SecOC
- 技能 `c3-dos-panda` — op 助手排障顺序

## C3 Lite（无功放 / 无麦克风）

**Lite** 指 comma three（`tici` / **C3**）上 **I2C 音频功放 `0x10` 不存在** 的硬件变体，与订阅档位 `PrimeType.LITE` **无关**。C3X（`tizi`）与 C4（`mici`）**不**走 Lite 进程策略（与 `launch_chffrplus.sh` 的 `set_lite_hw()` 一致）。

| 检测 | 说明 |
|------|------|
| `LITE=1` | `launch_chffrplus.sh` 在 `set_lite_hw()` 中设置（仅 `tici`） |
| `i2cget -y 0 0x10 0x00` 失败/空 | 无功放 → 判定为 Lite（仅 `tici`） |
| `ai.system.hardware_lite.detect_lite_hw()` | op 助手统一入口 |

### 进程差异（`system/manager/process_config.py`）

| 进程 | 完整 C3 | Lite C3 |
|------|---------|---------|
| `micd` | 开 | **关** |
| `soundd` | 开 | **关** |
| `dmonitoringmodeld` / `dmonitoringd` | 开 | **关** |
| `beepd` | 关 | **开**（需 `SpDevBeep=1` 且 onroad） |
| `modemd`（TICI） | 开 | **关** |

### op 助手 API / 工具

| 接口 | Lite 相关字段 |
|------|----------------|
| `tici_info()` / `host_hardware_profile` | `lite`, `device_type`, `product_label`, `lite_capable`, `beepd_eligible`, … |
| `get_host_environment` | `hardware_profile.lite`；Lite 时 `hint` 提示勿写 RecordAudio/AlwaysOnDM |
| `get_sp_device_hw` | 同上 + `SpDevBeep` |
| `set_sp_dev_beep` | 仅 Lite C3 有效；完整音频版返回 error |
| `list_sp_settings` | `lite_unavailable` + `lite_note` 标注不可用项 |
| `write_params` / `params_policy` | **拒绝** `RecordAudio`、`AlwaysOnDM`、`DistractionDetectionLevel` |

### 用户反馈替代

- 完整 C3：`soundd` 语音/提示音
- Lite：`SpDevBeep=1` → onroad 启动 `beepd`（GPIO 蜂鸣），见 `sunnypilot/selfdrive/ui/beepd.py`

### 技能

- `sp-device-lite` — 硬件识别与 SpDevBeep
- `engage-troubleshooting` — Lite 无 DM/声音时的排障顺序
- `c3-dos-panda` — C3 DOS/黑熊/红熊多 Panda 刷机与 NO PANDA 恢复
