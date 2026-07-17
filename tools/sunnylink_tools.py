"""sunnypilot Sunnylink cloud backup / restore triggers."""

from __future__ import annotations

from typing import Any

from openpilot.common.params import Params

try:
  from openpilot.sunnypilot.sunnylink.api import UNREGISTERED_SUNNYLINK_DONGLE_ID
except Exception:
  UNREGISTERED_SUNNYLINK_DONGLE_ID = "unregistered"


def get_sunnylink_status(params: Params | None = None) -> dict[str, Any]:
  params = params or Params()
  sl_id = params.get("SunnylinkDongleId")
  if isinstance(sl_id, bytes):
    sl_id = sl_id.decode(errors="replace")
  sl_id = str(sl_id or UNREGISTERED_SUNNYLINK_DONGLE_ID)
  registered = sl_id not in (UNREGISTERED_SUNNYLINK_DONGLE_ID, "", "None")
  return {
    "ok": True,
    "SunnylinkEnabled": params.get_bool("SunnylinkEnabled") if params.get("SunnylinkEnabled") is not None else None,
    "EnableSunnylinkUploader": params.get_bool("EnableSunnylinkUploader") if params.get("EnableSunnylinkUploader") is not None else None,
    "SunnylinkDongleId": sl_id,
    "registered": registered,
    "SunnylinkTempFault": params.get_bool("SunnylinkTempFault") if params.get("SunnylinkTempFault") is not None else False,
    "CompletedSunnylinkConsentVersion": params.get("CompletedSunnylinkConsentVersion"),
    "backup_pending": bool(params.get_bool("BackupManager_CreateBackup")),
    "restore_version": params.get("BackupManager_RestoreVersion"),
    "hint": "Pair in UI Settings → Sunnylink; backup/restore via trigger_sunnylink_backup/restore (offroad).",
  }


def trigger_sunnylink_backup(params: Params) -> dict[str, Any]:
  if not params.get_bool("SunnylinkEnabled"):
    return {"ok": False, "error": "SunnylinkEnabled is off"}
  params.put_bool("BackupManager_CreateBackup", True)
  return {"ok": True, "hint": "Backup runs via backupManagerSP; poll cereal backupManagerSP or retry get_sunnylink_status."}


def trigger_sunnylink_restore(params: Params, version: str = "latest") -> dict[str, Any]:
  if not params.get_bool("SunnylinkEnabled"):
    return {"ok": False, "error": "SunnylinkEnabled is off"}
  params.put("BackupManager_RestoreVersion", version or "latest")
  return {"ok": True, "version": version or "latest", "hint": "Restore may restart UI when complete."}
