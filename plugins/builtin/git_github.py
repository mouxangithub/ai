"""Git commit/push + GitHub Pull Request plugin."""

from __future__ import annotations

from typing import Any, Callable


TOOL_META: dict[str, dict[str, Any]] = {
  "git_publish_pull_request": {"label": "发布 PR", "group": "write", "default_enabled": True, "driving": False},
  "list_github_pull_requests": {"label": "PR 列表", "group": "read", "default_enabled": True, "driving": True},
  "get_github_pull_request": {"label": "PR 详情", "group": "read", "default_enabled": True, "driving": True},
  "review_github_pull_request": {"label": "PR 审阅", "group": "write", "default_enabled": True, "driving": False},
  "merge_github_pull_request": {"label": "合并 PR", "group": "write", "default_enabled": True, "driving": False},
  "auto_review_pull_request": {"label": "PR 自动审阅", "group": "write", "default_enabled": True, "driving": False},
  "report_bug_and_publish_pr": {"label": "Bug 报告 PR", "group": "write", "default_enabled": True, "driving": False},
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
  {
    "type": "function",
    "function": {
      "name": "git_publish_pull_request",
      "description": (
        "Offroad: commit local changes, push branch, open GitHub Pull Request. "
        "Auto-creates ai/* branch from protected base. Requires git credentials + ai_github_actions_pat (repo scope). "
        "confirm=true to execute. See ai/docs/GIT_PR.md."
      ),
      "parameters": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "body": {"type": "string"},
          "base_branch": {"type": "string", "description": "Target branch, default master-c3"},
          "branch": {"type": "string", "description": "Head branch; auto ai/* if empty"},
          "commit_message": {"type": "string"},
          "paths": {"type": "array", "items": {"type": "string"}},
          "draft": {"type": "boolean"},
          "remote": {"type": "string"},
          "repo_url": {"type": "string"},
          "repo_target": {
            "type": "string",
            "enum": ["openpilot", "assistant", "ai"],
            "description": "openpilot 或独立 ai 仓库",
          },
          "severity": {"type": "string"},
          "request_auto_fix": {"type": "boolean"},
          "confirm": {"type": "boolean"},
        },
        "required": [],
      },
    },
  },
  {
    "type": "function",
    "function": {
      "name": "list_github_pull_requests",
      "description": "List GitHub pull requests. Requires ai_github_actions_pat in config.json.",
      "parameters": {
        "type": "object",
        "properties": {
          "repo_url": {"type": "string"},
          "state": {"type": "string", "enum": ["open", "closed", "all"]},
          "base": {"type": "string"},
          "head": {"type": "string"},
          "per_page": {"type": "integer"},
        },
        "required": [],
      },
    },
  },
  {
    "type": "function",
    "function": {
      "name": "get_github_pull_request",
      "description": "Get PR details and changed files list.",
      "parameters": {
        "type": "object",
        "properties": {"pull_number": {"type": "integer"}, "repo_url": {"type": "string"}},
        "required": ["pull_number"],
      },
    },
  },
  {
    "type": "function",
    "function": {
      "name": "review_github_pull_request",
      "description": "Post PR review (COMMENT/APPROVE/REQUEST_CHANGES). confirm=true required.",
      "parameters": {
        "type": "object",
        "properties": {
          "pull_number": {"type": "integer"},
          "body": {"type": "string"},
          "event": {"type": "string", "enum": ["COMMENT", "APPROVE", "REQUEST_CHANGES"]},
          "repo_url": {"type": "string"},
          "confirm": {"type": "boolean"},
        },
        "required": ["pull_number", "body"],
      },
    },
  },
  {
    "type": "function",
    "function": {
      "name": "merge_github_pull_request",
      "description": (
        "Merge PR (squash by default). Protected bases only accept ai/* head branches. confirm=true required."
      ),
      "parameters": {
        "type": "object",
        "properties": {
          "pull_number": {"type": "integer"},
          "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"]},
          "repo_url": {"type": "string"},
          "repo_target": {"type": "string", "enum": ["openpilot", "assistant", "ai"]},
          "confirm": {"type": "boolean"},
        },
        "required": ["pull_number"],
      },
    },
  },
  {
    "type": "function",
    "function": {
      "name": "auto_review_pull_request",
      "description": (
        "Summarize PR diff and post review comment; optional approve + merge_if_clean. confirm=true required."
      ),
      "parameters": {
        "type": "object",
        "properties": {
          "pull_number": {"type": "integer"},
          "repo_url": {"type": "string"},
          "approve": {"type": "boolean"},
          "merge_if_clean": {"type": "boolean"},
          "confirm": {"type": "boolean"},
        },
        "required": ["pull_number"],
      },
    },
  },
  {
    "type": "function",
    "function": {
      "name": "report_bug_and_publish_pr",
      "description": (
        "Structured bug report from op助手 → PR to mouxangithub/ai (default) or openpilot. "
        "Auto-labels ai-auto-review. confirm=true to execute."
      ),
      "parameters": {
        "type": "object",
        "properties": {
          "repo_target": {"type": "string", "enum": ["assistant", "ai", "openpilot"]},
          "title": {"type": "string"},
          "repro_steps": {"type": "string"},
          "expected": {"type": "string"},
          "actual": {"type": "string"},
          "severity": {"type": "string", "enum": ["ui", "docs", "typo", "web", "logic", "crash"]},
          "attach_audit": {"type": "boolean"},
          "request_auto_fix": {"type": "boolean"},
          "paths": {"type": "array", "items": {"type": "string"}},
          "confirm": {"type": "boolean"},
        },
        "required": [],
      },
    },
  },
]


def make_handlers(ctx: dict) -> dict[str, Callable[..., Any]]:
  p = ctx.get("params")
  stationary_check = ctx.get("stationary_check")
  needs_confirm = ctx.get("needs_confirm")

  def _git_write_gate(args, hint: str):
    if not args.get("confirm") and needs_confirm():
      return {"ok": True, "needs_confirmation": True, "hint": hint}
    err = stationary_check("write_param")
    return err

  def h_publish(args):
    from ai.tools.git_pr_tools import git_publish_pull_request
    paths = args.get("paths")
    path_list = [str(x) for x in paths] if isinstance(paths, list) else None
    common = dict(
      title=str(args.get("title", "") or ""),
      body=str(args.get("body", "") or ""),
      base_branch=str(args.get("base_branch", "") or ""),
      branch=str(args.get("branch", "") or ""),
      commit_message=str(args.get("commit_message", "") or ""),
      paths=path_list,
      draft=bool(args.get("draft")),
      remote=str(args.get("remote", "") or "origin"),
      repo_url=str(args.get("repo_url", "") or ""),
      repo_target=str(args.get("repo_target", "") or "openpilot"),
      severity=str(args.get("severity", "") or ""),
      request_auto_fix=bool(args.get("request_auto_fix")),
      params=p,
    )
    if not args.get("confirm") and needs_confirm():
      return git_publish_pull_request(**common, confirm=False)
    err = stationary_check("write_param")
    if err:
      return err
    return git_publish_pull_request(**common, confirm=True)

  def h_list_prs(args):
    from ai.tools.git_pr_tools import list_github_pull_requests
    return list_github_pull_requests(
      repo_url=str(args.get("repo_url", "") or ""),
      state=str(args.get("state", "") or "open"),
      base=str(args.get("base", "") or ""),
      head=str(args.get("head", "") or ""),
      per_page=int(args.get("per_page", 10) or 10),
      params=p,
    )

  def h_get_pr(args):
    from ai.tools.git_pr_tools import get_github_pull_request
    return get_github_pull_request(
      pull_number=int(args.get("pull_number") or 0),
      repo_url=str(args.get("repo_url", "") or ""),
      params=p,
    )

  def h_review(args):
    gate = _git_write_gate(args, "Set confirm=true to post PR review.")
    if gate:
      return gate
    from ai.tools.git_pr_tools import review_github_pull_request
    return review_github_pull_request(
      pull_number=int(args.get("pull_number") or 0),
      body=str(args.get("body", "") or ""),
      event=str(args.get("event", "") or "COMMENT"),
      repo_url=str(args.get("repo_url", "") or ""),
      confirm=True,
      params=p,
    )

  def h_merge(args):
    gate = _git_write_gate(args, "Set confirm=true to merge PR.")
    if gate:
      return gate
    from ai.tools.git_pr_tools import merge_github_pull_request
    return merge_github_pull_request(
      pull_number=int(args.get("pull_number") or 0),
      merge_method=str(args.get("merge_method", "") or "squash"),
      repo_url=str(args.get("repo_url", "") or ""),
      repo_target=str(args.get("repo_target", "") or "openpilot"),
      confirm=True,
      params=p,
    )

  def h_report_bug(args):
    from ai.tools.bug_report_tools import report_bug_and_publish_pr
    paths = args.get("paths")
    path_list = [str(x) for x in paths] if isinstance(paths, list) else None
    common = dict(
      repo_target=str(args.get("repo_target", "") or "assistant"),
      title=str(args.get("title", "") or ""),
      repro_steps=str(args.get("repro_steps", "") or ""),
      expected=str(args.get("expected", "") or ""),
      actual=str(args.get("actual", "") or ""),
      severity=str(args.get("severity", "") or "ui"),
      attach_audit=bool(args.get("attach_audit", True)),
      request_auto_fix=bool(args.get("request_auto_fix")),
      paths=path_list,
      params=p,
    )
    if not args.get("confirm") and needs_confirm():
      return report_bug_and_publish_pr(**common, confirm=False)
    err = stationary_check("write_param")
    if err:
      return err
    return report_bug_and_publish_pr(**common, confirm=True)

  def h_auto_review(args):
    gate = _git_write_gate(args, "Set confirm=true to auto-review PR.")
    if gate:
      return gate
    from ai.tools.git_pr_tools import auto_review_pull_request
    return auto_review_pull_request(
      pull_number=int(args.get("pull_number") or 0),
      repo_url=str(args.get("repo_url", "") or ""),
      approve=bool(args.get("approve")),
      merge_if_clean=bool(args.get("merge_if_clean")),
      confirm=True,
      params=p,
    )

  return {
    "git_publish_pull_request": h_publish,
    "list_github_pull_requests": h_list_prs,
    "get_github_pull_request": h_get_pr,
    "review_github_pull_request": h_review,
    "merge_github_pull_request": h_merge,
    "auto_review_pull_request": h_auto_review,
    "report_bug_and_publish_pr": h_report_bug,
  }
