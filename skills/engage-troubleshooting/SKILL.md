# 无法开启 OP

顺序：`trip_review` → **Panda（C3 DOS）** → SecOC/指纹 → 摄像头/进程 → 车型

## 侧栏 NO PANDA / Panda 离线（C3 DOS）

1. `panda_status` — `pandaStates`、USB F4、`firmware_exists`
2. `panda_recovery_hint` — 推荐工具链
3. `grep_log` — `pandad|panda|xhci|DOS internal`
4. offroad：`tsk_restart_pandad(confirm=true)`
5. 仍失败 → 技能 **`c3-dos-panda`**：`list_f4_pandas` → `recover_dos_panda(confirm=true, internal=true)`
6. `updated` 后：`rebuild_pandad_tici(confirm=true)` + `reboot_device`

**禁忌**：F4 不要用 `panda_tici` 固件；见 `ai/docs/PANDA_FLASH.md`。

## Lite C3（无功放）

若 `get_host_environment` / `get_sp_device_hw` 显示 `lite: true`（`device_type` 为 `tici`）：

1. **不要**依赖 `soundd` 或驾驶员监控（`dmonitoringd`）——Lite 上这些进程不启动。
2. 需要声音反馈时：`set_sp_dev_beep(true)`，确认 onroad 后 `beepd` 运行（`SpDevBeep=1`）。
3. **勿**写入 `RecordAudio`、`AlwaysOnDM`（`params_policy` 会拒绝）。
4. UI 设置列表中 `lite_unavailable` 项可忽略。

丰田/雷克萨斯：`lookup_secoc_tier` + TSK 工具链。
