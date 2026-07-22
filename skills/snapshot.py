"""Skills prompt snapshot cache — stable prompts across chat rounds."""

from __future__ import annotations

import threading
from typing import Any

from ai.skills.loader import build_skills_prompt, load_enabled_skill_ids

_lock = threading.Lock()
_cache: dict[str, str] = {}
_warmed = False


def _cache_key(
  enabled_ids: set[str] | None,
  brand: str,
  available_tools: set[str] | None,
) -> str:
  enabled = ",".join(sorted(enabled_ids or []))
  tools = ",".join(sorted(available_tools or []))
  return f"{enabled}|{brand.lower()}|{tools}"


def warm_skills_snapshot(params, *, brand: str = "") -> int:
  """Pre-build skills prompt for common tool sets at startup."""
  global _warmed
  enabled = load_enabled_skill_ids(params)
  count = 0
  for tools in (None, set()):
    key = _cache_key(enabled, brand, tools)
    prompt = build_skills_prompt(enabled, brand=brand, available_tools=tools)
    with _lock:
      _cache[key] = prompt
    if prompt:
      count += 1
  _warmed = True
  return count


def get_skills_prompt(
  params,
  *,
  brand: str = "",
  available_tools: set[str] | None = None,
) -> str:
  enabled = load_enabled_skill_ids(params)
  key = _cache_key(enabled, brand, available_tools)
  with _lock:
    if key in _cache:
      return _cache[key]
  prompt = build_skills_prompt(enabled, brand=brand, available_tools=available_tools)
  with _lock:
    _cache[key] = prompt
  return prompt


def clear_skills_snapshot() -> None:
  with _lock:
    _cache.clear()


def snapshot_stats() -> dict[str, Any]:
  with _lock:
    return {"warmed": _warmed, "entries": len(_cache)}
