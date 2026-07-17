"""C3 Lite hardware variant — detection and AI param policy.

Lite = comma three (C3 / tici) without I2C audio amp @ 0x10.
When ``LITE=1``: no micd/soundd/dmonitoring*; use ``beepd`` + ``SpDevBeep`` for feedback.
Not the same as PrimeType.LITE (subscription tier).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from openpilot.common.params import Params

from ai.system.paths import is_comma_device

# Writes blocked on Lite (hardware cannot honor these).
LITE_BLOCKED_WRITE_PARAMS = frozenset({
  "RecordAudio",
  "AlwaysOnDM",
})

# Shown as unavailable in list_sp_settings (includes blocked + ineffective).
LITE_UNAVAILABLE_PARAMS = frozenset({
  "RecordAudio",
  "AlwaysOnDM",
})

LITE_UNAVAILABLE_NOTE = (
  "Lite 硬件无麦克风与驾驶员监控进程；声音反馈请用 SpDevBeep + beepd，勿启用本项。"
)


def detect_lite_hw() -> bool | None:
  """True=Lite, False=full C3 audio, None=unknown (PC or probe failed)."""
  if os.getenv("LITE"):
    return True
  if not is_comma_device():
    return None
  try:
    proc = subprocess.run(
      ["i2cget", "-y", "0", "0x10"],
      capture_output=True,
      text=True,
      timeout=3,
    )
    return proc.returncode != 0
  except Exception:
    return None


def is_lite_hw() -> bool:
  return detect_lite_hw() is True


def lite_write_block_reason(key: str) -> str | None:
  if is_lite_hw() and key in LITE_BLOCKED_WRITE_PARAMS:
    return (
      f"Param '{key}' is unavailable on Lite C3 (no microphone / no dmonitoring). "
      f"Use set_sp_dev_beep for GPIO beep feedback instead."
    )
  return None


def lite_profile(params: Params | None = None) -> dict[str, Any]:
  params = params or Params()
  lite = detect_lite_hw()
  beep = None
  try:
    if params.get("SpDevBeep") is not None:
      beep = params.get_bool("SpDevBeep")
  except Exception:
    pass

  out: dict[str, Any] = {
    "lite": lite,
    "lite_env": bool(os.getenv("LITE")),
    "lite_note": (
      "LITE=1: micd/soundd/dmonitoringd off; beepd when SpDevBeep=1. C3 only (not C3X/C4)."
      if lite
      else ("Full C3 audio stack" if lite is False else "Lite status unknown off-device")
    ),
    "SpDevBeep": beep,
    "beepd_eligible": lite is True and beep is True,
    "audio_feedback": "beepd" if lite else "soundd",
    "unavailable_params": sorted(LITE_UNAVAILABLE_PARAMS) if lite else [],
  }
  return out
