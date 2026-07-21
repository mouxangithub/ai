"""Context manager to run git commands against openpilot or assistant ai repo."""

from __future__ import annotations

import contextvars

_git_repo_target: contextvars.ContextVar[str] = contextvars.ContextVar("git_repo_target", default="openpilot")


def current_git_repo_target() -> str:
  return _git_repo_target.get()


class git_repo_context:
  def __init__(self, repo_target: str = "openpilot") -> None:
    self._repo_target = repo_target or "openpilot"
    self._token = None

  def __enter__(self) -> "git_repo_context":
    self._token = _git_repo_target.set(self._repo_target)
    return self

  def __exit__(self, *_args) -> None:
    if self._token is not None:
      _git_repo_target.reset(self._token)
