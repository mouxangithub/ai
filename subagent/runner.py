"""Subagent runner — lightweight wrapper around ai.agents.orchestrator."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from ai.subagent.models import SubagentResult, SubagentStopReason, SubagentTask

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]
RunChatFn = Callable[..., Awaitable[dict[str, Any]]]


class SubagentRunner:
  """Runs one subagent task by delegating to the orchestrator chat loop."""

  def __init__(
    self,
    *,
    run_chat: RunChatFn | None = None,
    get_state_reader: Callable | None = None,
    get_tool_handlers: Callable | None = None,
    filter_tools: Callable | None = None,
  ) -> None:
    self.run_chat = run_chat
    self.get_state_reader = get_state_reader
    self.get_tool_handlers = get_tool_handlers
    self.filter_tools = filter_tools

  async def run(
    self,
    task: SubagentTask,
    *,
    params: Any,
    tools: list[dict[str, Any]] | None = None,
    max_tool_rounds: int = 24,
    emit: EmitFn | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    session_log_path: str | None = None,
  ) -> SubagentResult:
    events: list[dict[str, Any]] = []

    async def _emit(event: dict[str, Any]) -> None:
      events.append(event)
      if emit is not None:
        await emit(event)

    body = self._build_body(task)
    runner = self.run_chat

    try:
      if runner is None:
        from ai.agents.orchestrator import run_chat_with_agents
        result = await run_chat_with_agents(
          body,
          params,
          _emit,
          get_state_reader=self.get_state_reader,
          get_tool_handlers=self.get_tool_handlers,
          tools=tools,
          max_tool_rounds=max_tool_rounds,
          is_cancelled=is_cancelled,
          session_log_path=session_log_path,
        )
      else:
        result = await runner(
          body,
          params,
          emit=_emit,
          get_state_reader=self.get_state_reader,
          get_tool_handlers=self.get_tool_handlers,
          tools=tools,
          max_tool_rounds=max_tool_rounds,
          is_cancelled=is_cancelled,
          session_log_path=session_log_path,
        )
    except asyncio.CancelledError:
      return SubagentResult(
        task_id=task.id,
        ok=False,
        stop_reason="aborted",
        error="subagent cancelled",
        events=events,
      )
    except Exception as e:
      return SubagentResult(
        task_id=task.id,
        ok=False,
        stop_reason="error",
        error=str(e),
        events=events,
      )

    ok = bool(result.get("ok", False))
    output = self._extract_output(events)
    stop_reason: SubagentStopReason = "completed" if ok else "error"
    if not ok and any(e.get("type") == "error" and e.get("error") == "cancelled" for e in events):
      stop_reason = "aborted"

    return SubagentResult(
      task_id=task.id,
      ok=ok,
      output=output,
      structured=result.get("structured"),
      stop_reason=stop_reason,
      error=result.get("error", ""),
      events=events,
    )

  def _build_body(self, task: SubagentTask) -> dict[str, Any]:
    session_id = task.session_id or f"sub-{uuid.uuid4()}"
    messages: list[dict[str, Any]] = [{"role": "user", "content": task.prompt}]
    body: dict[str, Any] = {
      "sessionId": session_id,
      "messages": messages,
      "_subagent": True,
      "_subagent_task_id": task.id,
    }
    if task.workflow:
      body["workflow"] = task.workflow
    if task.agent_id:
      body["_agent_route"] = {
        "agent_id": task.agent_id,
        "agentId": task.agent_id,
        "workflow_id": task.workflow,
      }
    if task.output_schema is not None:
      body["output_schema"] = task.output_schema
    return body

  @staticmethod
  def _extract_output(events: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for event in events:
      if event.get("type") == "content":
        delta = event.get("delta") or ""
        if isinstance(delta, str):
          parts.append(delta)
    return "".join(parts).strip()


async def run_subagent(
  task: SubagentTask | dict[str, Any],
  *,
  params: Any,
  tools: list[dict[str, Any]] | None = None,
  max_tool_rounds: int = 24,
  emit: EmitFn | None = None,
  is_cancelled: Callable[[], bool] | None = None,
  session_log_path: str | None = None,
  runner: SubagentRunner | None = None,
) -> SubagentResult:
  if isinstance(task, dict):
    task = SubagentTask.from_dict(task)
  r = runner or SubagentRunner()
  return await r.run(
    task,
    params=params,
    tools=tools,
    max_tool_rounds=max_tool_rounds,
    emit=emit,
    is_cancelled=is_cancelled,
    session_log_path=session_log_path,
  )
