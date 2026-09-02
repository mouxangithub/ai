"""Agent loop over session event log.

This module drives one session through turn and step boundaries, using
AgentState for lifecycle/cancellation and SessionLog as the durable source
of truth. It emits events compatible with the existing SSE protocol.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ai.core.agent.state import AgentState, CancelCause, CancelCauseKind, ChatCancelled, InboxTarget
from ai.core.session.log import EventType, RequestHeader, SessionLog, SurfaceOp
from ai.core.tools.pipeline import ToolPipeline

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]
StreamFn = Callable[..., Any]


class AgentLoop:
  """Drives one session with explicit turn/step boundaries and event logging."""

  def __init__(
    self,
    session_id: str,
    agent_id: str,
    params: Any,
    emit: EmitFn,
    stream_fn: StreamFn,
    tool_pipeline: ToolPipeline,
    *,
    max_tool_rounds: int = 64,
    tool_timeout: float = 300.0,
    stream_timeout: float = 120.0,
  ) -> None:
    self.session_id = session_id
    self.agent_id = agent_id
    self.params = params
    self.emit = emit
    self.stream_fn = stream_fn
    self.tool_pipeline = tool_pipeline
    self.max_tool_rounds = max_tool_rounds
    self.tool_timeout = tool_timeout
    self.stream_timeout = stream_timeout
    self.state = AgentState(agent_id, session_id)
    self.log = SessionLog(session_id)
    self._driver_task: asyncio.Task[Any] | None = None

  def _check_cancel(self) -> None:
    if self.state.is_cancelled():
      cause = self.state.cancel_cause() or CancelCause(CancelCauseKind.USER)
      raise ChatCancelled(cause)

  async def emit_event(self, event: dict[str, Any]) -> None:
    await self.emit(event)

  async def add_user_message(self, content: str, *, wakeup: bool = True) -> None:
    from ai.core.agent.state import AgentMessage
    self.state.followup(AgentMessage(role="user", content=content, source="user"))
    if wakeup:
      self._drive_if_idle()

  def _drive_if_idle(self) -> None:
    if self.state.phase.kind == "idle":
      self._driver_task = asyncio.create_task(self._run())

  async def _run(self) -> dict[str, Any]:
    self.state.begin_activity()
    try:
      while await self._turn():
        pass
      return {"ok": True, "agentId": self.agent_id}
    except ChatCancelled:
      return {"ok": False, "error": "cancelled"}
    except Exception as e:
      await self.emit_event({"type": "error", "error": str(e)})
      return {"ok": False, "error": str(e)}
    finally:
      self.state.end_activity()

  async def _turn(self) -> bool:
    if self.state.phase.kind != "running":
      return False
    phase = self.state.phase.running
    turn = phase.turn + 1
    phase.turn = turn
    phase.step = 0
    self.log.append(EventType.TURN_START, {"turn": turn})
    turn_end_reason = {"kind": "completed"}

    try:
      target = InboxTarget.NEXT_TURN
      while True:
        self._check_cancel()
        step = phase.step + 1
        claimed = self.state.inbox.claim(target, turn)
        if step == 1 and not claimed:
          turn_end_reason = {"kind": "completed"}
          break
        if not claimed:
          break

        self.log.append(EventType.STEP_START, {"turn": turn, "step": step})
        phase.step = step
        for msg in claimed:
          self.log.append(
            EventType.USER_MESSAGE,
            {"role": msg.role, "content": msg.content},
            surface_op=SurfaceOp.APPEND,
          )

        step_end = await self._step(turn, step)
        self.log.append(EventType.STEP_END, {"turn": turn, "step": step})

        if step_end == "max-tokens":
          turn_end_reason = {"kind": "max-tokens"}
        elif step_end == "completed" and turn_end_reason.get("kind") != "max-tokens":
          turn_end_reason = {"kind": "completed"}

        if step_end == "completed" and not self.state.inbox.has_pending:
          break
        target = InboxTarget.NEXT_STEP
    except ChatCancelled as cc:
      turn_end_reason = {"kind": "aborted", "reason": cc.cause.to_dict()}
      raise
    except Exception as e:
      turn_end_reason = {"kind": "error", "error": str(e)}
      await self.emit_event({"type": "error", "error": str(e)})
    finally:
      self.log.append(EventType.TURN_END, {"turn": turn, "reason": turn_end_reason})

    if not self.state.inbox.has_pending:
      return False
    # reset abort for next turn
    phase.abort = asyncio.get_event_loop().create_future()
    return True

  async def _step(self, turn: int, step: int) -> str:
    messages = self.log.derive_messages()
    header = self.log.request_header()
    if header is None:
      raise RuntimeError("no request header configured")

    request: dict[str, Any] = {
      "provider": header.provider,
      "model": header.model,
      "messages": messages,
    }
    if header.system is not None:
      request["system"] = header.system
    if header.tools:
      request["tools"] = header.tools

    pending_tool_calls: dict[int, dict[str, Any]] = {}
    assistant_content = ""
    assistant_reasoning = ""

    try:
      async for chunk in self._stream_with_timeout(request):
        self._check_cancel()
        if chunk.error:
          await self.emit_event({"type": "error", "error": chunk.error})
          return "error"
        if chunk.done:
          break
        if chunk.reasoning_content:
          assistant_reasoning += chunk.reasoning_content
          await self.emit_event({"type": "reasoning", "delta": chunk.reasoning_content})
        if chunk.content:
          assistant_content += chunk.content
          await self.emit_event({"type": "content", "delta": chunk.content})
        if chunk.tool_calls:
          for tc in chunk.tool_calls:
            idx = tc.get("index", 0)
            pending_tool_calls.setdefault(idx, {
              "id": tc.get("id", ""),
              "type": tc.get("type", "function"),
              "function": {"name": "", "arguments": ""},
            })
            fn = tc.get("function", {}) or {}
            pending_tool_calls[idx]["function"]["name"] += fn.get("name", "")
            pending_tool_calls[idx]["function"]["arguments"] += fn.get("arguments", "")
            await self.emit_event({"type": "tool_call_delta", "delta": tc})
    except TimeoutError as e:
      await self.emit_event({"type": "error", "error": f"Stream timeout: {e}"})
      return "error"

    tool_calls = [pending_tool_calls[i] for i in sorted(pending_tool_calls.keys())]
    self.log.append(
      EventType.ASSISTANT_MESSAGE,
      {
        "role": "assistant",
        "content": assistant_content,
        "tool_calls": tool_calls,
      },
      surface_op=SurfaceOp.APPEND,
    )

    if not tool_calls:
      return "completed"

    for tc in tool_calls:
      self._check_cancel()
      fn = tc.get("function", {})
      name = fn.get("name", "")
      arguments = fn.get("arguments", "")
      call_id = tc.get("id", f"{name}:{turn}:{step}")
      await self.emit_event({
        "type": "tool_call",
        "id": call_id,
        "name": name,
        "arguments": arguments,
        "agentId": self.agent_id,
      })
      self.log.append(EventType.TOOL_CALL, {"turn": turn, "step": step, "callId": call_id, "name": name, "arguments": arguments})

      result = await self.tool_pipeline.execute(
        call_id=call_id,
        name=name,
        raw_arguments=arguments,
        is_cancelled=self.state.is_cancelled,
        timeout_seconds=self.tool_timeout,
      )

      await self.emit_event({
        "type": "tool_result",
        "id": call_id,
        "name": name,
        "result": result,
        "agentId": self.agent_id,
      })
      self.log.append(
        EventType.TOOL_RESULT,
        {
          "turn": turn,
          "step": step,
          "tool_call_id": call_id,
          "content": json.dumps(result, ensure_ascii=False, default=str),
        },
        surface_op=SurfaceOp.APPEND,
      )

    return "completed"

  async def _stream_with_timeout(self, request: dict[str, Any]) -> Any:
    # stream_fn is expected to return an async iterator.
    iterator = self.stream_fn(request, self.params)
    if hasattr(iterator, "__aiter__"):
      iterator = iterator.__aiter__()
    while True:
      try:
        item = await asyncio.wait_for(iterator.__anext__(), timeout=self.stream_timeout)
      except StopAsyncIteration:
        break
      yield item

  def configure_request(
    self,
    provider: str,
    model: str,
    system: str | None = None,
    tools: list[dict[str, Any]] | None = None,
  ) -> None:
    header = RequestHeader(provider=provider, model=model, system=system, tools=tools)
    self.log.append(EventType.REQUEST_HEADER, {"header": header.to_dict(), "reason": "initial"})

  def cancel(self, kind: CancelCauseKind = CancelCauseKind.USER, reason: str = "") -> None:
    self.state.cancel(CancelCause(kind, reason))


