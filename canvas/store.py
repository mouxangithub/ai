"""Canvas artifacts — structured visual outputs per session."""

from __future__ import annotations

import time
import uuid
from typing import Any

_MAX_PER_SESSION = 20
_artifacts: dict[str, list[dict[str, Any]]] = {}


def _session_key(session_id: str) -> str:
  return session_id or "__global__"


def add_artifact(
  session_id: str,
  *,
  kind: str,
  title: str,
  payload: dict[str, Any] | None = None,
  source_tool: str = "",
) -> dict[str, Any]:
  key = _session_key(session_id)
  items = _artifacts.setdefault(key, [])
  artifact = {
    "id": f"art_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
    "kind": kind,
    "title": title,
    "payload": payload or {},
    "sourceTool": source_tool,
    "createdAt": int(time.time()),
  }
  items.append(artifact)
  if len(items) > _MAX_PER_SESSION:
    del items[: len(items) - _MAX_PER_SESSION]
  return artifact


def list_artifacts(session_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
  items = _artifacts.get(_session_key(session_id), [])
  return list(reversed(items[-limit:]))


def get_artifact(session_id: str, artifact_id: str) -> dict[str, Any] | None:
  for a in _artifacts.get(_session_key(session_id), []):
    if a.get("id") == artifact_id:
      return a
  return None


def maybe_capture_tool_artifact(
  session_id: str,
  tool_name: str,
  result: Any,
) -> dict[str, Any] | None:
  if not isinstance(result, dict):
    return None
  if result.get("canvas"):
    c = result["canvas"]
    if isinstance(c, dict):
      return add_artifact(
        session_id,
        kind=str(c.get("kind") or "report"),
        title=str(c.get("title") or tool_name),
        payload=c.get("payload") if isinstance(c.get("payload"), dict) else c,
        source_tool=tool_name,
      )
  for key, kind in (
    ("report", "report"),
    ("chart", "chart"),
    ("html", "html"),
    ("markdown", "markdown"),
    ("tune_passport", "tune"),
  ):
    if key in result and result[key]:
      title = str(result.get("title") or result.get("name") or tool_name)
      return add_artifact(
        session_id,
        kind=kind,
        title=title,
        payload={key: result[key], **{k: result[k] for k in ("summary", "metrics") if k in result}},
        source_tool=tool_name,
      )
  return None


async def notify_artifact(session_id: str, artifact: dict[str, Any]) -> None:
  try:
    from ai.sync_hub import notify_canvas_artifact
    await notify_canvas_artifact(session_id, artifact)
  except Exception:
    pass
