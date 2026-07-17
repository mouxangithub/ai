"""sunnypilot settings catalog + current values (no Dashy required)."""

from __future__ import annotations

from typing import Any

from openpilot.common.params import Params

from ai.tools.catalog_builder import build_merged_catalog

_BOOL_KEYS = frozenset({
  "ExperimentalMode", "SpDevBeep", "RecordAudio", "RecordFront", "Mads", "LagdToggle",
  "LaneTurnDesire", "NeuralNetworkLateralControl", "DynamicExperimentalControl",
  "SmartCruiseControlMap", "SmartCruiseControlVision", "CustomTorqueParams",
  "LiveTorqueParamsToggle", "LiveTorqueParamsRelaxedToggle", "TorqueParamsOverrideEnabled",
  "EnforceTorqueControl", "BlindSpot", "RainbowMode", "QuietMode", "OsmLocal",
  "SunnylinkEnabled", "EnableSunnylinkUploader", "ShowAdvancedControls",
  "EnableGithubRunner", "EnableCopyparty", "QuickBootToggle", "OnroadUploads",
  "ToyotaStopAndGoHack", "ToyotaEnforceStockLongitudinal", "SubaruStopAndGo",
  "TeslaCoopSteering", "IntelligentCruiseButtonManagement", "CustomAccIncrementsEnabled",
  "LeadDepartAlert", "GreenLightAlert", "StandstillTimer", "RoadNameToggle",
  "TrueVEgoUI", "HideVEgoUI", "ShowTurnSignals", "RocketFuel", "TorqueBar",
})


def _read_param(params: Params, key: str, entry: dict[str, Any]) -> Any:
  if entry.get("tier") == "read_redacted":
    return None
  try:
    if key.endswith("Toggle") or key in _BOOL_KEYS:
      if params.get(key) is not None:
        try:
          return params.get_bool(key)
        except Exception:
          pass
    val = params.get(key, return_default=True)
    if val is None:
      val = params.get(key)
    if isinstance(val, bytes):
      return val.decode("utf-8", errors="replace")
    return val
  except Exception:
    return None


def list_sp_settings(params: Params | None = None, brand: str = "") -> dict[str, Any]:
  """Return sunnypilot tunable params grouped by section with current values (merged catalog)."""
  params = params or Params()
  catalog = build_merged_catalog()
  sections: dict[str, list[dict[str, Any]]] = {}

  for key, entry in sorted(catalog.items()):
    if entry.get("tier") == "write_forbidden":
      continue
    brands = entry.get("brands")
    if brands and brand and brand.lower() not in [b.lower() for b in brands]:
      continue
    section = entry.get("section", "General")
    sections.setdefault(section, []).append({
      "key": key,
      "section": section,
      "title": entry.get("title") or entry.get("summary", key),
      "description": entry.get("summary", ""),
      "tier": entry.get("tier", "read_always"),
      "current_value": _read_param(params, key, entry),
      "brands": brands,
      "ui_source": entry.get("ui_source"),
    })

  sections_out = [{"title": title, "settings": items} for title, items in sorted(sections.items())]
  return {
    "ok": True,
    "fork": "sunnypilot",
    "brand": brand,
    "catalog_source": "merged",
    "catalog_count": len(catalog),
    "sections": sections_out,
    "setting_count": sum(len(s["settings"]) for s in sections_out),
  }


list_dp_settings = list_sp_settings
