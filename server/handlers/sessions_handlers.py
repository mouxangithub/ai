"""API handlers — sessions."""

from ai.server.handlers._api_common import *  # noqa: F403
from ai.server.handlers.chat_handlers import _session_log_path

async def api_sessions(request: web.Request) -> web.Response:
  if request.method == "GET":
    session_id = (request.query.get("session_id") or request.query.get("session") or "").strip()
    compact = request.query.get("compact", "1") in ("1", "true", "yes")
    loop = asyncio.get_running_loop()
    from ai.server.thread_pools import io_executor
    from ai.tools.session_store import get_session_by_id, get_sessions

    pool = io_executor()
    if session_id:
      result = await loop.run_in_executor(pool, lambda: get_session_by_id(_PARAMS, session_id))
      return _json_response(result)
    result = await loop.run_in_executor(pool, lambda: get_sessions(_PARAMS, compact=compact))
    return _json_response(result)
  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON"}, status=400)
  result = save_sessions(_PARAMS, body)
  try:
    await broadcast_sessions(_PARAMS)
  except Exception as e:
    cloudlog.warning(f"aid: broadcast_sessions failed: {e}")
  return _json_response(result)

async def api_pc_sessions(request: web.Request) -> web.Response:
  try:
    from ai.tools.pc_dev_tools import pc_list_tool_sessions
    return _json_response(pc_list_tool_sessions(limit=int(request.query.get("limit", "20"))))
  except Exception as e:
    return _json_response({"ok": False, "error": str(e)})


async def api_session_log(request: web.Request) -> web.Response:
  """GET /api/ai/sessions/{session_id}/log - return durable session event log."""
  session_id = request.match_info.get("session_id", "").strip()
  if not session_id:
    return _json_response({"ok": False, "error": "session_id required"}, status=400)
  log_path = _session_log_path(session_id)
  events: list[dict[str, Any]] = []
  if log_path and os.path.isfile(log_path):
    try:
      with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
          line = line.strip()
          if not line:
            continue
          try:
            events.append(json.loads(line))
          except json.JSONDecodeError:
            continue
    except Exception as e:
      return _json_response({"ok": False, "error": f"Failed to read log: {e}"}, status=500)
  return _json_response({"ok": True, "sessionId": session_id, "events": events})


async def api_session_repair(request: web.Request) -> web.Response:
  """POST /api/ai/sessions/{id}/repair - deterministic repair of a corrupt log tail."""
  session_id = request.match_info.get("session_id", "").strip()
  if not session_id:
    return _json_response({"ok": False, "error": "session_id required"}, status=400)
  try:
    from ai.tools.domains.platform.transcript_store import recover_partial
    return _json_response(recover_partial(session_id))
  except Exception as e:
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_session_resume(request: web.Request) -> web.Response:
  """POST /api/ai/sessions/{id}/resume - replay persisted events to rebuild context."""
  session_id = request.match_info.get("session_id", "").strip()
  if not session_id:
    return _json_response({"ok": False, "error": "session_id required"}, status=400)
  log_path = _session_log_path(session_id)
  if not log_path or not os.path.isfile(log_path):
    return _json_response({"ok": False, "error": "no persisted log for session"}, status=404)
  try:
    from ai.core.session.log import SessionLog
    log = SessionLog(session_id, persist_path=log_path, load_persisted=True)
    replayed = len(log.events)
    # Reconstruct durable goal/plan/todo refs from the surface/events.
    reconstructed = {"goal": None, "plan": None, "todo": None}
    interrupted = []
    call_ids: set[str] = set()
    result_ids: set[str] = set()
    for ev in log.events:
      data = ev.data or {}
      if ev.type.value == "tool/call":
        cid = data.get("callId") if isinstance(data, dict) else None
        if cid:
          call_ids.add(str(cid))
      elif ev.type.value == "tool/result":
        cid = data.get("tool_call_id") if isinstance(data, dict) else None
        if cid:
          result_ids.add(str(cid))
    interrupted = sorted(call_ids - result_ids)
    log.close()
    return _json_response({
      "ok": True,
      "sessionId": session_id,
      "replayedEvents": replayed,
      "reconstructed": reconstructed,
      "interrupted": interrupted,
      "repaired": [],
    })
  except Exception as e:
    return _json_response({"ok": False, "error": str(e)}, status=500)
