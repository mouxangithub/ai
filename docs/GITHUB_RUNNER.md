# GitHub Actions 自建 Runner（C3 prebuilt）

适用于 **comma three (C3 / `tici`)** 上运行 GitHub Actions，为 fork 编译并发布 **`*-prebuilt`** 分支。op助手技能：**`github-runner`**。

> 用户向手册（仓库根目录）：`release/ci/README.md`  
> 控制脚本：`release/ci/install_github_runner.sh`、`system/manager/github_runner.sh`

## 架构

```
push master-c3 ──► prepare_strategy ──► build (C3 Runner, label: tici)
                                              │
                                              ▼
                                         prebuilt.tar.gz
                                              │
publish ◄─────────────────────────────────────┘
    │
    ▼
master-c3-prebuilt 分支（车机 checkout 后含 prebuilt 文件，快速启动）
```

| 组件 | 路径 / 名称 |
|------|-------------|
| Runner 用户 | `github-runner` |
| 数据根目录 | `/data/github`（或 `/data/media/0/github`） |
| Runner 目录 | `{base}/runner` |
| 编译工作区 | `{base}/builds`（**不要**用 `/data/openpilot` 作 BUILD_DIR） |
| CI 绑定 openpilot | `{base}/openpilot` → mount bind 到 `/data/openpilot`（仅 Runner 作业内） |
| systemd 服务名 | `{runner}/.service`（如 `actions.runner.mouxangithub-openpilot.comma-xxxxx`） |
| Workflow | `.github/workflows/build.yaml` |
| 默认仓库 | `https://github.com/mouxangithub/openpilot` |

## GUI 启停（车机）

**设置 → 开发者 → 显示高级控制项 → GitHub Runner Service**

| Param | 作用 |
|-------|------|
| `ShowAdvancedControls` | 显示高级项（含 Runner 开关） |
| `EnableGithubRunner` | 允许 manager 启停 Runner |
| `NetworkMetered` | `true` 时 **禁止** 启 Runner |
| `GithubRunnerSufficientVoltage` | 电压 > 9V 时为 `true`（`hardwared` 写入；桌面 USB 常 < 9V） |

manager 条件（`system/manager/process_config.py` → `use_github_runner`）：

- **离路**（未 onroad）
- `EnableGithubRunner=true`
- `NetworkMetered=false`
- `GithubRunnerSufficientVoltage=true`（或未知时不挡）

满足时启动 `system/manager/github_runner.sh start`，循环 `systemctl start <service>`；进程退出时 `systemctl stop`。

**服务名解析**（`github_runner.sh`）：优先读 `{runner}/.service`，否则回退 `actions.runner.sunnypilot.$(hostname)`。fork 注册到自有仓库时 **必须** 读 `.service`，否则 GUI 无法控制。

## 安装（一次性）

1. GitHub → **Settings → Actions → Runners → New self-hosted runner**
2. 复制 **Registration token**（约 1 小时有效）
3. C3 SSH：

```bash
cd /data/openpilot
git pull
sudo ./release/ci/install_github_runner.sh \
  --token <TOKEN> \
  --repo https://github.com/mouxangithub/openpilot
```

4. GitHub Runners 页应显示 **Idle**，标签含 **`tici`**

可选：

- `--start-at-boot` — systemd 开机自启（与 GUI 并行；若只要 GUI 控制则不要加，或事后 `systemctl disable`）
- `--restore` — 已有 `.credentials` + `.service` 时恢复

一键脚本（含 `ai` 子模块）：`release/ci/deploy_c3_runner.sh <TOKEN>`

## 卸载

```bash
sudo ./release/ci/uninstall_github_runner.sh
```

## GitHub 仓库配置

| 项 | 说明 |
|----|------|
| `DEPLOY_STRATEGY` | Actions Variable，见 `.github/DEPLOY_STRATEGY.example.json` |
| Workflow permissions | Read and write（推送 `*-prebuilt`） |
| Environments | 按策略创建 `c3-dev` / `feature-branch` 等 |

## 车机使用 prebuilt 分支

```bash
cd /data/openpilot
git fetch origin master-c3-prebuilt
git reset --hard origin/master-c3-prebuilt
git submodule update --init --recursive
test -f prebuilt && echo OK
sudo reboot
```

## 故障排查

| 现象 | 处理 |
|------|------|
| Actions `build` 一直 Pending | Runner 未注册/离线；`github_runner_status` |
| GUI 开关无效 | 对比 `cat /data/github/runner/.service` 与 `github_runner.sh` 使用的服务名 |
| 桌面供电 Runner 不启 | 电压 < 9V → `GithubRunnerSufficientVoltage=false` |
| checkout /tmp 满 | 安装脚本设置 `TMPDIR=/data/tmp` |
| 车机 `/data/openpilot` 被清空 | workflow BUILD_DIR 必须是 `/data/github/...`，非 live 目录 |
| 编译失败 | `/data/github/logs`、Actions 日志、`grep_log actions.runner` |

## op助手工具

| 工具 | 用途 |
|------|------|
| `github_runner_status` | 路径、Param 门控、systemd 状态 |
| `github_runner_recovery_hint` | 推荐排查顺序 |
| `install_github_runner` | 预览/执行安装脚本（`confirm=true` + token） |
| `get_device_settings` / `set_device_settings` | 读写 `EnableGithubRunner` |

## 相关技能

- `github-runner` — Runner 与 prebuilt CI 主技能
- `pc-dev-environment` — PC 侧触发 workflow、devsync
- `network-diagnostics` — 网络与代码同步
- `diagnostics` — 进程与日志
- `sp-display-device` — 开发者 Param 总览
