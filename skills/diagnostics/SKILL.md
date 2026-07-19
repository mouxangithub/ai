# 系统健康

## 基础

`device_health`、`list_managed_processes`、`read_manager_log`、`grep_log`、`ota_status`

## Panda / C3 DOS

侧栏 **NO PANDA** 或 `panda_status` 无 `pandaStates`：

1. `panda_status` — 含 `usb_f4`、`firmware_path`、`dos_note`
2. `panda_recovery_hint` — 下一步建议
3. `list_f4_pandas` — 内置 vs 外接黑熊
4. offroad 刷机：`recover_dos_panda(confirm=true)` — 技能 **`c3-dos-panda`**
5. `rebuild_pandad_tici(confirm=true)` — `updated` 删二进制后
6. 文档：`ai/docs/PANDA_FLASH.md`

**F4 固件**：`panda/board/obj/panda.bin.signed`（非 `panda_tici`）。
