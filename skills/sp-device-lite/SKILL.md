# C3 / C3X Lite 硬件与 SpDevBeep

适用于 **comma three（C3 / `tici`）** 或 **comma threeX（C3X / `tizi`）** 无功放变体，不是 Prime 订阅 Lite。C4（`mici`）不算 Lite。

## 识别

```text
get_sp_device_hw()  → lite, device_type, product_label, beepd_eligible
get_host_environment() → hardware_profile.lite, comma_device
tici_info()           → lite, device_type (tici|tizi), audio_feedback
```

- `lite: true` — `LITE=1` 或 `i2cget -y 0 0x10 0x00` 失败（仅 tici/tizi）
- `device_type: tizi` + `lite: true` — C3X Lite
- `beepd_eligible: true` — `lite` 且 `SpDevBeep=1`

## 工具

| 工具 | 用途 |
|------|------|
| `get_sp_device_hw` | Lite 快照、蜂鸣、Panda 数量 |
| `set_sp_dev_beep` | offroad 设置 `SpDevBeep`（仅 Lite C3/C3X） |
| `list_sp_settings` | Lite 下 `lite_unavailable` 标注 |

## 策略

- **禁止 AI 写入**：`RecordAudio`、`AlwaysOnDM`
- 完整音频版 C3/C3X 调用 `set_sp_dev_beep` 会报错
- Lite → `beepd`；完整版 → `soundd`

## 参考

- `ai/docs/COMMA_DEVICES.md`
- `launch_chffrplus.sh` — `set_lite_hw()` 匹配 `tici|tizi`
