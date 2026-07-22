"""OpenClaw-style heartbeat — periodic checklist from HEARTBEAT.md."""

from __future__ import annotations

from typing import Any

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

from ai.workspace import heartbeat_checklist


async def run_heartbeat(params: Params, *, get_state_reader) -> dict[str, Any]:
  """Evaluate HEARTBEAT.md checklist; enqueue notifications when needed."""
  checklist = heartbeat_checklist()
  if not checklist:
    return {"ok": True, "skipped": True, "reason": "empty checklist"}

  state = get_state_reader().update(timeout=0)
  actions: list[str] = []

  try:
    from ai.tools.notifications import list_notifications, push_notification
    unread = list_notifications(unread_only=True).get("notifications", [])
    if unread:
      actions.append(f"unread_notifications={len(unread)}")
      if len(unread) >= 3:
        push_notification(
          "Heartbeat",
          f"有 {len(unread)} 条未读通知待处理",
          level="info",
        )
  except Exception as e:
    cloudlog.debug(f"aid: heartbeat notifications: {e}")

  if not state.is_driving:
    actions.append("vehicle_stopped")
  else:
    actions.append("vehicle_driving")

  cloudlog.info(f"aid: heartbeat tick driving={state.is_driving} actions={actions}")
  return {
    "ok": True,
    "driving": state.is_driving,
    "checklistChars": len(checklist),
    "actions": actions,
  }
