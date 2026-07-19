"""F4 (black/DOS) panda firmware helpers for op助手.

Self-contained: does **not** require ``tools/recover_dos_panda.py`` (optional CLI wrapper on some forks).
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from ai.system.paths import openpilot_root

FW_REL = Path("panda", "board", "obj", "panda.bin.signed")
REBUILD_SCRIPT = Path("tools", "rebuild_pandad_tici.sh")
RECOVER_SCRIPT = Path("tools", "recover_dos_panda.py")


def _fw_path() -> Path:
  return openpilot_root() / FW_REL


def _python() -> str:
  venv_py = Path("/usr/local/venv/bin/python3")
  if venv_py.is_file():
    return str(venv_py)
  return sys.executable


def _sub_env() -> dict[str, str]:
  root = str(openpilot_root())
  env = os.environ.copy()
  env["PYTHONPATH"] = root
  path = env.get("PATH", "")
  for prefix in ("/usr/local/venv/bin", "/usr/bin", "/bin"):
    if prefix not in path.split(":"):
      path = f"{prefix}:{path}" if path else prefix
  env["PATH"] = path
  return env


def shutil_which(cmd: str) -> str | None:
  from shutil import which
  return which(cmd)


def _describe_panda(serial: str) -> dict[str, Any]:
  try:
    from panda import Panda

    p = Panda(serial)
    hw = p.get_type()
    internal = p.is_internal()
    mcu = p.get_mcu_type().config.app_fn
    bootstub = p.bootstub
    p.close()
    return {
      "serial": serial,
      "internal": internal,
      "hw_type": hw.hex() if isinstance(hw, bytes) else str(hw),
      "mcu": mcu,
      "bootstub": bootstub,
      "is_f4": hw in Panda.F4_DEVICES,
    }
  except Exception as e:
    return {"serial": serial, "error": str(e)}


def pick_serial(serials: list[str], *, external: bool, internal: bool) -> str | None:
  try:
    from panda import Panda
  except ImportError:
    return serials[0] if serials else None

  if not serials:
    return None

  candidates: list[str] = []
  for serial in serials:
    try:
      p = Panda(serial)
      is_internal = p.is_internal()
      is_f4 = p.get_type() in Panda.F4_DEVICES
      p.close()
    except Exception:
      continue
    if not is_f4:
      continue
    if external and not is_internal:
      candidates.append(serial)
    elif internal and is_internal:
      candidates.append(serial)
    elif not external and not internal:
      candidates.append(serial)

  if external or internal:
    return candidates[0] if candidates else None

  for serial in serials:
    try:
      p = Panda(serial)
      if p.is_internal() and p.get_type() in Panda.F4_DEVICES:
        p.close()
        return serial
      p.close()
    except Exception:
      continue
  return serials[0]


def recover_dfu() -> tuple[list[str], str]:
  """Try internal DFU recovery. Returns (serials, log text)."""
  from panda import Panda, PandaDFU
  from openpilot.common.hardware import HARDWARE

  buf = io.StringIO()
  with redirect_stdout(buf), redirect_stderr(buf):
    print("no panda found, entering DFU recovery...")
    HARDWARE.recover_internal_panda()
    if not Panda.wait_for_dfu(None, 15):
      print("DFU not found")
      return [], buf.getvalue()
    dfu = PandaDFU(None)
    print("DFU mcu:", dfu.get_mcu_type())
    dfu.recover()
    dfu.reset()
    time.sleep(2)
    if not Panda.wait_for_panda(None, 30):
      print("panda did not come back after DFU recover")
      return [], buf.getvalue()
    serials = Panda.list()
    print("pandas after DFU:", serials)
  return serials, buf.getvalue()


def flash_serial(serial: str, *, fw_path: Path | None = None) -> dict[str, Any]:
  """Flash one F4 panda. Returns structured result (no process exit codes)."""
  from panda import Panda

  fw = fw_path or _fw_path()
  log = io.StringIO()

  def _log(msg: str) -> None:
    log.write(msg + "\n")

  try:
    p = Panda(serial)
    _log(f"serial: {serial}")
    _log(f"bootstub: {p.bootstub}")
    _log(f"hw_type: {p.get_type()!r}")
    _log(f"internal: {p.is_internal()}")
    _log(f"mcu: {p.get_mcu_type()}")

    if not fw.is_file():
      p.close()
      return {"ok": False, "error": f"missing firmware: {fw}", "log": log.getvalue()}

    expected = Panda.get_signature_from_firmware(str(fw))
    _log(f"expected sig: {expected.hex()[:16]}")
    if not p.bootstub:
      try:
        current_sig = p.get_signature()
        _log(f"current sig: {current_sig.hex()[:16]}")
        _log(f"health pkt: {p.get_packets_versions()}")
        if current_sig == expected:
          _log("firmware already matches, no flash needed")
          p.close()
          return {"ok": True, "skipped": True, "serial": serial, "log": log.getvalue()}
      except Exception as e:
        _log(f"health read error: {e}")

    _log(f"flashing {fw}")
    code = fw.read_bytes()
    mcu_type = p.get_mcu_type()
    if not p.bootstub:
      try:
        p._handle.controlWrite(Panda.REQUEST_IN, 0xd1, 1, 0, b'', timeout=15000, expect_disconnect=True)
      except Exception:
        pass
      p.close()
      time.sleep(1)
      p = Panda(serial)
    if not p.bootstub:
      p.close()
      return {"ok": False, "error": "failed to enter bootstub", "log": log.getvalue()}

    Panda.flash_static(p._handle, code, mcu_type=mcu_type)
    p.close()

    time.sleep(2)
    p2 = Panda(serial)
    _log(f"after flash bootstub: {p2.bootstub}")
    _log(f"version: {p2.get_version()}")
    _log(f"signature: {p2.get_signature().hex()[:16]}")
    _log(f"health pkt: {p2.get_packets_versions()}")
    ok = (not p2.bootstub) and p2.get_signature() == expected
    p2.close()
    _log("OK" if ok else "FAILED")
    return {
      "ok": ok,
      "serial": serial,
      "flash_ok": ok,
      "log": log.getvalue(),
    }
  except Exception as e:
    return {"ok": False, "error": str(e), "log": log.getvalue()}


def execute_recover_dos_panda(
  *,
  serial: str = "",
  external: bool = False,
  internal: bool = False,
  try_dfu: bool = True,
) -> dict[str, Any]:
  """Core recover/flash implementation (no subprocess, no external script)."""
  try:
    from panda import Panda
  except ImportError as e:
    return {"ok": False, "error": f"panda module unavailable: {e}"}

  fw = _fw_path()
  if not fw.is_file():
    return {"ok": False, "error": f"missing firmware: {fw}", "hint": "build_panda_firmware first"}

  logs: list[str] = []
  serials = Panda.list()
  logs.append(f"pandas: {serials}")
  for s in serials:
    logs.append(f"  {_describe_panda(s)}")

  if not serials and try_dfu:
    serials, dfu_log = recover_dfu()
    logs.append(dfu_log)
    if not serials:
      return {"ok": False, "error": "no panda after DFU", "log": "\n".join(logs), "implementation": "inline"}

  if not serials:
    return {"ok": False, "error": "no panda found", "log": "\n".join(logs), "implementation": "inline"}

  if serial:
    if serial not in serials:
      return {"ok": False, "error": f"serial not found: {serial}", "log": "\n".join(logs)}
    target = serial
  else:
    target = pick_serial(serials, external=external, internal=internal)
    if target is None:
      kind = "external" if external else ("internal" if internal else "F4")
      return {"ok": False, "error": f"no {kind} panda found", "log": "\n".join(logs)}
  logs.append(f"selected: {target}")

  result = flash_serial(target, fw_path=fw)
  result["log"] = "\n".join(logs) + "\n" + result.get("log", "")
  result["implementation"] = "inline"
  result["recover_script_present"] = (openpilot_root() / RECOVER_SCRIPT).is_file()
  return result


def list_f4_pandas() -> dict[str, Any]:
  """List connected F4 pandas (DOS/black) with internal/external hints."""
  try:
    from panda import Panda
  except ImportError as e:
    return {"ok": False, "error": f"panda module unavailable: {e}"}

  serials = Panda.list()
  entries = [_describe_panda(s) for s in serials]
  f4 = [e for e in entries if e.get("is_f4")]
  fw = _fw_path()
  script = openpilot_root() / RECOVER_SCRIPT
  return {
    "ok": True,
    "serials": serials,
    "pandas": entries,
    "f4_pandas": f4,
    "firmware_path": str(fw),
    "firmware_exists": fw.is_file(),
    "recover_script": str(script),
    "recover_script_present": script.is_file(),
    "flash_implementation": "inline (ai.tools.panda_flash_tools); script optional",
    "hint": "F4/DOS 固件在 panda/，不要用 panda_tici 固件。刷机用 recover_dos_panda(confirm=true)。",
  }


def build_panda_firmware(*, jobs: int = 4) -> dict[str, Any]:
  """Compile panda/board F4 firmware (panda.bin.signed)."""
  board = openpilot_root() / "panda" / "board"
  if not board.is_dir():
    return {"ok": False, "error": f"missing panda/board at {board}"}
  if not shutil_which("scons"):
    return {"ok": False, "error": "scons not found in PATH"}
  jobs = max(1, min(int(jobs or 4), 32))
  try:
    proc = subprocess.run(
      ["scons", f"-j{jobs}"],
      cwd=str(board),
      env=_sub_env(),
      capture_output=True,
      text=True,
      timeout=600,
    )
    fw = _fw_path()
    return {
      "ok": proc.returncode == 0 and fw.is_file(),
      "returncode": proc.returncode,
      "firmware_path": str(fw),
      "firmware_exists": fw.is_file(),
      "stdout_tail": (proc.stdout or "")[-2000:],
      "stderr_tail": (proc.stderr or "")[-1000:],
    }
  except subprocess.TimeoutExpired:
    return {"ok": False, "error": "scons timed out after 600s"}
  except Exception as e:
    return {"ok": False, "error": str(e)}


def rebuild_pandad_tici(*, confirm: bool = False) -> dict[str, Any]:
  """Re-link pandad_tici binary after git reset (offroad). Script optional on some forks."""
  script = openpilot_root() / REBUILD_SCRIPT
  pandad_dir = openpilot_root() / "selfdrive" / "pandad_tici"
  if not script.is_file() and not pandad_dir.is_dir():
    return {
      "ok": False,
      "error": "pandad_tici not found in this fork",
      "hint": "SP/sunnypilot C3 forks: tools/rebuild_pandad_tici.sh; others: manager_control(rebuild) or full scons.",
    }
  if not confirm:
    return {
      "ok": True,
      "needs_confirmation": True,
      "script": str(script) if script.is_file() else None,
      "hint": "Set confirm=true to run rebuild (offroad only).",
    }
  if not script.is_file():
    return {
      "ok": False,
      "error": f"missing {script}",
      "hint": "Fork has pandad_tici but no rebuild script; run full build or copy script from sunnypilot.",
      "pandad_dir": str(pandad_dir),
    }
  try:
    proc = subprocess.run(
      ["bash", str(script)],
      cwd=str(openpilot_root()),
      env=_sub_env(),
      capture_output=True,
      text=True,
      timeout=300,
    )
    return {
      "ok": proc.returncode == 0,
      "returncode": proc.returncode,
      "stdout": (proc.stdout or "")[-3000:],
      "stderr": (proc.stderr or "")[-1000:],
    }
  except Exception as e:
    return {"ok": False, "error": str(e)}


def recover_dos_panda(
  *,
  confirm: bool = False,
  serial: str = "",
  external: bool = False,
  internal: bool = False,
  build_firmware: bool = False,
) -> dict[str, Any]:
  """
  Flash F4 panda with panda/ firmware (not panda_tici).
  Requires confirm=true. Offroad recommended. Works without tools/recover_dos_panda.py.
  """
  listing = list_f4_pandas()
  fw = _fw_path()
  script = openpilot_root() / RECOVER_SCRIPT
  preview = {
    "firmware_path": str(fw),
    "firmware_exists": fw.is_file(),
    "f4_pandas": listing.get("f4_pandas", []),
    "recover_script_present": script.is_file(),
    "implementation": "inline (no script required)",
    "target": {
      "serial": serial or None,
      "external": external,
      "internal": internal,
      "default": "internal F4 preferred" if not (serial or external or internal) else None,
    },
    "build_firmware": build_firmware,
    "warnings": [
      "内置 DOS / 外接黑熊必须用 panda/board/obj/panda.bin.signed",
      "不要用 panda_tici 固件或 Panda.flash()（SUPPORTED_DEVICES 仅 H7）",
      "刷机后若 fork 有 rebuild_pandad_tici 则运行；否则 reboot",
    ],
  }

  if not confirm:
    return {"ok": True, "needs_confirmation": True, "preview": preview, "hint": "Set confirm=true to flash (offroad)."}

  if build_firmware and not fw.is_file():
    built = build_panda_firmware()
    if not built.get("ok"):
      return {"ok": False, "error": "firmware build failed", "build": built}

  if not fw.is_file():
    return {
      "ok": False,
      "error": f"missing firmware: {fw}",
      "hint": "Run with build_firmware=true or scons in panda/board first.",
    }

  result = execute_recover_dos_panda(
    serial=serial.strip(),
    external=external,
    internal=internal,
    try_dfu=True,
  )
  result["next_steps"] = [
    "rebuild_pandad_tici(confirm=true) if fork provides it",
    "reboot_device",
    "panda_status to verify",
  ]
  return result


def panda_recovery_hint(get_state_reader=None) -> dict[str, Any]:
  """Suggest recovery steps when pandaStates empty or sidebar shows NO PANDA."""
  listing = list_f4_pandas()
  live: list[Any] = []
  if get_state_reader is not None:
    try:
      reader = get_state_reader()
      reader.update(timeout=0)
      full = reader.latest()
      if isinstance(full, dict):
        live = full.get("pandaStates") or []
    except Exception:
      pass

  steps: list[str] = ["panda_status", "device_health", "grep_log pandad|panda|xhci"]
  if not live:
    steps.extend([
      "tsk_restart_pandad(confirm=true) — offroad",
      "若仍 NO PANDA：list_f4_pandas → recover_dos_panda(confirm=true)",
      "C3 内置：recover_dos_panda(internal=true)；外接 aux 黑熊：external=true",
      "无需 tools/recover_dos_panda.py，op 助手内联刷机",
    ])
  try:
    from ai.tsk.lib.panda_connect import tici_info

    info = tici_info()
    device_type = info.get("device_type")
    if device_type == "tici" and info.get("use_tici_panda_stack"):
      steps.append("C3 DOS：固件 panda/ 非 panda_tici；单内置走 DOS 快速路径不自动刷机")
  except Exception:
    pass

  return {
    "ok": True,
    "panda_states_count": len(live),
    "usb_f4": listing.get("f4_pandas", []),
    "firmware_exists": listing.get("firmware_exists"),
    "recover_script_present": listing.get("recover_script_present"),
    "recommended_steps": steps,
    "skill": "c3-dos-panda",
    "doc": "ai/docs/PANDA_FLASH.md",
  }
