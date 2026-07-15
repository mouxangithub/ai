"""Generate fork-specific skill/doc drafts using configured LLM (P5)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai.fork.detect_fork import detect_fork, profile_for_fork

AI_DIR = Path(__file__).resolve().parent.parent
DRAFTS_DIR = AI_DIR / "data" / "fork_drafts"
MAX_SCAN_LINES = 400


def _scan_params_keys(root: Path, prefixes: list[str]) -> list[str]:
  for rel in ("common/params_keys.h", "openpilot/common/params_keys.h"):
    path = root / rel
    if not path.is_file():
      continue
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:2000]:
      m = re.search(r'\{"([^"]+)"', line)
      if not m:
        continue
      key = m.group(1)
      if not prefixes or any(key.startswith(p) for p in prefixes):
        keys.append(key)
    return keys[:120]
  return []


def _scan_settings_dirs(root: Path) -> list[str]:
  hints: list[str] = []
  for rel in ("dragonpilot/settings", "sunnypilot", "carrot"):
    d = root / rel
    if d.is_dir():
      py_files = sorted(d.rglob("*.py"))[:12]
      hints.append(f"{rel}: {len(py_files)} settings modules")
  return hints


def build_fork_context(root: Path, fork_id: str | None = None) -> dict[str, Any]:
  detected = detect_fork(root)
  fid = fork_id or detected.get("fork_id") or "openpilot"
  profile = profile_for_fork(fid) or {}
  prefixes = list(profile.get("param_prefixes") or [])
  return {
    "fork_id": fid,
    "fork_label": profile.get("label", fid),
    "detected": detected,
    "profile": profile,
    "param_keys_sample": _scan_params_keys(root, prefixes),
    "settings_hints": _scan_settings_dirs(root),
    "recommended_skills": profile.get("skills", []),
    "recommended_docs": profile.get("docs", []),
  }


def _draft_paths(fork_id: str) -> dict[str, Path]:
  base = DRAFTS_DIR / fork_id
  return {
    "base": base,
    "skill": base / "FORK_SKILL.md",
    "tools": base / "tools_notes.md",
    "manifest": base / "manifest.json",
  }


async def generate_fork_drafts(
  params: Any,
  *,
  fork_id: str | None = None,
  openpilot_root: Path | None = None,
) -> dict[str, Any]:
  """Use configured chat model to draft fork-specific guidance (human review required)."""
  from ai.client import chat_completion_collect, load_config_from_params
  from ai.system.paths import openpilot_root as default_root

  root = openpilot_root or default_root()
  ctx = build_fork_context(root, fork_id)
  fid = ctx["fork_id"]
  paths = _draft_paths(fid)
  paths["base"].mkdir(parents=True, exist_ok=True)

  config = load_config_from_params(params)
  if not config.is_configured:
    return {"ok": False, "error": config.configuration_error or "AI not configured", "fork_id": fid}

  system = (
    "You are an openpilot fork integration assistant. "
    "Output concise Markdown for maintainers. Do not invent unsafe vehicle controls. "
    "Focus on params, skills, and documentation alignment for the detected fork."
  )
  user = f"""Analyze this fork context and produce TWO markdown sections.

## Context (JSON)
```json
{json.dumps(ctx, ensure_ascii=False, indent=2)[:12000]}
```

## Output format
### Section A: FORK_SKILL
A skill draft (YAML frontmatter + markdown) for op助手 describing fork-specific tuning params and workflows.

### Section B: TOOLS_NOTES
Bullet list of suggested tool/skill/doc updates for this fork (no code, just actionable notes).

Keep total under 2500 words."""

  text, _reasoning, err = await chat_completion_collect(
    config,
    [
      {"role": "system", "content": system},
      {"role": "user", "content": user},
    ],
    timeout_total=180,
  )
  if err:
    return {"ok": False, "error": err, "fork_id": fid}

  skill_part = text
  tools_part = ""
  if "### Section B" in text:
    parts = re.split(r"### Section B:\s*TOOLS_NOTES\s*", text, maxsplit=1)
    skill_part = re.sub(r"^### Section A:.*?\n", "", parts[0], flags=re.S).strip()
    tools_part = parts[1].strip() if len(parts) > 1 else ""

  paths["skill"].write_text(skill_part.strip() + "\n", encoding="utf-8")
  paths["tools"].write_text(tools_part.strip() + "\n", encoding="utf-8")
  manifest = {
    "fork_id": fid,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "model": config.model,
    "provider": config.provider,
    "paths": {k: str(v) for k, v in paths.items()},
    "context_summary": {
      "param_keys_count": len(ctx.get("param_keys_sample") or []),
      "recommended_skills": ctx.get("recommended_skills"),
    },
  }
  paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

  return {
    "ok": True,
    "fork_id": fid,
    "draft_dir": str(paths["base"]),
    "skill_draft": str(paths["skill"]),
    "tools_notes": str(paths["tools"]),
    "manifest": manifest,
    "preview": skill_part[:1500],
  }


def list_fork_drafts() -> list[dict[str, Any]]:
  if not DRAFTS_DIR.is_dir():
    return []
  out: list[dict[str, Any]] = []
  for manifest_path in sorted(DRAFTS_DIR.glob("*/manifest.json")):
    try:
      data = json.loads(manifest_path.read_text(encoding="utf-8"))
      out.append(data)
    except Exception:
      continue
  return out
