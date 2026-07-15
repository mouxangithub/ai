# 安装与集成

> 仓库：https://github.com/mouxangithub/ai  
> 路径：`<openpilot>/ai`

## 一键安装

**Comma 设备（默认 `/data/openpilot`）：**

```bash
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/install.sh | bash
```

**PC（指定 openpilot 根目录）：**

```bash
export OPENPILOT_ROOT=/path/to/your/openpilot
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/install.sh | bash
```

## 安装脚本做什么

| 步骤 | 说明 |
|------|------|
| 1. Git | 克隆或更新 `ai/` 到 `$OPENPILOT_ROOT/ai` |
| 2. Params | 将 `ai/common/params.py` 中缺失的 `ai_*` 键写入 `common/params_keys.h`（自动 `.bak` 备份） |
| 3. 启动 | 在 `launch_chffrplus.sh` 注入 `start_op_assistant`（若尚未存在） |
| 4. 编译 | 尝试 `scons common/params_pyx.so` 或 `system/manager/build.py` |

预编译发行版若无 SConstruct：尽量复用已有 `params_pyx.so`；若新增了 Param 键，需在可编译环境重建。

**手动集成：**

```bash
cd "$OPENPILOT_ROOT"
git clone -b main https://github.com/mouxangithub/ai.git ai
PYTHONPATH=$PWD python3 ai/install/integrate_openpilot.py --root "$PWD"
```

## 更新

```bash
curl -fsSL https://raw.githubusercontent.com/mouxangithub/ai/main/install/update.sh | bash
```

或通过 Web：**设置 → 开发 → op助手 版本 → 立即更新**（会 `git pull` 并重新 integrate）。

API：`POST /api/ai/integrate` 可手动触发集成。

## 首次使用

打开 `http://<IP>:5090`，未完成配置时会弹出**首次向导**（服务商 / API Key / 模型）。也可在 **设置 → 模型** 中配置。

## Fork 分析（不限定社区列表）

op助手 **不内置** sunnypilot / dragonpilot 等固定配置表。

1. **扫描**：`GET /api/ai/fork/detect` — 读取 git remote、README、特征目录、`params_keys.h` 前缀、各路径下的 `settings/ITEMS` 等。  
2. **AI 分析**：`POST /api/ai/fork/analyze` — 用已配置模型阅读项目摘录，输出 JSON 分析报告（缓存于 `ai/data/fork_analysis/latest.json`，commit 变化后需重跑）。  
3. **草稿**：`POST /api/ai/fork/sync`（`confirm: true`）— 基于分析生成技能/文档草稿到 `ai/data/fork_drafts/`（**必须人工审核**）。

开发面板：**设置 → 开发 → Fork 分析**。

## 依赖关系

| 组件 | 作用 |
|------|------|
| `params_pyx.so` | op助手读写 `Params` |
| `launch_chffrplus.sh` | 车机开机拉起 `python3 -m ai.aid` |
| 网络 | 云端模型、embedding、部分工具 |

## 卸载

```bash
pkill -f 'python.* -m ai\.aid'   # 可选
rm -rf /data/openpilot/ai
```

Params 中 `ai_*` 配置会保留。`params_keys.h` / `launch_chffrplus.sh` 可从 `.bak.*` 恢复。
