# Git 提交与 Pull Request

本地改代码后，一键提交、推送并创建 GitHub PR；PC 上拉取审阅或让 AI 自动审阅/合并。

> 详见 `ai/docs/GIT_PR.md`

## 何时触发

- 用户说「发个 PR」「推到 GitHub」「我在车机上改好了想让你提交」
- 适配/调参改完代码，要在 PC 上 review
- 用户问「能不能自动审 PR / 自动合并」

## 前置

1. **离路**（写操作）
2. **Git push 凭据**已配置
3. **GitHub PAT**（`ai_github_actions_pat`）— `github_actions_auth_status` 检查

## 发布 PR（推荐）

```
git_status → git_diff
git_publish_pull_request(title=..., confirm=false)  # 预览
用户确认 → git_publish_pull_request(..., confirm=true)
```

- 在 `master-c3` 等有未提交改动时，自动 `checkout -b ai/...`
- `repo_target=assistant` 时针对独立 `mouxangithub/ai` 仓（见 `ai/docs/PR_AUTOMATION.md`）
- 返回 `pull_request_url`，提示用户在 PC 打开

勿直接 `git push` 到保护分支。

## 审阅与合并

- **审阅**：GitHub OpenCode（`opencode-pr.yml`），模型由仓库 `OPENCODE_MODEL` + `OPENCODE_API_KEY` 配置
- **自动合并**：仅 `ai-safe-merge` + `ai-pr-automation.yml` 规则门控
- 设备侧：`auto_review_pull_request` 仅摘要，非 OpenCode

**安全**：合并到 `master-c3` 时，仅允许 head 为 `ai/*` 分支；默认不自动 merge。

## 工作流

- `publish_pr` — 发布一条龙
- `pr_review_merge` — 审阅 + 可选合并

## 与 Runner/CI

PR 创建后可在 PC 用 `wait_github_workflow` 等 CI；与 `github-runner` 技能配合。

## 禁止

- 行驶中 commit/push/merge
- 未经确认合并到主分支
- 输出 PAT 或私钥
