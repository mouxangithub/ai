"""Shared sandbox runners and policy resolution for shell/python tools.

Holds process-level singletons for ``ShellRunner`` and ``PythonRunner`` so
``tools/agent_tools`` shell handlers and the ``run_python_code`` harness tool
execute through the same sandbox boundary with one policy point.
"""
from __future__ import annotations

from typing import Any

from ai.system.paths import workspace_path

_shell_runner: Any = None
_python_runner: Any = None


def sandbox_shell_enabled(params: Any = None) -> bool:
  try:
    from ai.common.storage import read_param_bool
    return read_param_bool(params, "ai_sandbox_shell", True)
  except Exception:
    return True


def shell_runner() -> Any:
  """Return the process-level ShellRunner (create on first use)."""
  global _shell_runner
  if _shell_runner is None:
    from ai.sandbox.shell_runner import ShellRunner
    _shell_runner = ShellRunner(workspace_root=str(workspace_path("", mkdir=True)))
  return _shell_runner


def python_runner() -> Any:
  """Return the process-level PythonRunner (create on first use)."""
  global _python_runner
  if _python_runner is None:
    from ai.sandbox.python_runner import PythonRunner
    _python_runner = PythonRunner(workspace_root=str(workspace_path("", mkdir=True)))
  return _python_runner


async def run_shell_via_sandbox(command: str, *, timeout: int = 60, params: Any = None) -> dict[str, Any]:
  """Run a shell command through the sandbox ShellRunner; fall back to host on error.

  Returns a ``{ok, stdout, stderr, returncode, error?}`` dict compatible with
  the existing system.shell.run_shell_command shape.
  """
  try:
    runner = shell_runner()
    result = await runner.run_shell(command, timeout=timeout)
    return result.to_dict()
  except Exception as exc:
    from openpilot.common.swaglog import cloudlog
    cloudlog.error(f"aid: sandbox shell fell back to host: {exc}")
    from ai.system.shell import run_shell_command
    return await run_shell_command(command, timeout=timeout)