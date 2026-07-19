# C3 DOS / 黑熊 Panda 刷机与恢复

适用于 **comma three（C3 / `tici`）** 内置 **DOS（F4）** 与外接 **黑熊（F4, aux）**。红熊（H7）不在本技能范围。

> 事实来源：`ai/docs/PANDA_FLASH.md`、`ai/docs/COMMA_DEVICES.md`。CLI 脚本 `tools/recover_dos_panda.py` **可选**（部分 fork 无此文件）；op 助手 **内联刷机**，不依赖该脚本。

## 何时触发

- 侧栏 **NO PANDA** / **否**
- `panda_status` → `pandaStates` 为空但 USB 能看到 F4
- 日志：`xhci-hcd` 误枚举、`pandad` 崩溃、固件签名不匹配
- 更新 `panda/` 子模块后需手动刷内置 DOS

## 固件与进程（勿混淆）

| 对象 | 固件路径 | 刷机方式 |
|------|----------|----------|
| 内置 DOS（F4） | `panda/board/obj/panda.bin.signed` | **手动** `recover_dos_panda` |
| 外接黑熊（F4, aux） | 同上 | **手动** `recover_dos_panda(external=true)` |
| 外接红熊（H7） | `panda_tici/board/obj/panda*.bin.signed` | `pandad_tici` 自动刷 |

- **进程栈**：C3 仍用 `pandad_tici` + `panda_tici` Python（通信层），但 **F4 固件永远来自 `panda/`**。
- **禁止**：对 F4 使用 `panda_tici` 固件、或 `Panda.flash()`（`SUPPORTED_DEVICES` 仅 H7）。
- **单内置 DOS**：`TICI_DOS=1` 时走 DOS 快速路径，**不自动刷机**。

## 推荐工具顺序（offroad）

1. `panda_status` — 看 `pandaStates`、USB F4、`firmware_exists`
2. `panda_recovery_hint` — 生成下一步建议
3. `grep_log` — `pandad|panda|xhci|DOS internal`
4. `tsk_restart_pandad(confirm=true)` — 先尝试重启 pandad（不刷固件）
5. 仍失败 → `list_f4_pandas` 确认目标
6. 缺固件 → `build_panda_firmware` 或 `scons` in `panda/board`
7. `recover_dos_panda(confirm=true, internal=true)` — 内置 DOS
8. `recover_dos_panda(confirm=true, external=true)` — 外接 aux 黑熊
9. `recover_dos_panda(confirm=true, serial="...")` — 指定序列号
10. `rebuild_pandad_tici(confirm=true)` — `updated` reset 后 pandad 二进制被删时
11. `reboot_device` — 刷机/重编后重启
12. 再验 `panda_status`（应有 `pandaType: dos` 或非空 `pandaStates`）

## CLI（车机 SSH）

```bash
cd /data/openpilot
PATH=/usr/local/venv/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot \
  python3 tools/recover_dos_panda.py --internal   # 或 --external / --serial
bash tools/rebuild_pandad_tici.sh
sudo reboot
```

## 与 TSK / SecOC 的关系

- TSK 采集 CAN / DataFlash 会 `stop_manager_and_pandad()`；完成后用 `tsk_restart_pandad` 恢复。
- SecOC 排障见 `secoc-toyota`；**不要**把 F4 刷机与 SecOC 密钥安装混为一步。

## 相关技能

- `engage-troubleshooting` — 无法开启 OP 总入口
- `diagnostics` — 日志与进程健康
- `network-diagnostics` — 代码同步 / devsync
- `sp-device-lite` — C3 Lite 硬件（与 Panda 独立）
