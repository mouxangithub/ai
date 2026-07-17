"""sunnypilot settings catalog + current values (no Dashy required)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpilot.common.params import Params

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "skills" / "params_catalog.json"


def _load_catalog() -> list[dict[str, Any]]:
  if not _CATALOG_PATH.is_file():
    return []
  data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
  return list(data.get("params", []))


def _read_param(params: Params, key: str) -> Any:
  try:
    if key.endswith("Toggle") or key in ("ExperimentalMode", "SpDevBeep", "RecordAudio", "RecordFront"):
      return params.get_bool(key)
    val = params.get(key)
    if val is None:
      return None
    if isinstance(val, bytes):
      return val.decode("utf-8", errors="replace")
    return val
  except Exception:
    return None


def list_sp_settings(params: Params | None = None, brand: str = "") -> dict[str, Any]:
  """Return sunnypilot tunable params grouped by section with current values."""
  params = params or Params()
  catalog = _load_catalog()
  sections: dict[str, list[dict[str, Any]]] = {}

  for entry in catalog:
    key = entry.get("key")
    if not key:
      continue
    brands = entry.get("brands")
    if brands and brand and brand.lower() not in [b.lower() for b in brands]:
      continue
    section = entry.get("section", "General")
    sections.setdefault(section, []).append({
      "key": key,
      "section": section,
      "title": entry.get("summary", key),
      "description": entry.get("summary", ""),
      "tier": entry.get("tier", "read_always"),
      "current_value": _read_param(params, key),
      "brands": brands,
    })

  sections_out = [{"title": title, "settings": items} for title, items in sorted(sections.items())]
  return {
    "ok": True,
    "fork": "sunnypilot",
    "brand": brand,
    "sections": sections_out,
    "setting_count": sum(len(s["settings"]) for s in sections_out),
  }


# Backwards-compatible alias for migrated tool handlers
list_dp_settings = list_sp_settings
