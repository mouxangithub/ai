# 无法开启 OP

顺序：`trip_review` → SecOC/指纹 → 摄像头/进程 → Panda

## Lite C3 / C3X（无功放）

若 `get_host_environment` / `get_sp_device_hw` 显示 `lite: true`（`device_type` 为 `tici` 或 `tizi`）：

1. **不要**依赖 `soundd` 或驾驶员监控（`dmonitoringd`）——Lite 上这些进程不启动。
2. 需要声音反馈时：`set_sp_dev_beep(true)`，确认 onroad 后 `beepd` 运行（`SpDevBeep=1`）。
3. **勿**写入 `RecordAudio`、`AlwaysOnDM`（`params_policy` 会拒绝）。
4. UI 设置列表中 `lite_unavailable` 项可忽略。

丰田/雷克萨斯：`lookup_secoc_tier` + TSK 工具链。
