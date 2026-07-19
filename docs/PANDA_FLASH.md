# Panda 刷机与恢复（sunnypilot / C3 DOS）

> **单一事实来源**（与 `ai/docs/COMMA_DEVICES.md` 互补）。op 助手工具：`list_f4_pandas`、`recover_dos_panda`、`rebuild_pandad_tici`、`panda_recovery_hint`。

## 术语

| 名称 | MCU | hw_type | 说明 |
|------|-----|---------|------|
| DOS / 内置 Panda | F4 | `0x04` DOS | C3 板载，SPI/USB |
| 黑熊 Black Panda | F4 | `0x03` | 常见外接 aux |
| 红熊 Red Panda | H7 | H7 系列 | 外接，自动刷 `panda_tici` |

## sunnypilot C3 架构要点

1. **`pandad_tici`** 负责 C3 上 pandad 进程（含 DOS 快速路径）。
2. **内置 F4** 固件包：`panda/board/obj/panda.bin.signed`（子模块 `panda/`）。
3. **`panda_tici` 固件** 仅用于 **H7**（外接红熊）；刷到 F4 会损坏或无法启动。
4. `pandad_tici` 对非 H7 **跳过自动刷机**；代码更新后内置 DOS **需手动刷**。
5. `Panda.flash()` 在 `panda`/`panda_tici` Python 中 assert 仅 H7；F4 使用 **`Panda.flash_static` + bootstub**（`recover_dos_panda.py` 已实现）。

## 脚本与工具

| 入口 | 用途 |
|------|------|
| `tools/recover_dos_panda.py` | 可选 CLI（部分 fork 有）；**op 助手不依赖此文件** |
| op助手 `recover_dos_panda` | 内联实现于 `ai/tools/panda_flash_tools.py`，需 `confirm=true` |
| `tools/rebuild_pandad_tici.sh` | `updated` git reset 后重链 `pandad` 二进制 |
| op助手 `build_panda_firmware` | `scons` 编译 `panda/board` |

## 标准流程（车机）

```bash
# 1. 编译 F4 固件（若缺失）
cd /data/openpilot/panda/board && scons -j$(nproc)

# 2. 刷机（离路）
cd /data/openpilot
PYTHONPATH=/data/openpilot python3 tools/recover_dos_panda.py --internal

# 3. 重编 pandad（若被 updated 删掉）
bash tools/rebuild_pandad_tici.sh

# 4. 重启
sudo reboot
```

## 双 Panda（内置 + 外接）

| 组合 | 内置 | 外接 | 刷机 |
|------|------|------|------|
| 内置 + 红熊 | 跳过刷机 | `panda_tici` 自动 | 内置一般不需动 |
| 内置 + 黑熊 | 跳过刷机 | 跳过刷机 | **两只都可能需手动** `recover_dos_panda` |

外接黑熊：`--external` 或 `--serial <aux序列号>`（`list_f4_pandas` 查 `internal=false`）。

## 验证

- `panda_status`：`pandaStates` 非空，`pandaType` 含 `dos`
- 日志：`DOS internal panda: skipping Python panda setup`，无 `xhci-hcd` 误重连
- `pgrep -af pandad`：`selfdrive.pandad_tici.pandad`

## 常见错误

| 现象 | 原因 | 处理 |
|------|------|------|
| NO PANDA + xhci 重连 | USB 过滤 / pandad 退出 | 已修复的 `pandad_tici` 代码 + 重启 |
| 刷机后仍 NO PANDA | 未 `rebuild_pandad_tici` | 运行重编脚本并 reboot |
| 用了 panda_tici 固件 | 固件包错误 | DFU 恢复 + `recover_dos_panda` |
| `Panda.flash()` 断言失败 | F4 不在 SUPPORTED_DEVICES | 用 `recover_dos_panda` |

## 相关文档

- [`COMMA_DEVICES.md`](COMMA_DEVICES.md) — 产品映射与 pandad 模块选择
- [`TSK_AND_AID.md`](TSK_AND_AID.md) — TSK 停 manager/pandad 行为
- 技能 `c3-dos-panda` — op 助手排障顺序
