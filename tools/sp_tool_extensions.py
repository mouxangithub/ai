"""sunnypilot grouped settings + device/sunnylink tools (merged via extensions.py)."""

from __future__ import annotations

from typing import Any, Callable

SP_EXTENSION_TOOL_META: dict[str, dict[str, Any]] = {
  "get_torque_settings": {"label": "扭矩设置", "group": "read", "default_enabled": True, "driving": True},
  "set_torque_settings": {"label": "写入扭矩", "group": "write", "default_enabled": True, "driving": True},
  "get_lane_change_settings": {"label": "变道设置", "group": "read", "default_enabled": True, "driving": True},
  "set_lane_change_settings": {"label": "写入变道", "group": "write", "default_enabled": True, "driving": True},
  "get_speed_limit_settings": {"label": "限速设置", "group": "read", "default_enabled": True, "driving": True},
  "set_speed_limit_settings": {"label": "写入限速", "group": "write", "default_enabled": True, "driving": True},
  "list_visuals_settings": {"label": "视觉 HUD", "group": "read", "default_enabled": True, "driving": True},
  "set_visuals_settings": {"label": "写入视觉", "group": "write", "default_enabled": True, "driving": True},
  "get_sunnylink_status": {"label": "Sunnylink 状态", "group": "read", "default_enabled": True, "driving": True},
  "trigger_sunnylink_backup": {"label": "Sunnylink 备份", "group": "write", "default_enabled": True, "driving": False},
  "trigger_sunnylink_restore": {"label": "Sunnylink 恢复", "group": "write", "default_enabled": True, "driving": False},
  "get_sp_device_hw": {"label": "设备硬件", "group": "read", "default_enabled": True, "driving": True},
  "set_sp_dev_beep": {"label": "Lite 蜂鸣", "group": "write", "default_enabled": True, "driving": True},
  "get_model_tune_settings": {"label": "模型调参", "group": "read", "default_enabled": True, "driving": True},
  "set_model_tune_settings": {"label": "写入模型调参", "group": "write", "default_enabled": True, "driving": True},
  "get_display_settings": {"label": "显示设置", "group": "read", "default_enabled": True, "driving": True},
  "set_display_settings": {"label": "写入显示", "group": "write", "default_enabled": True, "driving": True},
  "get_device_settings": {"label": "设备设置", "group": "read", "default_enabled": True, "driving": True},
  "set_device_settings": {"label": "写入设备", "group": "write", "default_enabled": True, "driving": True},
  "list_sunnylink_backups": {"label": "Sunnylink 备份列表", "group": "read", "default_enabled": True, "driving": True},
  "get_backup_manager_status": {"label": "备份进程状态", "group": "read", "default_enabled": True, "driving": True},
  "list_f4_pandas": {"label": "F4 Panda 列表", "group": "read", "default_enabled": True, "driving": True},
  "list_all_pandas": {"label": "全部 Panda 列表", "group": "read", "default_enabled": True, "driving": True},
  "recover_dos_panda": {"label": "刷 DOS/黑熊固件", "group": "write", "default_enabled": True, "driving": False},
  "rebuild_pandad_tici": {"label": "重编 pandad_tici", "group": "write", "default_enabled": True, "driving": False},
  "panda_recovery_hint": {"label": "Panda 恢复建议", "group": "read", "default_enabled": True, "driving": True},
  "build_panda_firmware": {"label": "编译 panda 固件", "group": "write", "default_enabled": True, "driving": False, "pc_only": False},
  "github_runner_status": {"label": "GitHub Runner 状态", "group": "read", "default_enabled": True, "driving": True},
  "github_runner_recovery_hint": {"label": "Runner 排查建议", "group": "read", "default_enabled": True, "driving": True},
  "install_github_runner": {"label": "安装 GitHub Runner", "group": "write", "default_enabled": True, "driving": False},
}

SP_EXTENSION_SCHEMAS: list[dict[str, Any]] = [
  {"type": "function", "function": {"name": "get_torque_settings", "description": "Read LiveTorque / torque override params.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_torque_settings", "description": "Write torque-related params while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "get_lane_change_settings", "description": "Read AutoLaneChange timer and BSM delay.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_lane_change_settings", "description": "Write lane change params while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "get_speed_limit_settings", "description": "Read SpeedLimit* params.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_speed_limit_settings", "description": "Write speed limit params while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "list_visuals_settings", "description": "Read visuals/HUD toggle params.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_visuals_settings", "description": "Write visuals/HUD params while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "get_sunnylink_status", "description": "Sunnylink registration, backup/restore pending flags.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "trigger_sunnylink_backup", "description": "Queue Sunnylink cloud backup (offroad).", "parameters": {"type": "object", "properties": {"confirm": {"type": "boolean"}}, "required": ["confirm"]}}},
  {"type": "function", "function": {"name": "trigger_sunnylink_restore", "description": "Queue Sunnylink restore from version (offroad).", "parameters": {"type": "object", "properties": {"version": {"type": "string"}, "confirm": {"type": "boolean"}}, "required": ["confirm"]}}},
  {"type": "function", "function": {"name": "get_sp_device_hw", "description": "Lite variant, SpDevBeep, Panda count, board hints.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_sp_dev_beep", "description": "Enable SpDevBeep on Lite hardware (GPIO beepd).", "parameters": {"type": "object", "properties": {"enabled": {"type": "boolean"}, "confirm": {"type": "boolean"}}, "required": ["enabled", "confirm"]}}},
  {"type": "function", "function": {"name": "get_model_tune_settings", "description": "Read CameraOffset and PlanplusControl (modeld_v2).", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_model_tune_settings", "description": "Write CameraOffset / PlanplusControl while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "get_display_settings", "description": "Read display params (brightness, onroad screen off, interactivity).", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_display_settings", "description": "Write display params while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "get_device_settings", "description": "Read device params (max offroad, boot mode, quiet, developer toggles).", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "set_device_settings", "description": "Write device/developer service params while stationary.", "parameters": {"type": "object", "properties": {"params": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["params", "confirm"]}}},
  {"type": "function", "function": {"name": "list_sunnylink_backups", "description": "List Sunnylink cloud backups for this device.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "get_backup_manager_status", "description": "backupManagerSP progress and pending backup/restore flags.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "list_f4_pandas", "description": "List USB pandas; highlight F4 (black/DOS) and internal vs external. Read-only.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "list_all_pandas", "description": "List all USB pandas with hw_type/MCU, multi-panda scenario (e.g. F4+H7), and pandad process snapshot. Read-only.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "panda_recovery_hint", "description": "When sidebar NO PANDA or pandaStates empty: recommended tool sequence and doc links.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "build_panda_firmware", "description": "Offroad: scons panda/board to produce panda.bin.signed (F4 firmware, not panda_tici).", "parameters": {"type": "object", "properties": {"jobs": {"type": "integer"}}, "required": []}}},
  {"type": "function", "function": {"name": "recover_dos_panda", "description": "Offroad: flash F4 panda (C3 DOS internal or aux black panda) with panda/ firmware. Inline in ai — does NOT require tools/recover_dos_panda.py. NEVER use panda_tici firmware for F4. confirm=true required.", "parameters": {"type": "object", "properties": {"confirm": {"type": "boolean"}, "serial": {"type": "string"}, "external": {"type": "boolean", "description": "Flash first external F4 (aux black panda)"}, "internal": {"type": "boolean", "description": "Flash internal F4 (C3 DOS)"}, "build_firmware": {"type": "boolean", "description": "Run scons first if firmware missing"}}, "required": []}}},
  {"type": "function", "function": {"name": "rebuild_pandad_tici", "description": "Offroad: run tools/rebuild_pandad_tici.sh after git reset deleted pandad binary. confirm=true required.", "parameters": {"type": "object", "properties": {"confirm": {"type": "boolean"}}, "required": []}}},
  {"type": "function", "function": {"name": "github_runner_status", "description": "Read C3 GitHub Actions self-hosted runner: install paths, EnableGithubRunner gates, systemd service name/state. See ai/docs/GITHUB_RUNNER.md.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "github_runner_recovery_hint", "description": "When CI build is Pending or runner offline: recommended steps (params, systemd, install).", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "install_github_runner", "description": "Offroad: run release/ci/install_github_runner.sh on device. confirm=true and GitHub registration token required. Token never returned in logs.", "parameters": {"type": "object", "properties": {"token": {"type": "string"}, "repo_url": {"type": "string"}, "start_at_boot": {"type": "boolean"}, "confirm": {"type": "boolean"}}, "required": []}}},
]


def make_sp_extension_handlers(
  p,
  *,
  stationary_check: Callable[[str], dict[str, Any] | None],
  needs_confirm: Callable[[], bool],
  get_state_reader: Callable[[], Any] | None = None,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
  from ai.tools.write_pending import create_pending

  def _group_set(action: str, group: str, apply_fn):
    def handler(args):
      err = stationary_check("write_param")
      if err:
        return err
      writes = args.get("params") or {}
      if not isinstance(writes, dict):
        return {"ok": False, "error": "params must be an object"}
      if not args.get("confirm") and needs_confirm():
        from ai.tools.sp_tune_groups import preview_group_writes
        preview = preview_group_writes(p, writes, group)
        if not preview.get("ok", True):
          return preview
        return create_pending(p, action=action, payload={"params": writes}, preview=preview.get("changes", preview))
      return apply_fn(p, writes)
    return handler

  def _device_group_set(action: str, group: str, apply_fn):
    def handler(args):
      err = stationary_check("write_param")
      if err:
        return err
      writes = args.get("params") or {}
      if not isinstance(writes, dict):
        return {"ok": False, "error": "params must be an object"}
      if not args.get("confirm") and needs_confirm():
        from ai.tools.display_device_tools import preview_group_writes as dev_preview
        preview = dev_preview(p, writes, group)
        if not preview.get("ok", True):
          return preview
        return create_pending(p, action=action, payload={"params": writes}, preview=preview.get("changes", preview))
      return apply_fn(p, writes)
    return handler

  def _model_tune_set(args):
    err = stationary_check("write_param")
    if err:
      return err
    writes = args.get("params") or {}
    if not args.get("confirm") and needs_confirm():
      from ai.tools.model_tune_tools import preview_model_tune_writes
      preview = preview_model_tune_writes(p, writes)
      if not preview.get("ok", True):
        return preview
      return create_pending(p, action="set_model_tune_settings", payload={"params": writes}, preview=preview.get("changes", preview))
    from ai.tools.model_tune_tools import apply_model_tune_writes
    return apply_model_tune_writes(p, writes)

  def h_get_model_tune_settings(_a):
    from ai.tools.model_tune_tools import get_model_tune_settings
    return get_model_tune_settings(p)

  def h_get_display_settings(_a):
    from ai.tools.display_device_tools import get_display_settings
    return get_display_settings(p)

  def h_get_device_settings(_a):
    from ai.tools.display_device_tools import get_device_settings
    return get_device_settings(p)

  def h_list_sunnylink_backups(_a):
    from ai.tools.sunnylink_tools import list_sunnylink_backups
    return list_sunnylink_backups(p)

  def h_get_backup_manager_status(_a):
    from ai.tools.sunnylink_tools import get_backup_manager_status
    return get_backup_manager_status(get_state_reader=get_state_reader)

  def h_list_f4_pandas(_a):
    from ai.tools.panda_flash_tools import list_f4_pandas
    return list_f4_pandas()

  def h_list_all_pandas(_a):
    from ai.tools.panda_flash_tools import list_all_pandas
    return list_all_pandas()

  def h_panda_recovery_hint(_a):
    from ai.tools.panda_flash_tools import panda_recovery_hint
    return panda_recovery_hint(get_state_reader=get_state_reader)

  def h_build_panda_firmware(args):
    err = stationary_check("run_shell")
    if err:
      return err
    from ai.tools.panda_flash_tools import build_panda_firmware
    return build_panda_firmware(jobs=int(args.get("jobs", 4) or 4))

  def h_recover_dos_panda(args):
    err = stationary_check("run_shell")
    if err:
      return err
    from ai.tools.panda_flash_tools import recover_dos_panda
    return recover_dos_panda(
      confirm=bool(args.get("confirm")),
      serial=str(args.get("serial", "") or ""),
      external=bool(args.get("external")),
      internal=bool(args.get("internal")),
      build_firmware=bool(args.get("build_firmware")),
    )

  def h_rebuild_pandad_tici(args):
    err = stationary_check("run_shell")
    if err:
      return err
    from ai.tools.panda_flash_tools import rebuild_pandad_tici
    return rebuild_pandad_tici(confirm=bool(args.get("confirm")))

  def h_github_runner_status(_a):
    from ai.tools.github_runner_tools import github_runner_status
    return github_runner_status(p)

  def h_github_runner_recovery_hint(_a):
    from ai.tools.github_runner_tools import github_runner_recovery_hint
    return github_runner_recovery_hint(p, get_state_reader=get_state_reader)

  def h_install_github_runner(args):
    err = stationary_check("run_shell")
    if err:
      return err
    from ai.tools.github_runner_tools import install_github_runner_preview
    return install_github_runner_preview(
      token=str(args.get("token", "") or ""),
      repo_url=str(args.get("repo_url", "") or ""),
      start_at_boot=bool(args.get("start_at_boot")),
      confirm=bool(args.get("confirm")),
    )

  def h_get_torque_settings(_a):
    from ai.tools.sp_tune_groups import get_torque_settings
    return get_torque_settings(p)

  def h_get_lane_change_settings(_a):
    from ai.tools.sp_tune_groups import get_lane_change_settings
    return get_lane_change_settings(p)

  def h_get_speed_limit_settings(_a):
    from ai.tools.sp_tune_groups import get_speed_limit_settings
    return get_speed_limit_settings(p)

  def h_list_visuals_settings(_a):
    from ai.tools.sp_tune_groups import list_visuals_settings
    return list_visuals_settings(p)

  def h_get_sunnylink_status(_a):
    from ai.tools.sunnylink_tools import get_sunnylink_status
    return get_sunnylink_status(p)

  def h_get_sp_device_hw(_a):
    from ai.tools.device_hw_tools import get_sp_device_hw
    return get_sp_device_hw(p, get_state_reader=get_state_reader)

  def h_trigger_sunnylink_backup(args):
    err = stationary_check("write_param")
    if err:
      return err
    if not args.get("confirm") and needs_confirm():
      return {"ok": True, "needs_confirmation": True, "hint": "Set confirm=true to queue backup."}
    from ai.tools.sunnylink_tools import trigger_sunnylink_backup
    return trigger_sunnylink_backup(p)

  def h_trigger_sunnylink_restore(args):
    err = stationary_check("write_param")
    if err:
      return err
    version = str(args.get("version", "latest") or "latest")
    if not args.get("confirm") and needs_confirm():
      return {"ok": True, "needs_confirmation": True, "version": version, "hint": "Set confirm=true to queue restore."}
    from ai.tools.sunnylink_tools import trigger_sunnylink_restore
    return trigger_sunnylink_restore(p, version)

  def h_set_sp_dev_beep(args):
    err = stationary_check("write_param")
    if err:
      return err
    enabled = bool(args.get("enabled"))
    if not args.get("confirm") and needs_confirm():
      return {"ok": True, "needs_confirmation": True, "SpDevBeep": enabled}
    from ai.tools.device_hw_tools import set_sp_dev_beep
    return set_sp_dev_beep(p, enabled)

  from ai.tools.sp_tune_groups import (
    apply_lane_change_writes,
    apply_speed_limit_writes,
    apply_torque_writes,
    apply_visuals_writes,
  )

  from ai.tools.display_device_tools import apply_device_writes, apply_display_writes

  return {
    "get_torque_settings": h_get_torque_settings,
    "set_torque_settings": _group_set("set_torque_settings", "torque", apply_torque_writes),
    "get_lane_change_settings": h_get_lane_change_settings,
    "set_lane_change_settings": _group_set("set_lane_change_settings", "lane_change", apply_lane_change_writes),
    "get_speed_limit_settings": h_get_speed_limit_settings,
    "set_speed_limit_settings": _group_set("set_speed_limit_settings", "speed_limit", apply_speed_limit_writes),
    "list_visuals_settings": h_list_visuals_settings,
    "set_visuals_settings": _group_set("set_visuals_settings", "visuals", apply_visuals_writes),
    "get_sunnylink_status": h_get_sunnylink_status,
    "trigger_sunnylink_backup": h_trigger_sunnylink_backup,
    "trigger_sunnylink_restore": h_trigger_sunnylink_restore,
    "get_sp_device_hw": h_get_sp_device_hw,
    "set_sp_dev_beep": h_set_sp_dev_beep,
    "get_model_tune_settings": h_get_model_tune_settings,
    "set_model_tune_settings": _model_tune_set,
    "get_display_settings": h_get_display_settings,
    "set_display_settings": _device_group_set("set_display_settings", "display", apply_display_writes),
    "get_device_settings": h_get_device_settings,
    "set_device_settings": _device_group_set("set_device_settings", "device", apply_device_writes),
    "list_sunnylink_backups": h_list_sunnylink_backups,
    "get_backup_manager_status": h_get_backup_manager_status,
    "list_f4_pandas": h_list_f4_pandas,
    "list_all_pandas": h_list_all_pandas,
    "panda_recovery_hint": h_panda_recovery_hint,
    "build_panda_firmware": h_build_panda_firmware,
    "recover_dos_panda": h_recover_dos_panda,
    "rebuild_pandad_tici": h_rebuild_pandad_tici,
    "github_runner_status": h_github_runner_status,
    "github_runner_recovery_hint": h_github_runner_recovery_hint,
    "install_github_runner": h_install_github_runner,
  }
