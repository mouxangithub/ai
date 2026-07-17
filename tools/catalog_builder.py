"""Merge static params_catalog.json with dragonpilot + sunnypilot UI discovery."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_STATIC = Path(__file__).resolve().parent.parent / "skills" / "params_catalog.json"
_SP_UI_ROOT = Path(__file__).resolve().parents[2] / "selfdrive" / "ui" / "sunnypilot"

_FORBIDDEN_KEYS = frozenset({
  "AdbEnabled", "SshEnabled", "SecOCKey", "AlphaLongitudinalEnabled",
  "JoystickDebugMode", "LongitudinalManeuverMode",
})
_REDACTED_KEYS = frozenset({
  "ai_api_key", "DongleId", "GithubSshKeys", "ApiCache_Device",
})

_SP_SECTION_HINTS: dict[str, str] = {
  "Mads": "MADS", "Lagd": "Lateral", "LaneTurn": "Lateral", "Blinker": "Lateral",
  "Torque": "Lateral", "LiveTorque": "Lateral", "NeuralNetwork": "Lateral",
  "EnforceTorque": "Lateral", "AutoLaneChange": "Lateral",
  "SpeedLimit": "Longitudinal", "SmartCruise": "Longitudinal", "DynamicExperimental": "Longitudinal",
  "CustomAcc": "Longitudinal", "IntelligentCruise": "Longitudinal",
  "Toyota": "Toyota", "Subaru": "Subaru", "Hyundai": "Hyundai", "Tesla": "Tesla",
  "Osm": "OSM", "ModelManager": "Models", "Mapd": "OSM",
  "Sunnylink": "Sunnylink", "Chevron": "Visuals", "DevUI": "Visuals",
  "OnroadScreen": "Display", "Interactivity": "Display", "QuickBoot": "Developer",
}


def _infer_tier(key: str) -> str:
  if key in _FORBIDDEN_KEYS:
    return "write_forbidden"
  if key in _REDACTED_KEYS:
    return "read_redacted"
  if key.startswith("dp_ui_") or key in ("IsMetric", "dp_dev_audible_alert_mode", "dp_dev_beep", "dp_dev_opview"):
    return "write_offroad_ui"
  if key == "dp_dev_last_log":
    return "read_always"
  if key.startswith("dp_dev_"):
    return "write_offroad_dev"
  if key.startswith(("dp_lat_", "dp_lon_", "dp_toyota_", "dp_honda_", "dp_vag_")):
    return "write_offroad_tune"
  if key.startswith("dp_"):
    return "write_offroad_tune"
  if key.startswith("ai_"):
    if key == "ai_api_key":
      return "read_redacted"
    if key in ("ai_web_pin",):
      return "write_offroad_dev"
    return "write_offroad_ui"
  if key.startswith(("Osm", "OSM", "Mapd")):
    return "write_offroad_tune"
  if key.startswith("ModelManager_"):
    if key in ("ModelManager_ModelsCache", "ModelManager_LastSyncTime"):
      return "read_always"
    return "write_offroad_tune"
  if key in ("SpDevBeep", "RecordAudio", "RecordFront", "ShowAdvancedControls"):
    return "write_offroad_ui"
  if key in ("QuickBootToggle", "EnableGithubRunner", "EnableCopyparty"):
    return "write_offroad_dev"
  return "write_offroad_tune"


def _infer_section(key: str) -> str:
  if key.startswith("dp_lat_"):
    return "Lateral"
  if key.startswith("dp_lon_"):
    return "Longitudinal"
  if key.startswith("dp_toyota_"):
    return "Toyota"
  if key.startswith("dp_honda_"):
    return "Honda"
  if key.startswith("dp_vag_"):
    return "VAG"
  if key.startswith("dp_ui_"):
    return "UI"
  if key.startswith("dp_dev_"):
    return "Device"
  if key.startswith("ai_"):
    return "AI"
  for prefix, section in _SP_SECTION_HINTS.items():
    if key.startswith(prefix):
      return section
  if key == "CarPlatformBundle":
    return "Vehicle"
  return "sunnypilot"


def _discover_sunnypilot_ui_params() -> set[str]:
  found: set[str] = set()
  if not _SP_UI_ROOT.is_dir():
    return found
  rx = re.compile(r'param\s*=\s*["\']([A-Za-z][A-Za-z0-9_]+)["\']')
  for path in _SP_UI_ROOT.rglob("*.py"):
    try:
      text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
      continue
    for match in rx.finditer(text):
      found.add(match.group(1))
  return found


@lru_cache(maxsize=1)
def build_merged_catalog() -> dict[str, dict[str, Any]]:
  merged: dict[str, dict[str, Any]] = {}
  if _STATIC.is_file():
    data = json.loads(_STATIC.read_text(encoding="utf-8"))
    for entry in data.get("params") or []:
      key = entry.get("key")
      if key:
        merged[key] = dict(entry)

  try:
    from dragonpilot.settings import SETTINGS
  except ImportError:
    SETTINGS = []

  for section in SETTINGS:
    section_title = section.get("title", "")
    for setting in section.get("settings", []):
      key = setting.get("key")
      if not key or setting.get("type") == "action_item":
        continue
      if key in merged:
        continue
      title = setting.get("title")
      if callable(title):
        title = str(title)
      desc = setting.get("description")
      if callable(desc):
        desc = str(desc)
      entry: dict[str, Any] = {
        "key": key,
        "tier": _infer_tier(key),
        "section": section_title or _infer_section(key),
        "summary": (desc or title or key)[:200],
      }
      brands = setting.get("brands")
      if brands:
        entry["brands"] = brands
      merged[key] = entry

  for key in sorted(_discover_sunnypilot_ui_params()):
    if key in merged:
      continue
    merged[key] = {
      "key": key,
      "tier": _infer_tier(key),
      "section": _infer_section(key),
      "summary": key,
    }

  return merged


def clear_catalog_cache() -> None:
  build_merged_catalog.cache_clear()
