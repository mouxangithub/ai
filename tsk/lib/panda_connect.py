"""Panda USB access on comma devices — unified ``panda`` + ``selfdrive.pandad``.

Product naming (devicetree ``comma <type>``):
  - **tici** — comma three (C3), internal panda F4 (DOS)
  - **tizi** — comma threeX (C3X), internal panda H7
  - **mici** — comma four (C4), internal panda H7

All firmware (F4 ``panda.bin.signed`` and H7 ``panda_h7.bin.signed``) is built from ``panda/``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PANDA_MCU_CACHE = "/persist/sp_dev_panda_mcu_type"
PANDA_MCU_LEGACY_CACHE = "/persist/dp_dev_panda_mcu_type"
DEVICE_TREE_MODEL = "/sys/firmware/devicetree/base/model"
PANDAD_MODULE = "selfdrive.pandad.pandad"

_COMMA_PRODUCTS: dict[str, dict[str, str]] = {
  "tici": {"label": "C3", "name": "comma three"},
  "tizi": {"label": "C3X", "name": "comma threeX"},
  "mici": {"label": "C4", "name": "comma four"},
}


def _openpilot_root() -> Path:
  from ai.system.paths import openpilot_root
  return openpilot_root()


def _mcu_from_raw(mcu_raw: str) -> str | None:
  if "F4" in mcu_raw:
    return "F4"
  if "H7" in mcu_raw:
    return "H7"
  return None


def _backend_for_mcu(mcu: str | None) -> dict[str, Any]:
  dos = mcu == "F4"
  return {
    "panda_backend": "panda",
    "pandad_process": "pandad",
    "pandad_module": PANDAD_MODULE,
    "tici_dos": dos,
    "tici_tres": mcu == "H7",
    "inferred_class": "C3" if dos else "C3X/C4",
  }


def get_device_type() -> str | None:
  try:
    with open(DEVICE_TREE_MODEL) as f:
      model = f.read().strip("\x00")
    tail = model.split("comma ")[-1].strip().lower()
  except OSError:
    return None
  return tail if tail in ("tici", "tizi", "mici") else None


def is_comma_hw() -> bool:
  if os.environ.get("TICI_HW") == "1":
    return True
  return get_device_type() in ("tici", "tizi", "mici")


def is_tici_hw() -> bool:
  return is_comma_hw()


def _read_mcu_cache() -> str | None:
  for path in (PANDA_MCU_CACHE, PANDA_MCU_LEGACY_CACHE):
    try:
      value = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
      continue
    if value in ("F4", "H7"):
      return value
  return None


def _query_panda_mcu_type() -> str | None:
  try:
    from panda import Panda

    panda = Panda(cli=False)
    try:
      mcu = str(panda.get_mcu_type())
    finally:
      panda.close()
  except Exception:
    return None
  return _mcu_from_raw(mcu)


def is_tici_dos() -> bool:
  if os.environ.get("TICI_DOS") == "1" or "TICI_DOS" in os.environ:
    return True
  if os.environ.get("TICI_TRES") == "1" or "TICI_TRES" in os.environ:
    return False
  cached = _read_mcu_cache()
  if cached == "F4":
    return True
  if cached == "H7":
    return False
  device = get_device_type()
  if device == "tici":
    return True
  if device in ("tizi", "mici"):
    return False
  if not is_comma_hw():
    return False
  queried = _query_panda_mcu_type()
  if queried == "F4":
    return True
  if queried == "H7":
    return False
  return False


def ensure_tici_env() -> None:
  if not is_comma_hw():
    return
  if "TICI_DOS" in os.environ or "TICI_TRES" in os.environ:
    return
  if is_tici_dos():
    os.environ["TICI_DOS"] = "1"
  else:
    os.environ["TICI_TRES"] = "1"


def panda_backend() -> str:
  return "panda"


def pandad_process_name() -> str:
  return "pandad"


def pandad_module() -> str:
  return PANDAD_MODULE


def import_panda_class():
  from panda import Panda
  return Panda


def is_manager_running() -> bool:
  try:
    return subprocess.run(
      ["pgrep", "-f", "system/manager/manager.py"],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      check=False,
    ).returncode == 0
  except OSError:
    return False


def is_pandad_running() -> bool:
  try:
    return subprocess.run(
      ["pgrep", "-f", PANDAD_MODULE],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      check=False,
    ).returncode == 0
  except OSError:
    return False


def stop_pandad() -> None:
  subprocess.run(["pkill", "-9", "-f", PANDAD_MODULE], check=False)


def start_pandad(*, wait_seconds: float = 0.5) -> bool:
  ensure_tici_env()
  root = _openpilot_root()
  env = os.environ.copy()
  try:
    subprocess.Popen(
      [sys.executable, "-m", PANDAD_MODULE],
      cwd=str(root),
      env=env,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      start_new_session=True,
    )
  except OSError:
    return False
  if wait_seconds > 0:
    time.sleep(wait_seconds)
  return is_pandad_running()


def stop_manager_and_pandad() -> None:
  subprocess.run(["pkill", "-9", "-f", "manager.py"], check=False)
  stop_pandad()
  time.sleep(2)


def restart_pandad() -> dict[str, Any]:
  ensure_tici_env()
  stop_pandad()
  time.sleep(1)
  if is_manager_running():
    return {
      "ok": True,
      "started": False,
      "pandad_process": "pandad",
      "pandad_module": PANDAD_MODULE,
      "message": "已终止 pandad。manager 正在运行，将自动重新拉起。",
    }
  started = start_pandad()
  if started:
    return {
      "ok": True,
      "started": True,
      "pandad_process": "pandad",
      "pandad_module": PANDAD_MODULE,
      "message": f"已重启 pandad（manager 未运行，已直接启动 {PANDAD_MODULE}）。",
    }
  return {
    "ok": False,
    "started": False,
    "pandad_process": "pandad",
    "pandad_module": PANDAD_MODULE,
    "message": "已终止 pandad，但未能重新启动。请尝试「重启 manager」或重启设备。",
  }


def probe_pc_panda() -> dict[str, Any]:
  out: dict[str, Any] = {"connected": False, "probe": "panda"}
  try:
    from panda import Panda

    panda = Panda(cli=False)
    try:
      mcu_raw = str(panda.get_mcu_type())
      out["connected"] = True
      out["mcu_raw"] = mcu_raw
      mcu = _mcu_from_raw(mcu_raw)
      out["panda_mcu"] = mcu
      if mcu:
        out.update(_backend_for_mcu(mcu))
    finally:
      panda.close()
  except Exception as exc:
    out["error"] = str(exc)[:240]
  return out


def host_hardware_profile() -> dict[str, Any]:
  runtime = {
    "manager_running": is_manager_running(),
    "pandad_running": is_pandad_running(),
  }
  if is_comma_hw():
    info = tici_info()
    mcu = info.get("panda_mcu_cache")
    if mcu not in ("F4", "H7"):
      if info.get("tici_dos"):
        mcu = "F4"
      elif info.get("tici_tres"):
        mcu = "H7"
      else:
        mcu = _query_panda_mcu_type()
    return {
      **info,
      **runtime,
      "host_kind_label": info.get("product_label") or info.get("device_type"),
      "panda_mcu": mcu,
      "panda_connected": True,
      "panda_probe": "comma_internal",
    }

  probe = probe_pc_panda()
  profile: dict[str, Any] = {
    "host_kind_label": "PC",
    "product_label": "PC",
    "device_type": None,
    **runtime,
    "panda_probe": "panda",
    "panda_connected": bool(probe.get("connected")),
    "panda_backend": "panda",
    "pandad_process": "pandad",
    "pandad_module": PANDAD_MODULE,
  }
  if probe.get("connected"):
    profile.update({
      "panda_mcu": probe.get("panda_mcu"),
      "tici_dos": probe.get("tici_dos"),
      "tici_tres": probe.get("tici_tres"),
      "inferred_class": probe.get("inferred_class"),
      "mcu_raw": probe.get("mcu_raw"),
    })
    if probe.get("panda_mcu") == "F4":
      profile["host_kind_label"] = "PC · F4"
    elif probe.get("panda_mcu") == "H7":
      profile["host_kind_label"] = "PC · H7"
  else:
    profile["panda_probe_error"] = probe.get("error")
  return profile


def comma_product_meta(device_type: str | None) -> dict[str, str | None]:
  meta = _COMMA_PRODUCTS.get(device_type or "", {})
  return {
    "product_label": meta.get("label"),
    "product_name": meta.get("name"),
  }


def tici_info() -> dict[str, Any]:
  ensure_tici_env()
  cached = _read_mcu_cache()
  dos = is_tici_dos()
  device = get_device_type()
  from ai.system.hardware_lite import lite_profile

  return {
    "device_type": device,
    "tici_hw": is_comma_hw(),
    "tici_dos": dos,
    "tici_tres": is_comma_hw() and not dos,
    "panda_mcu_cache": cached,
    "panda_backend": "panda",
    "pandad_process": "pandad",
    "pandad_module": PANDAD_MODULE,
    **comma_product_meta(device),
    **lite_profile(),
  }


# Backward-compatible aliases (pre-merge)
def has_panda_tici() -> bool:
  return False


def has_pandad_tici() -> bool:
  return False


def use_tici_panda_stack() -> bool:
  return False
