"""Car platform selection via sunnypilot CarPlatformBundle (Settings → Vehicle)."""

from __future__ import annotations

import json
import os
from typing import Any

from openpilot.common.basedir import BASEDIR
from openpilot.common.params import Params

CAR_LIST_JSON = os.path.join(BASEDIR, "sunnypilot", "selfdrive", "car", "car_list.json")

_car_list_cache: dict[str, Any] | None = None


def load_car_list() -> dict[str, Any]:
  global _car_list_cache
  if _car_list_cache is None:
    with open(CAR_LIST_JSON, encoding="utf-8") as f:
      _car_list_cache = json.load(f)
  return _car_list_cache


def resolve_car_platform_bundle(model: str) -> dict[str, Any] | None:
  """Resolve display name or opendbc platform id to a CarPlatformBundle dict."""
  model = model.strip()
  if not model:
    return None

  cars = load_car_list()
  if model in cars:
    return {**cars[model], "name": model}

  for name, data in cars.items():
    if data.get("platform") == model:
      return {**data, "name": name}
  return None


def put_car_platform_bundle(params: Params, model: str) -> dict[str, Any]:
  model = str(model or "").strip()
  if not model:
    if params.get("CarPlatformBundle"):
      params.remove("CarPlatformBundle")
    return {"ok": True, "mode": "auto"}

  bundle = resolve_car_platform_bundle(model)
  if bundle is None:
    return {"ok": False, "error": f"unknown platform: {model}"}

  params.put("CarPlatformBundle", bundle)
  return {"ok": True, "platform": bundle["platform"], "name": bundle["name"]}


def preview_car_platform_change(params: Params, model: str) -> dict[str, Any]:
  model = str(model or "").strip()
  if not model:
    before = params.get("CarPlatformBundle")
    if before is None:
      return {"ok": True, "changes": {}, "change_count": 0}
    return {
      "ok": True,
      "changes": {"CarPlatformBundle": {"before": before, "after": None}},
      "change_count": 1,
    }

  bundle = resolve_car_platform_bundle(model)
  if bundle is None:
    return {"ok": False, "error": f"unknown platform: {model}"}

  from ai.tools.diagnostics_tools import diff_params
  return diff_params(params, {"CarPlatformBundle": bundle})
