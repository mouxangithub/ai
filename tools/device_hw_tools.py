"""C3 / Lite / aux Panda / SpDevBeep device helpers for op助手."""

from __future__ import annotations

import os
from typing import Any

from openpilot.common.params import Params

from ai.system.hardware_lite import detect_lite_hw, lite_profile
from ai.system.paths import is_comma_device


def get_sp_device_hw(params: Params | None = None, get_state_reader=None) -> dict[str, Any]:
  """Lite variant, SpDevBeep, Panda count, board hints."""
  params = params or Params()
  lp = lite_profile(params)

  panda_count = None
  pandas: list[Any] = []
  if get_state_reader is not None:
    try:
      reader = get_state_reader()
      reader.update(timeout=0)
      full = reader.latest()
      if isinstance(full, dict):
        pandas = full.get("pandaStates") or []
        panda_count = len(pandas)
    except Exception:
      pass

  board = None
  try:
    from ai.tsk.lib.panda_connect import tici_info
    info = tici_info()
    board = info.get("device_type") or info.get("product_label")
  except Exception:
    if os.path.isfile("/TICI"):
      board = "tici"

  return {
    "ok": True,
    "is_comma_device": is_comma_device(),
    **lp,
    "panda_count": panda_count,
    "pandas_preview": pandas[:3],
    "board": board,
    "hint": "Set SpDevBeep via set_sp_dev_beep (offroad). Aux Panda is launch-time only (set_aux_panda in launch_chffrplus.sh).",
  }


def set_sp_dev_beep(params: Params, enabled: bool) -> dict[str, Any]:
  lite = detect_lite_hw()
  if lite is False:
    return {
      "ok": False,
      "error": "SpDevBeep is for Lite C3 only (this device has soundd).",
    }
  if lite is None and not is_comma_device():
    return {
      "ok": True,
      "SpDevBeep": bool(enabled),
      "warning": "Lite hardware not detected; SpDevBeep/beepd only applies to Lite C3.",
    }
  params.put_bool("SpDevBeep", bool(enabled))
  return {"ok": True, "SpDevBeep": bool(enabled), "note": "Requires LITE=1 and onroad for beepd process."}
