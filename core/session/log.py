"""Append-only session event log.

Inspired by dsh-session: the log is the single source of truth for model
history. Every model-visible fact is an event; UI and replay derive from it.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any



class EventType(StrEnum):
  TURN_START = "turn/start"
  TURN_END = "turn/end"
  STEP_START = "step/start"
  STEP_END = "step/end"
  USER_MESSAGE = "user/message"
  ASSISTANT_CHUNK = "assistant/chunk"
  ASSISTANT_MESSAGE = "assistant/message"
  TOOL_CALL = "tool/call"
  TOOL_RESULT = "tool/result"
  REQUEST_HEADER = "request/header"
  REQUEST_CONTEXT = "request/context"
  LIFECYCLE = "lifecycle"


class SurfaceOp(StrEnum):
  APPEND = "append"
  REPLACE = "replace"


class TurnEndKind(StrEnum):
  COMPLETED = "completed"
  ABORTED = "aborted"
  BLOCKED = "blocked"
  ERROR = "error"
  MAX_TOKENS = "max-tokens"


class CancelCauseKind(StrEnum):
  USER = "user"
  PARENT = "parent"
  HOOK = "hook"
  DISPOSED = "disposed"


@dataclass(frozen=True)
class CancelCause:
  kind: CancelCauseKind
  reason: str = ""

  def to_dict(self) -> dict[str, Any]:
    return {"kind": self.kind.value, "reason": self.reason}


@dataclass(frozen=True)
class RequestHeader:
  provider: str
  model: str
  system: str | None = None
  tools: list[dict[str, Any]] | None = None
  reasoning_effort: str | None = None
  max_tokens: int | None = None

  def to_dict(self) -> dict[str, Any]:
    out: dict[str, Any] = {"provider": self.provider, "model": self.model}
    if self.system is not None:
      out["system"] = self.system
    if self.tools is not None:
      out["tools"] = self.tools
    if self.reasoning_effort is not None:
      out["reasoningEffort"] = self.reasoning_effort
    if self.max_tokens is not None:
      out["maxTokens"] = self.max_tokens
    return out

  @staticmethod
  def from_dict(data: dict[str, Any]) -> RequestHeader:
    return RequestHeader(
      provider=str(data.get("provider", "")),
      model=str(data.get("model", "")),
      system=data.get("system"),
      tools=data.get("tools"),
      reasoning_effort=data.get("reasoningEffort"),
      max_tokens=data.get("maxTokens"),
    )

  def equals(self, other: RequestHeader) -> bool:
    return (
      self.provider == other.provider
      and self.model == other.model
      and self.system == other.system
      and _json_eq(self.tools, other.tools)
      and self.reasoning_effort == other.reasoning_effort
      and self.max_tokens == other.max_tokens
    )


def _json_eq(a: Any, b: Any) -> bool:
  return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def _lossless_json(value: Any) -> Any:
  """Return a deep copy if value is losslessly JSON-serializable, else raise."""
  # Use json round-trip as a cheap lossless check.
  try:
    return json.loads(json.dumps(value, default=_raise_non_json))
  except (TypeError, ValueError) as e:
    raise ValueError(f"value is not losslessly JSON-serializable: {e}") from e


def _raise_non_json(_obj: Any) -> None:
  raise TypeError("non-JSON-serializable value")


def _deep_freeze(value: Any) -> Any:
  if isinstance(value, dict):
    return type(value)((k, _deep_freeze(v)) for k, v in value.items())
  if isinstance(value, list):
    return type(value)(_deep_freeze(v) for v in value)
  if isinstance(value, tuple):
    return tuple(_deep_freeze(v) for v in value)
  return value


@dataclass(frozen=True)
class SessionEvent:
  type: EventType
  seq: int
  time: int
  data: Any
  surface_op: SurfaceOp | None = None
  source_seqs: tuple[int, ...] | None = None

  def to_dict(self) -> dict[str, Any]:
    out: dict[str, Any] = {
      "type": self.type.value,
      "seq": self.seq,
      "time": self.time,
      "data": self.data,
    }
    if self.surface_op is not None:
      out["surfaceOp"] = self.surface_op.value
    if self.source_seqs is not None:
      out["sourceEventSeqs"] = list(self.source_seqs)
    return out


@dataclass
class SurfaceNode:
  seq: int
  event_type: EventType
  data: Any


class SessionLog:
  """Append-only event log for one session.

  Events are kept in memory and optionally mirrored to a JSONL file.
  Loading from disk is opt-in so consumers that only need the current
  process history are not surprised by stale events.
  """

  def __init__(
    self,
    session_id: str,
    seed: list[SessionEvent] | None = None,
    *,
    persist_path: str | Path | None = None,
    load_persisted: bool = False,
  ) -> None:
    self.session_id = session_id
    self._events: list[SessionEvent] = []
    self._surface: list[SurfaceNode] = []
    self._header: RequestHeader | None = None
    self._context: dict[str, Any] | None = None
    self._persist_path = Path(persist_path) if persist_path else None
    self._persist_file: Any = None
    if load_persisted and self._persist_path is not None and self._persist_path.is_file():
      self._load_from_disk()
    if self._persist_path is not None:
      try:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_file = open(self._persist_path, "a", encoding="utf-8")
      except Exception:
        self._persist_file = None
    if seed:
      for ev in seed:
        self.append(ev.type, ev.data, surface_op=ev.surface_op, source_seqs=ev.source_seqs)

  @property
  def events(self) -> tuple[SessionEvent, ...]:
    return tuple(self._events)

  @property
  def persist_path(self) -> Path | None:
    return self._persist_path

  @property
  def surface(self) -> tuple[SurfaceNode, ...]:
    return tuple(self._surface)

  @property
  def seq(self) -> int:
    return len(self._events)

  def append(
    self,
    event_type: EventType,
    data: Any,
    *,
    surface_op: SurfaceOp | None = None,
    source_seqs: tuple[int, ...] | list[int] | None = None,
  ) -> SessionEvent:
    cleaned = _lossless_json(data)
    event = SessionEvent(
      type=event_type,
      seq=self.seq,
      time=int(time.monotonic() * 1000),
      data=_deep_freeze(cleaned),
      surface_op=surface_op,
      source_seqs=tuple(source_seqs) if source_seqs is not None else None,
    )
    self._events.append(event)
    if surface_op is not None:
      self._apply_surface(event)
    if event_type == EventType.REQUEST_HEADER:
      self._fold_header(cleaned)
    if event_type == EventType.REQUEST_CONTEXT:
      self._context = dict(cleaned)
    self._persist_event(event)
    return event

  def _persist_event(self, event: SessionEvent) -> None:
    if self._persist_file is None:
      return
    try:
      self._persist_file.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")
      self._persist_file.flush()
    except Exception:
      pass

  def _load_from_disk(self) -> None:
    if self._persist_path is None or not self._persist_path.is_file():
      return
    try:
      with open(self._persist_path, "r", encoding="utf-8") as f:
        for line in f:
          line = line.strip()
          if not line:
            continue
          data = json.loads(line)
          ev_type = EventType(data.get("type", ""))
          surface_op = data.get("surfaceOp")
          source_seqs = data.get("sourceEventSeqs")
          self.append(
            ev_type,
            data.get("data"),
            surface_op=SurfaceOp(surface_op) if surface_op else None,
            source_seqs=tuple(source_seqs) if isinstance(source_seqs, list) else None,
          )
    except Exception:
      pass

  def close(self) -> None:
    if self._persist_file is not None:
      try:
        self._persist_file.close()
      except Exception:
        pass
      self._persist_file = None

  def __del__(self) -> None:
    self.close()

  def _apply_surface(self, event: SessionEvent) -> None:
    if event.surface_op == SurfaceOp.APPEND:
      self._surface.append(SurfaceNode(seq=event.seq, event_type=event.type, data=event.data))
    elif event.surface_op == SurfaceOp.REPLACE:
      # Minimal replace support: caller is expected to provide range in data.
      start = event.data.get("start") if isinstance(event.data, dict) else None
      end = event.data.get("end") if isinstance(event.data, dict) else None
      if isinstance(start, int) and isinstance(end, int):
        self._surface[start:end + 1] = [SurfaceNode(seq=event.seq, event_type=event.type, data=event.data)]
      else:
        self._surface.append(SurfaceNode(seq=event.seq, event_type=event.type, data=event.data))

  def _fold_header(self, data: Any) -> None:
    header_data = data.get("header") if isinstance(data, dict) else data
    if not isinstance(header_data, dict):
      return
    candidate = RequestHeader.from_dict(header_data)
    if self._header is None or not self._header.equals(candidate):
      self._header = candidate

  def request_header(self) -> RequestHeader | None:
    return copy.deepcopy(self._header)

  def request_context(self) -> dict[str, Any] | None:
    return copy.deepcopy(self._context) if self._context else None

  def derive_messages(self) -> list[dict[str, Any]]:
    """Derive OpenAI-style message history from the surface."""
    messages: list[dict[str, Any]] = []
    for node in self._surface:
      if node.event_type == EventType.USER_MESSAGE:
        messages.append(_project_user(node.data))
      elif node.event_type == EventType.ASSISTANT_MESSAGE:
        messages.append(_project_assistant(node.data))
      elif node.event_type == EventType.TOOL_RESULT:
        messages.append(_project_tool_result(node.data))
    return messages

  def last_assistant(self) -> dict[str, Any] | None:
    for node in reversed(self._surface):
      if node.event_type == EventType.ASSISTANT_MESSAGE:
        return _project_assistant(node.data)
    return None


def _project_user(data: Any) -> dict[str, Any]:
  if isinstance(data, dict):
    return {"role": "user", "content": data.get("content", "")}
  return {"role": "user", "content": str(data)}


def _project_assistant(data: Any) -> dict[str, Any]:
  if not isinstance(data, dict):
    return {"role": "assistant", "content": str(data)}
  content = data.get("content", "")
  tool_calls = data.get("tool_calls")
  msg: dict[str, Any] = {"role": "assistant"}
  if content:
    msg["content"] = content
  if tool_calls:
    msg["tool_calls"] = tool_calls
  return msg


def _project_tool_result(data: Any) -> dict[str, Any]:
  if isinstance(data, dict):
    return {
      "role": "tool",
      "tool_call_id": data.get("tool_call_id", ""),
      "content": data.get("content", ""),
    }
  return {"role": "tool", "tool_call_id": "", "content": str(data)}


@dataclass
class SessionStore:
  """In-memory store of session logs. Disk persistence is handled by SessionLog."""

  _sessions: dict[str, SessionLog] = field(default_factory=dict)

  def get_or_create(
    self,
    session_id: str,
    seed: list[SessionEvent] | None = None,
    *,
    load_persisted: bool = False,
  ) -> SessionLog:
    if session_id not in self._sessions:
      self._sessions[session_id] = SessionLog(session_id, seed=seed, load_persisted=load_persisted)
    return self._sessions[session_id]

  def get(self, session_id: str) -> SessionLog | None:
    return self._sessions.get(session_id)

  def remove(self, session_id: str) -> None:
    self._sessions.pop(session_id, None)


_global_store: SessionStore | None = None


def get_session_store() -> SessionStore:
  global _global_store
  if _global_store is None:
    _global_store = SessionStore()
  return _global_store
