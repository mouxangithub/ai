# op助手 独立安装指南

> 仓库：<https://github.com/mouxangithub/ai>  
> 安装路径：`<openpilot>/ai`（车机默认 `/data/openpilot/ai`）

## 一键安装（SSH / HTTPS 自动选择）

**Comma 设备（C3/C3X/C4，已 SSH）：**

```bash
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/install.sh | bash
```

**PC 开发机（自定义 openpilot 路径）：**

```bash
export OPENPILOT_ROOT=/path/to/your/openpilot
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/install.sh | bash
```

安装脚本会自动完成：

1. `git clone` / `git pull` 到 `$OPENPILOT_ROOT/ai`
2. **补丁 `common/params_keys.h`** — 从 `ai/common/params.py` 同步缺失的 `ai_*` 键（自动备份 `.bak.*`）
3. **补丁 `launch_chffrplus.sh`** — 注入 `start_op_assistant` 与 45s 看门狗（若尚未存在）
4. **编译 `params_pyx.so`** — 优先 `scons common/params_pyx.so`，否则 `system/manager/build.py`

> 部分预编译 fork 若无 `SConstruct`/`common/SConscript`，脚本会尽量使用已有 `.so`；若 `params_keys.h` 有新增键，需在可编译环境重建 `.so`。

**手动 git 克隆：**

```bash
cd /data/openpilot   # 或你的 OPENPILOT_ROOT
git clone -b main git@github.com:mouxangithub/ai.git ai
PYTHONPATH=$PWD python3 ai/install/integrate_openpilot.py --root "$PWD"
```

## 更新

```bash
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/update.sh | bash
# 或
cd /data/openpilot/ai && bash install/update.sh
```

更新后会自动再次运行 `integrate_openpilot.py`（params + launch + 编译）。

Web：**设置 → 开发 → op助手 版本** →「检查更新」/「立即更新」（静止或 PC）。

也可调用 API：`POST /api/ai/integrate`（offroad 或 PC）手动重新集成。

## 首次使用（P2）

浏览器打开 `:5090` 后，若未完成首次配置，会弹出**配置向导**（服务商 / API Key / 模型）。

也可在 **设置 → 模型** 中手动配置。完成后写入 Param `ai_first_run_done=1`。

## Fork 识别与草稿生成（P4 / P5）

- **开发面板 → Fork 识别**：根据 git remote、目录特征识别 sunnypilot / carrotpilot / dragonpilot / iqpilot 等
- **生成草稿**：使用已配置模型分析本 fork，在 `ai/data/fork_drafts/<fork_id>/` 生成技能与文档草稿（**需人工审核**后再合并）

配置文件：`ai/fork-profiles/*.json`

## 与 fork 集成（手动说明）

op助手依赖 openpilot 主仓：

| 依赖 | 说明 |
|------|------|
| `Params` / `params_pyx.so` | 一键安装会自动补丁并编译 |
| `launch_chffrplus.sh` | 一键安装会自动注入 `ai.aid` 启动钩子 |
| 社区 fork | 安装路径相同，仅 `OPENPILOT_ROOT` 不同 |

## 版本

- 当前版本见 `VERSION`（0.2.0+ 含自动集成）
- API：`GET /api/ai/package/version`
- 更新：`POST /api/ai/package/update`（含 integrate）

## 卸载

```bash
rm -rf /data/openpilot/ai   # 先停止 ai.aid
```

保留 Params 中的 `ai_*` 配置；`launch_chffrplus.sh` / `params_keys.h` 的备份文件可手动恢复。
