"""Git commit/push + GitHub Pull Request tools."""

from __future__ import annotations

import re
import time
from typing import Any, TYPE_CHECKING

from ai.tools.adaptation_pr_tools import generate_adaptation_pr_draft
from ai.common.repo_targets import (
  LABEL_AUTO_REVIEW,
  LABEL_SAFE_MERGE,
  merge_allowed,
  repo_target_meta,
  resolve_repo_url,
  default_base_branch,
  suggest_pr_labels,
)
from ai.tools.github_api_client import (
  DEFAULT_REPO,
  add_pull_request_labels,
  create_pull_request,
  create_pull_request_review,
  get_combined_status,
  get_pat,
  get_pull_request,
  get_pull_request_labels,
  list_pull_requests,
  merge_pull_request,
  parse_repo_url,
)
from ai.tools.git_repo_context import git_repo_context
from ai.tools.git_tools import (
  git_commit,
  git_create_branch,
  git_diff,
  git_push,
  git_status,
)

if TYPE_CHECKING:
  from openpilot.common.params import Params

PROTECTED_BASES = frozenset({"master", "main", "master-c3", "release", "production"})
AUTO_MERGE_LABEL = LABEL_SAFE_MERGE
AI_BRANCH_PREFIX = "ai/"


def _params_or_none(params: "Params | None"):
  if params is not None:
    return params
  try:
    from openpilot.common.params import Params
    return Params()
  except Exception:
    return None


def _require_pat(params: "Params | None" = None) -> tuple[str | None, dict[str, Any] | None]:
  del params
  token = get_pat()
  if not token:
    return None, {
      "ok": False,
      "error": "github_pat_not_configured",
      "hint": "set_github_actions_pat (stored as ai_github_actions_pat in config.json)",
      "doc": "ai/docs/GIT_PR.md",
    }
  return token, None


def _slug(text: str, max_len: int = 32) -> str:
  s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "change").lower()).strip("-")
  return (s[:max_len] or "change").strip("-")


def _ensure_branch(
  *,
  base_branch: str,
  branch: str = "",
  title: str = "",
) -> tuple[str | None, dict[str, Any] | None]:
  status = git_status()
  current = status.get("branch") or ""
  dirty = int(status.get("dirty_count", 0) or 0)

  if branch:
    b = branch.strip()
    if current == b:
      return b, None
    from ai.tools.git_tools import _git
    exists = _git(["rev-parse", "--verify", b], timeout=10)
    if exists.get("ok"):
      if dirty:
        return None, {
          "ok": False,
          "error": "cannot switch to existing branch with uncommitted changes",
          "hint": "commit/stash first, or omit branch to auto-create ai/* branch",
          "branch": b,
          "current": current,
        }
      from ai.tools.git_tools import git_checkout
      co = git_checkout(branch=b)
      if not co.get("ok"):
        return None, co
      return b, {"checked_out": b}
    created = git_create_branch(branch=b)
    if not created.get("ok"):
      return None, created
    return b, {"created_branch": b}

  if current and current not in PROTECTED_BASES:
    return current, {"used_existing_branch": current}

  if dirty == 0:
    return None, {"ok": False, "error": "no changes to publish"}

  new_branch = f"{AI_BRANCH_PREFIX}{_slug(title)}-{int(time.time()) % 100000}"
  created = git_create_branch(branch=new_branch)
  if not created.get("ok"):
    return None, created
  return new_branch, {"created_branch": new_branch}


def git_publish_pull_request(
  *,
  title: str = "",
  body: str = "",
  base_branch: str = "",
  branch: str = "",
  commit_message: str = "",
  paths: list[str] | None = None,
  draft: bool = False,
  remote: str = "origin",
  repo_url: str = "",
  repo_target: str = "openpilot",
  severity: str = "",
  request_auto_fix: bool = False,
  auto_label: bool = True,
  confirm: bool = False,
  params: "Params | None" = None,
) -> dict[str, Any]:
  """Commit local changes, push branch, open GitHub PR (one-shot)."""
  meta = repo_target_meta(repo_target)
  target = meta["repo_target"]
  url = (repo_url or meta["repo_url"] or DEFAULT_REPO).strip()
  base = (base_branch or meta["default_base"]).strip()
  owner, repo = parse_repo_url(url)

  with git_repo_context(target):
    status = git_status()
    diff_stat = git_diff(stat=True)

    if not title:
      title = f"chore(ai): update from {status.get('branch') or target}"

    head_branch, branch_err = _ensure_branch(base_branch=base, branch=branch, title=title)
    if branch_err and not head_branch:
      return branch_err if branch_err.get("ok") is False else {"ok": False, "error": "branch_setup_failed", **branch_err}
    if not head_branch:
      return {"ok": False, "error": "could not determine head branch"}

    labels = suggest_pr_labels(
      repo_target=target,
      severity=severity,
      request_auto_fix=request_auto_fix,
    ) if auto_label else []

    preview = {
      "action": "git_publish_pull_request",
      "repo_target": target,
      "title": title,
      "head": head_branch,
      "base": base,
      "remote": remote,
      "repo": f"{owner}/{repo}",
      "repo_root": meta.get("repo_root"),
      "draft": draft,
      "labels": labels,
      "dirty_count": status.get("dirty_count"),
      "diff_stat": (diff_stat.get("stdout") or "")[:2000],
      "steps": ["commit", "push -u", "create PR", "add labels"],
      "doc": "ai/docs/PR_AUTOMATION.md",
    }
    if branch_err:
      preview["branch_setup"] = branch_err

    if not confirm:
      return {"ok": True, "needs_confirmation": True, "preview": preview}

    if status.get("dirty_count", 0) == 0 and not branch_err:
      return {"ok": False, "error": "nothing to commit", "preview": preview}

    msg = (commit_message or title).strip()[:500]
    path_list = [str(x) for x in paths] if isinstance(paths, list) else None
    committed = git_commit(message=msg, add_all=not path_list, paths=path_list)
    if not committed.get("ok"):
      return {**committed, "preview": preview}

    pushed = git_push(remote=remote, branch=head_branch, set_upstream=True)
    if not pushed.get("ok"):
      return {**pushed, "preview": preview, "hint": "commit succeeded; fix git credentials and retry git_push"}

  token, err = _require_pat(params)
  if err:
    return {
      **err,
      "partial": True,
      "committed": True,
      "pushed": True,
      "branch": head_branch,
      "hint": "Code pushed; configure PAT then create PR manually",
    }

  pr_body = body.strip()
  if not pr_body:
    draft_md = generate_adaptation_pr_draft(project_name=title, summary=msg)
    pr_body = draft_md.get("markdown", "")

  pr = create_pull_request(
    token,
    owner,
    repo,
    title=title[:250],
    head=head_branch,
    base=base,
    body=pr_body[:65000],
    draft=draft,
  )
  if not pr.get("ok"):
    return {**pr, "partial": True, "branch": head_branch, "pushed": True}

  pull_number = (pr.get("pull") or {}).get("number")
  label_res = None
  if pull_number and labels:
    label_res = add_pull_request_labels(token, owner, repo, int(pull_number), labels)

  return {
    "ok": True,
    "pull_request_url": pr.get("html_url"),
    "pull": pr.get("pull"),
    "pull_number": pull_number,
    "labels": labels,
    "labels_applied": label_res,
    "branch": head_branch,
    "base": base,
    "repo_target": target,
    "commit": committed.get("staged_stat"),
    "next": "OpenCode reviews PR (opencode-pr.yml); safe-merge if ai-safe-merge label",
  }


def list_github_pull_requests(
  *,
  repo_url: str = DEFAULT_REPO,
  state: str = "open",
  base: str = "",
  head: str = "",
  per_page: int = 10,
  params: "Params | None" = None,
) -> dict[str, Any]:
  token, err = _require_pat(params)
  if err:
    return err
  owner, repo = parse_repo_url(repo_url)
  head_q = head
  if head and ":" not in head and "/" not in head:
    head_q = f"{owner}:{head}"
  data = list_pull_requests(token, owner, repo, state=state, head=head_q or None, base=base or None, per_page=per_page)
  if data.get("ok"):
    data["repo"] = f"{owner}/{repo}"
  return data


def get_github_pull_request(
  *,
  pull_number: int,
  repo_url: str = DEFAULT_REPO,
  params: "Params | None" = None,
) -> dict[str, Any]:
  if not pull_number:
    return {"ok": False, "error": "pull_number required"}
  token, err = _require_pat(params)
  if err:
    return err
  owner, repo = parse_repo_url(repo_url)
  data = get_pull_request(token, owner, repo, int(pull_number))
  if data.get("ok"):
    data["repo"] = f"{owner}/{repo}"
  return data


def review_github_pull_request(
  *,
  pull_number: int,
  body: str,
  event: str = "COMMENT",
  repo_url: str = DEFAULT_REPO,
  confirm: bool = False,
  params: "Params | None" = None,
) -> dict[str, Any]:
  if not pull_number:
    return {"ok": False, "error": "pull_number required"}
  if not (body or "").strip():
    return {"ok": False, "error": "review body required"}
  preview = {
    "action": "review_pull_request",
    "pull_number": int(pull_number),
    "event": event,
    "body_preview": body[:500],
  }
  if not confirm:
    return {"ok": True, "needs_confirmation": True, "preview": preview}
  token, err = _require_pat(params)
  if err:
    return err
  owner, repo = parse_repo_url(repo_url)
  return create_pull_request_review(token, owner, repo, int(pull_number), body=body, event=event)


def merge_github_pull_request(
  *,
  pull_number: int,
  merge_method: str = "squash",
  repo_url: str = "",
  repo_target: str = "openpilot",
  require_label: str = AUTO_MERGE_LABEL,
  confirm: bool = False,
  params: "Params | None" = None,
) -> dict[str, Any]:
  if not pull_number:
    return {"ok": False, "error": "pull_number required"}
  meta = repo_target_meta(repo_target)
  url = (repo_url or meta["repo_url"] or DEFAULT_REPO).strip()
  preview = {
    "action": "merge_pull_request",
    "pull_number": int(pull_number),
    "merge_method": merge_method,
    "repo": url,
    "repo_target": meta["repo_target"],
    "safety": f"requires label {require_label} and path/branch gates",
  }
  if not confirm:
    return {"ok": True, "needs_confirmation": True, "preview": preview}

  token, err = _require_pat(params)
  if err:
    return err
  owner, repo = parse_repo_url(url)
  pr_data = get_pull_request(token, owner, repo, int(pull_number))
  if not pr_data.get("ok"):
    return pr_data
  pull = pr_data.get("pull") or {}
  base = pull.get("base") or ""
  head = pull.get("head") or ""
  files = pr_data.get("files") or []

  labels_res = get_pull_request_labels(token, owner, repo, int(pull_number))
  labels = labels_res.get("labels") or [] if labels_res.get("ok") else []

  allowed, reason = merge_allowed(
    repo_target=meta["repo_target"],
    head=str(head),
    base=str(base),
    files=files,
    labels=labels,
  )
  if require_label and not allowed:
    return {"ok": False, "error": "merge_not_allowed", "reason": reason, "pull": pull, "labels": labels}

  if pull.get("mergeable") is False:
    return {"ok": False, "error": "PR not mergeable (conflicts)", "pull": pull}
  if pull.get("mergeable_state") in ("blocked", "dirty"):
    return {"ok": False, "error": "PR blocked; checks or reviews required", "pull": pull}

  return merge_pull_request(token, owner, repo, int(pull_number), merge_method=merge_method)


def auto_review_pull_request(
  *,
  pull_number: int,
  repo_url: str = DEFAULT_REPO,
  approve: bool = False,
  merge_if_clean: bool = False,
  confirm: bool = False,
  params: "Params | None" = None,
) -> dict[str, Any]:
  """Fetch PR diff summary, post review comment; optionally approve + merge."""
  if not pull_number:
    return {"ok": False, "error": "pull_number required"}
  pr_data = get_github_pull_request(pull_number=pull_number, repo_url=repo_url, params=params)
  if not pr_data.get("ok"):
    return pr_data
  pull = pr_data.get("pull") or {}
  files = pr_data.get("files") or []
  summary_lines = [
    f"## op助手自动审阅 PR #{pull_number}",
    "",
    f"**标题**: {pull.get('title')}",
    f"**分支**: `{pull.get('head')}` → `{pull.get('base')}`",
    f"**变更文件**: {len(files)}",
    "",
    "### 文件列表",
  ]
  for f in files[:30]:
    summary_lines.append(
      f"- `{f.get('filename')}` (+{f.get('additions', 0)}/-{f.get('deletions', 0)}) [{f.get('status')}]"
    )
  summary_lines.extend([
    "",
    "### 说明",
    "此为 op助手自动摘要；请在 PC 上查看完整 diff 后决定是否合并。",
    "仅当 PR 带 `ai-safe-merge` 标签且 CI 通过时建议自动合并。",
  ])
  review_body = "\n".join(summary_lines)
  preview = {
    "action": "auto_review_pull_request",
    "pull_number": pull_number,
    "approve": approve,
    "merge_if_clean": merge_if_clean,
    "review_preview": review_body[:800],
  }
  if not confirm:
    return {"ok": True, "needs_confirmation": True, "preview": preview}

  event = "APPROVE" if approve else "COMMENT"
  reviewed = review_github_pull_request(
    pull_number=pull_number,
    body=review_body,
    event=event,
    repo_url=repo_url,
    confirm=True,
    params=params,
  )
  if not reviewed.get("ok"):
    return reviewed

  out: dict[str, Any] = {"ok": True, "review": reviewed, "pull": pull}
  if merge_if_clean:
    merged = merge_github_pull_request(
      pull_number=pull_number,
      repo_url=repo_url,
      confirm=True,
      params=params,
    )
    out["merge"] = merged
    out["ok"] = merged.get("ok", False)
  return out
