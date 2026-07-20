# GitHub Runner 与 C3 prebuilt CI

适用于 **comma three** 自建 Actions Runner：编译 `master-c3` → 发布 `master-c3-prebuilt`，以及 GUI / Param 启停 Runner。

> 事实来源：`ai/docs/GITHUB_RUNNER.md`、`release/ci/README.md`

## 何时触发

- GitHub Actions **build** 作业一直 **Pending**（等待 `tici` runner）
- 用户问「怎么开 Runner」「prebuilt 怎么编译」「GUI Runner 开关没用」
- 车机需要 `prebuilt` 快速启动
- `EnableGithubRunner` / 开发者高级控制相关

## 核心概念（勿混淆）

| 对象 | 说明 |
|------|------|
| `EnableGithubRunner` | UI/manager **允许**启停 Runner，不是安装开关 |
| `github_runner_start` | manager 子进程，跑 `github_runner.sh start` |
| `{base}/runner/.service` | **真实** systemd 单元名（fork 仓库名会体现在此） |
| `/data/openpilot` | 车机 **live** 代码树；CI 编译用 `{base}/builds`，勿 wipe |
| `tici` 标签 | workflow `runs-on` 要求；注册 Runner 时须带上 |

## 推荐工具顺序

### A. 已安装 — 排查不工作

1. `github_runner_status` — Param 门控、服务名、systemd、目录
2. `github_runner_recovery_hint` — 下一步建议
3. `get_device_settings` — 确认 `ShowAdvancedControls`、`EnableGithubRunner`
4. `list_managed_processes` — 是否有 `github_runner_start`
5. `grep_log` — `github_runner|actions.runner|EnableGithubRunner`
6. 电压/网络：`GithubRunnerSufficientVoltage`、`NetworkMetered`（见 status 输出）
7. 仍失败 → 对照 `ai/docs/GITHUB_RUNNER.md` 重装或 `--restore`

### B. 未安装 — 首次部署

1. 指引用户获取 GitHub **registration token**（Actions → Runners → New）
2. `install_github_runner` — 先 `confirm=false` 预览命令
3. `confirm=true` + token 执行（**离路**、需 root）
4. `github_runner_status` — 确认 `installed`、`systemd.running`、标签 `tici`
5. PC：检查 `DEPLOY_STRATEGY`、workflow permissions（见文档）

### C. prebuilt 发布与车机更新

1. PC：推 `master-c3` 或手动 Run workflow `build.yaml`
2. 等 `build`（C3）+ `publish`（云端）完成
3. 车机：`git fetch && git reset --hard origin/master-c3-prebuilt`
4. `test -f /data/openpilot/prebuilt` 或 `get_build_info`

## GUI 启停条件（全部满足才 start）

- 离路
- `EnableGithubRunner=true`
- `NetworkMetered≠true`
- `GithubRunnerSufficientVoltage=true`（车载 >9V；桌面 USB 可能不满足）

**非 release 分支**才显示 Runner 开关（`developer.py`）。

## 常见坑

1. **服务名不一致** — fork 注册为 `actions.runner.<org>-<repo>.<host>`；旧脚本写死 `sunnypilot` → 已改为读 `.service`
2. **`--start-at-boot`** — 开机自启与 GUI 并行；只要 GUI 控制则 `systemctl disable`
3. **桌面调试** — 电压门控导致 Runner 不启，属预期
4. **Pending ≠ 车机问题** — 也可能是 GitHub 无 runner、标签不对、runner 离线

## SSH 速查

```bash
cat /data/github/runner/.service
systemctl status "$(cat /data/github/runner/.service)"
cat /data/openpilot/release/ci/install_github_runner.sh | head
```

## 相关技能

- `pc-dev-environment` — workflow 触发、git、devsync
- `network-diagnostics` — 同步代码、SSH
- `diagnostics` — 进程/日志
- `sp-display-device` — `EnableGithubRunner` 等开发者 Param
