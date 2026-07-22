"""Phase-2 API handlers — schema, device trust, canvas, queue."""

from __future__ import annotations

from aiohttp import web

from openpilot.common.params import Params

from ai.canvas.store import list_artifacts
from ai.command_queue import list_queued
from ai.device_trust import (
  check_device_trust,
  list_paired_devices,
  pair_device,
  revoke_device,
  touch_device,
)
from ai.sync_protocol import get_protocol_schema


async def api_sync_schema(_request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  return json_response({"ok": True, "schema": get_protocol_schema()})


async def api_device_trust(request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  params: Params = request.app.get("params") or Params()
  status = check_device_trust(request, params)
  touch_device(params, status["deviceId"], status.get("fingerprint", ""))
  return json_response({
    "ok": True,
    **status,
    "devices": list_paired_devices(params),
    "queue": list_queued(),
  })


async def api_device_pair(request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  params: Params = request.app.get("params") or Params()
  try:
    body = await request.json()
  except Exception:
    body = {}
  if not isinstance(body, dict):
    body = {}
  result = pair_device(
    params,
    device_id=str(body.get("deviceId") or body.get("device_id") or "").strip(),
    fingerprint=str(body.get("fingerprint") or "").strip(),
    label=str(body.get("label") or "").strip(),
    pin=str(body.get("pin") or "").strip(),
  )
  status = 200 if result.get("ok") else 400
  return json_response(result, status=status)


async def api_device_revoke(request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  params: Params = request.app.get("params") or Params()
  device_id = request.match_info.get("device_id", "")
  result = revoke_device(params, device_id)
  status = 200 if result.get("ok") else 404
  return json_response(result, status=status)


async def api_canvas(request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  session_id = str(request.query.get("sessionId") or request.query.get("session_id") or "").strip()
  limit = int(request.query.get("limit", "10") or "10")
  return json_response({
    "ok": True,
    "sessionId": session_id,
    "artifacts": list_artifacts(session_id, limit=min(limit, 50)),
  })


async def api_workspace(request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  from ai.workspace import list_workspace_files, read_workspace_file

  key = str(request.query.get("key") or "").strip()
  if key:
    return json_response({
      "ok": True,
      "key": key,
      "content": read_workspace_file(key),
    })
  return json_response({"ok": True, "files": list_workspace_files()})


async def api_workspace_write(request: web.Request) -> web.Response:
  from ai.server.deps import json_response
  from ai.workspace import write_workspace_file

  try:
    body = await request.json()
  except Exception:
    body = {}
  if not isinstance(body, dict):
    body = {}
  key = str(body.get("key") or "").strip()
  if not key:
    return json_response({"ok": False, "error": "key required"}, status=400)
  return json_response(write_workspace_file(key, str(body.get("content") or "")))


async def api_usage_detail(request: web.Request) -> web.Response:
  from ai.server.deps import json_response, params
  from ai.usage_log import load_usage

  p = request.app.get("params") or params()
  usage = load_usage(p)
  return json_response({
    "ok": True,
    "usage": usage,
    "byProvider": usage.get("by_provider") or {},
    "byModel": usage.get("by_model") or {},
    "recent": (usage.get("recent") or [])[-20:],
  })
