"""OpenClaw-style workspace markdown — SOUL, AGENTS, HEARTBEAT."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_WORKSPACE = Path(__file__).resolve().parent

_FILES = {
  "soul": "SOUL.md",
  "agents": "AGENTS.md",
  "heartbeat": "HEARTBEAT.md",
  "tools": "TOOLS.md",
  "memory": "MEMORY.md",
}


def workspace_dir() -> Path:
  _WORKSPACE.mkdir(parents=True, exist_ok=True)
  return _WORKSPACE


def read_workspace_file(key: str) -> str:
  name = _FILES.get(key, key)
  path = workspace_dir() / name
  if not path.is_file():
    return ""
  return path.read_text(encoding="utf-8", errors="replace").strip()


def write_workspace_file(key: str, content: str) -> dict[str, Any]:
  name = _FILES.get(key, key)
  path = workspace_dir() / name
  path.write_text(content or "", encoding="utf-8")
  return {"ok": True, "path": str(path), "key": key}


def ensure_default_workspace_files() -> None:
  d = workspace_dir()
  defaults = {
    "SOUL.md": (
      "# SOUL — op助手人格\n\n"
      "你是 openpilot 车载研发助手：专业、简洁、以安全为先。\n"
      "行驶中可诊断与 shell，禁止控车。\n"
    ),
    "AGENTS.md": (
      "# AGENTS — 专员编排\n\n"
      "默认调度 OP；多域问题自动分派 triage/tune/secoc 等专员。\n"
    ),
    "HEARTBEAT.md": (
      "# HEARTBEAT — 定时巡检清单\n\n"
      "- [ ] 检查 manager 日志是否有 error/fault\n"
      "- [ ] 车辆静止时检查待写入 tune 草稿\n"
      "- [ ] 未读通知 > 0 时摘要推送\n"
    ),
    "TOOLS.md": (
      "# TOOLS — 工具策略\n\n"
      "行驶中：read/shell/diagnostics 可用；write/tune/restart 需静止。\n"
    ),
    "MEMORY.md": (
      "# MEMORY — 工作区记忆\n\n"
      "长期记忆见 Params ai_memory_notes；此处可放项目备注。\n"
    ),
  }
  for fname, body in defaults.items():
    p = d / fname
    if not p.is_file():
      p.write_text(body, encoding="utf-8")


def workspace_prompt_blocks() -> list[str]:
  ensure_default_workspace_files()
  blocks: list[str] = []
  for key in ("soul", "agents", "tools"):
    text = read_workspace_file(key)
    if text:
      blocks.append(text)
  return blocks


def heartbeat_checklist() -> str:
  ensure_default_workspace_files()
  return read_workspace_file("heartbeat")


def list_workspace_files() -> list[dict[str, Any]]:
  ensure_default_workspace_files()
  out = []
  for key, fname in _FILES.items():
    p = workspace_dir() / fname
    out.append({
      "key": key,
      "name": fname,
      "exists": p.is_file(),
      "size": p.stat().st_size if p.is_file() else 0,
    })
  return out
