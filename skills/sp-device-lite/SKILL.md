# C3 Lite 硬件与 SpDevBeep

适用于 **comma three（C3 / tici）无功放** 变体，不是 Prime 订阅 Lite。

## 识别

```text
get_sp_device_hw()  → lite, beepd_eligible, SpDevBeep, board
get_host_environment() → hardware_profile.lite, comma_device
tici_info()           → lite, audio_feedback ("beepd" | "soundd")
```

- `lite: true` — `LITE=1` 或 `i2cget -y 0 0x10` 失败
- `beepd_eligible: true` — `lite` 且 `SpDevBeep=1`

## 工具

| 工具 | 用途 |
|------|------|
| `get_sp_device_hw` | 快照：Lite、蜂鸣、Panda 数量 |
| `set_sp_dev_beep` | offroad 设置 `SpDevBeep`（仅 Lite C3） |
| `list_sp_settings` | Lite 下带 `lite_unavailable` 标注 |

## 策略

- **禁止 AI 写入**：`RecordAudio`、`AlwaysOnDM`（无麦克风 / 无 DM 进程）
- 完整 C3（`lite: false`）调用 `set_sp_dev_beep` 会报错
- 反馈路径：Lite → `beepd`；完整 C3 → `soundd`

## 参考

- `ai/docs/COMMA_DEVICES.md` — Lite 进程对照
- `launch_chffrplus.sh` — `set_lite_hw()`
- `system/manager/process_config.py` — 进程开关
