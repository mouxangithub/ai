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

**手动 git 克隆：**

```bash
cd /data/openpilot   # 或你的 OPENPILOT_ROOT
git clone -b main git@github.com:mouxangithub/ai.git ai
# HTTPS: git clone -b main https://github.com/mouxangithub/ai.git ai
```

## 更新

```bash
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/update.sh | bash
# 或
cd /data/openpilot/ai && bash install/update.sh
```

Web：**设置 → 开发 → op助手 版本** →「检查更新」/「立即更新」（静止或 PC）。

## 与 fork 集成

op助手依赖 openpilot 主仓的部分能力（`Params`、`params_pyx.so`、可选 `launch_chffrplus.sh` 钩子）。

1. **启动 aid**  
   - 车机：在 `launch_chffrplus.sh` 中 manager 之前执行 `python3 -m ai.aid`（Dragonpilot 等已集成的 fork 可跳过）。  
   - PC：`cd $OPENPILOT_ROOT && python3 -m ai.aid`

2. **Params 键**  
   - fork 需在 `common/params_keys.h` 与 `ai/common/params.py` 中登记 `ai_*` 键（见主仓 README）。

3. **社区 fork**  
   - sunnypilot / carrotpilot / iqpilot / dragonpilot 等：安装路径相同，仅 `OPENPILOT_ROOT` 不同。

## 版本

- 当前版本见仓库根目录 `VERSION`
- API：`GET /api/ai/package/version`
- 更新：`POST /api/ai/package/update`（需 offroad 或 PC）

## 卸载

```bash
rm -rf /data/openpilot/ai   # 先停止 ai.aid
```

保留 Params 中的 `ai_*` 配置；重新安装后可继续使用。
