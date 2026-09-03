"""Sandbox / code-runtime abstraction seam.

Mirrors the ``@deepseek-ai/dsh-sandbox`` and ``@deepseek-ai/dsh-code-runtime``
service definitions in plain Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]
ConfinedSandboxMode = Literal["read-only", "workspace-write"]


@dataclass(frozen=True)
class SandboxPolicy:
  """Per-call file-effect policy for a confined execution."""

  mode: ConfinedSandboxMode
  workspace_root: str = "."


@dataclass(frozen=True)
class SandboxExecutionPolicy:
  """Resolved policy including the unsafe passthrough mode."""

  mode: SandboxMode
  workspace_root: str = "."


@dataclass
class RunResult:
  """Outcome of running code or a shell command in the sandbox."""

  ok: bool
  stdout: str = ""
  stderr: str = ""
  returncode: int | None = None
  duration_ms: int = 0
  error: str | None = None
  error_kind: Literal[
    "exception", "timeout", "abort", "worker-exit", "invalid-output",
    "output-limit", "blocked", "sandbox-unavailable",
  ] | None = None

  def to_dict(self) -> dict[str, Any]:
    result: dict[str, Any] = {
      "ok": self.ok,
      "stdout": self.stdout,
      "stderr": self.stderr,
      "returncode": self.returncode,
      "durationMs": self.duration_ms,
    }
    if self.error is not None:
      result["error"] = self.error
    if self.error_kind is not None:
      result["errorKind"] = self.error_kind
    return result


class SandboxRuntime:
  """Abstract sandbox runtime that can run Python code and shell commands.

  Concrete implementations may use subprocesses, containers, or E2B sandboxes.
  The interface is intentionally small so callers can swap backends.
  """

  def __init__(
    self,
    *,
    default_timeout: int = 30,
    max_output_bytes: int = 2 * 1024 * 1024,
    workspace_root: str | None = None,
  ) -> None:
    self.default_timeout = default_timeout
    self.max_output_bytes = max_output_bytes
    self.workspace_root = workspace_root or "."

  async def run_python(
    self,
    code: str,
    *,
    timeout: int | None = None,  # noqa: ASYNC109
    bindings: dict[str, Any] | None = None,
  ) -> RunResult:
    """Run a Python program and return its captured output."""
    raise NotImplementedError

  async def run_shell(
    self,
    command: str | list[str],
    *,
    timeout: int | None = None,  # noqa: ASYNC109
    policy: SandboxPolicy | None = None,
  ) -> RunResult:
    """Run a shell command under the given file-effect policy."""
    raise NotImplementedError

  def is_blocked_command(self, command: str) -> str | None:
    """Return a refusal reason if the command is disallowed, else None."""
    return None
