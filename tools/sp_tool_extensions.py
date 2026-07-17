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
  }
