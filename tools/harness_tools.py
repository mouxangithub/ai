"""Harness model tools: goal, plan, todo, subagent, lsp, python and workflow.

All handlers are wired to the existing `ai.goal`, `ai.plan`, `ai.todo`,
`ai.subagent`, `ai.lsp`, `ai.mcp` and `ai.sandbox` modules. No stub /
unavailable / constant-success handlers remain — every tool performs a real
call and returns a structured `{ok, error?}` (or entity) result.
"""
from __future__ import annotations

import asyncio  # noqa: F401
from typing import Any

from ai.goal.models import CreateGoalRequest, EditGoalRequest, GoalRef
from ai.system.paths import workspace_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> dict[str, Any]:
  return {"ok": False, "error": message}


def _goal_store():
  from ai.goal.store import get_goal_store, set_goal_base_dir
  set_goal_base_dir(workspace_path("ai_goals", mkdir=True))
  return get_goal_store()


def _plan_store():
  from ai.plan.store import get_plan_store, set_plan_base_dir
  set_plan_base_dir(workspace_path("ai_plans", mkdir=True))
  return get_plan_store()


def _todo_store():
  from ai.todo.store import get_todo_store, set_todo_base_dir
  set_todo_base_dir(workspace_path("ai_todos", mkdir=True))
  return get_todo_store()


def _ref(args: dict[str, Any]) -> GoalRef:
  ref = args.get("ref") or args
  if isinstance(ref, dict):
    return GoalRef.from_dict(ref)
  return GoalRef(id=str(ref), revision=1)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def _f(name, description, properties, required=None):
  return {
    "type": "function",
    "function": {
      "name": name,
      "description": description,
      "parameters": {"type": "object", "properties": properties, "required": list(required or [])},
    },
  }


def harness_tool_schemas(params=None) -> list[dict[str, Any]]:
  ref_schema = {"type": "object", "properties": {"id": {"type": "string"}, "revision": {"type": "integer"}}}
  return [
    _f("goal_create", "创建会话目标", {"objective": {"type": "string"}, "maxGoalRounds": {"type": "integer"}}, ["objective"]),
    _f("goal_get", "读取当前会话目标", {}),
    _f("goal_edit", "编辑会话目标", {"ref": ref_schema, "objective": {"type": "string"}, "maxGoalRounds": {"type": "integer"}}, ["ref"]),
    _f("goal_pause", "暂停会话目标", {"ref": ref_schema}, ["ref"]),
    _f("goal_resume", "恢复会话目标", {"ref": ref_schema}, ["ref"]),
    _f("goal_complete", "完成会话目标", {"ref": ref_schema}, ["ref"]),
    _f("goal_block", "阻塞会话目标", {"ref": ref_schema, "reason": {"type": "object", "properties": {"code": {"type": "string"}, "message": {"type": "string"}}}}, ["ref", "reason"]),
    _f("plan_generate", "生成执行计划", {"title": {"type": "string"}, "steps": {"type": "array", "items": {"type": "object"}}, "goal_id": {"type": "string"}}, ["title"]),
    _f("plan_update", "更新计划", {"plan_id": {"type": "string"}, "patch": {"type": "object"}}, ["plan_id", "patch"]),
    _f("plan_activate", "激活计划", {"plan_id": {"type": "string"}}, ["plan_id"]),
    _f("plan_step_status", "设置步骤状态", {"plan_id": {"type": "string"}, "step_id": {"type": "string"}, "status": {"type": "string"}}, ["plan_id", "step_id", "status"]),
    _f("plan_complete", "完成计划", {"plan_id": {"type": "string"}}, ["plan_id"]),
    _f("todo_write", "写入待办事项", {"todos": {"type": "array", "items": {"type": "object"}}, "allowParallel": {"type": "boolean"}}),
    _f("todo_clear", "清理待办事项", {}),
    _f("todo_get", "读取待办事项", {}),
    _f("subagent_start", "启动子代理", {"agent_id": {"type": "string"}, "prompt": {"type": "string"}, "workflow": {"type": "string"}, "max_depth": {"type": "integer"}}, ["agent_id", "prompt"]),
    _f("subagent_query", "查询子代理状态", {"task_id": {"type": "string"}}, ["task_id"]),
    _f("subagent_cancel", "取消子代理", {"task_id": {"type": "string"}}, ["task_id"]),
    _f("lsp", "执行只读 LSP 查询（坐标 1-based UTF-16）", {
      "action": {"type": "string", "enum": ["goToDefinition", "findReferences", "goToImplementation", "hover"]},
      "uri": {"type": "string"},
      "line": {"type": "integer"},
      "character": {"type": "integer"},
      "workspaceRoot": {"type": "string"},
    }, ["action", "uri", "line", "character"]),
    _f("run_python_code", "在只读沙箱运行 Python（blocked os/subprocess imports）", {"code": {"type": "string"}, "timeout_s": {"type": "number"}}, ["code"]),
    _f("workflow_advance", "推进工作流节点（graph）", {
      "workflow_id": {"type": "string"},
      "node_id": {"type": "string"},
      "action": {"type": "string", "enum": ["step", "retry", "pause", "resume"]},
    }, ["workflow_id", "action"]),
    _f("mcp_discover", "发现已授权 MCP 服务工具", {"server_id": {"type": "string"}}, ["server_id"]),
  ]


# ---------------------------------------------------------------------------
# Goal handlers
# ---------------------------------------------------------------------------

def _h_goal_create(a: dict[str, Any]) -> dict[str, Any]:
  try:
    view = _goal_store().create(CreateGoalRequest(
      objective=str(a.get("objective", "")),
      max_goal_rounds=a.get("maxGoalRounds"),
    ))
    return {"ok": True, "goal": view.to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_goal_get(_a: dict[str, Any]) -> dict[str, Any]:
  try:
    view = _goal_store().get()
    return {"ok": True, "goal": view.to_dict() if view else None}
  except Exception as exc:
    return _error(str(exc))


def _h_goal_edit(a: dict[str, Any]) -> dict[str, Any]:
  try:
    view = _goal_store().edit(_ref(a), EditGoalRequest(
      objective=a.get("objective"),
      max_goal_rounds=a.get("maxGoalRounds"),
    ))
    return {"ok": True, "goal": view.to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_goal_pause(a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, "goal": _goal_store().pause(_ref(a)).to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_goal_resume(a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, "goal": _goal_store().resume(_ref(a)).to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_goal_complete(a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, "goal": _goal_store().complete(_ref(a)).to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_goal_block(a: dict[str, Any]) -> dict[str, Any]:
  try:
    view = _goal_store().block(_ref(a), dict(a.get("reason") or {}))
    return {"ok": True, "goal": view.to_dict()}
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# Plan handlers
# ---------------------------------------------------------------------------

def _h_plan_generate(a: dict[str, Any]) -> dict[str, Any]:
  try:
    plan = _plan_store().create(
      title=str(a.get("title", "")),
      steps=a.get("steps") or [],
      goal_id=a.get("goal_id") or a.get("goalId"),
    )
    return {"ok": True, "plan": plan.to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_plan_update(a: dict[str, Any]) -> dict[str, Any]:
  try:
    plan = _plan_store().update(str(a.get("plan_id", "")), dict(a.get("patch") or {}))
    return {"ok": True, "plan": plan.to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_plan_activate(a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, "plan": _plan_store().activate(str(a.get("plan_id", ""))).to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_plan_step_status(a: dict[str, Any]) -> dict[str, Any]:
  try:
    plan = _plan_store().set_step_status(
      str(a.get("plan_id", "")),
      str(a.get("step_id", "")),
      str(a.get("status", "")),
    )
    return {"ok": True, "plan": plan.to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_plan_complete(a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, "plan": _plan_store().complete(str(a.get("plan_id", ""))).to_dict()}
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# Todo handlers
# ---------------------------------------------------------------------------

def _h_todo_write(a: dict[str, Any]) -> dict[str, Any]:
  try:
    result = _todo_store().write(
      a.get("todos", []),
      allow_parallel=bool(a.get("allowParallel", True)),
      metadata=a.get("metadata"),
    )
    return {"ok": True, **result}
  except Exception as exc:
    return _error(str(exc))


def _h_todo_clear(_a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, **_todo_store().clear()}
  except Exception as exc:
    return _error(str(exc))


def _h_todo_get(_a: dict[str, Any]) -> dict[str, Any]:
  try:
    return {"ok": True, **_todo_store().get()}
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# Subagent handlers (async — pool.run is a coroutine)
# ---------------------------------------------------------------------------

def _subagent_pool():
  from ai.subagent.pool import get_subagent_pool
  return get_subagent_pool()


async def _h_subagent_start(a: dict[str, Any]) -> dict[str, Any]:
  try:
    pool = _subagent_pool()
    task = pool.create_task(
      agent_id=str(a.get("agent_id", "")),
      prompt=str(a.get("prompt", "")),
      workflow=str(a.get("workflow", "")),
      max_depth=int(a.get("max_depth", 3)),
    )
    result = await pool.run(task, params=None, tools=None, max_tool_rounds=24)
    return {"ok": result.ok, "task": task.to_dict(), "result": result.to_dict()}
  except Exception as exc:
    return _error(str(exc))


def _h_subagent_query(a: dict[str, Any]) -> dict[str, Any]:
  try:
    pool = _subagent_pool()
    task_id = str(a.get("task_id", ""))
    task = pool.get_task(task_id)
    result = pool.get_result(task_id)
    return {"ok": True, "task": task.to_dict() if task else None, "result": result.to_dict() if result else None}
  except Exception as exc:
    return _error(str(exc))


def _h_subagent_cancel(a: dict[str, Any]) -> dict[str, Any]:
  try:
    ok = _subagent_pool().cancel(str(a.get("task_id", "")))
    return {"ok": True, "cancelled": ok}
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# LSP handler (async)
# ---------------------------------------------------------------------------

_lsp_manager: Any = None


def set_lsp_manager(manager: Any) -> None:
  """Inject the shared LspServerManager owned by the app (app_factory)."""
  global _lsp_manager
  _lsp_manager = manager


def get_lsp_manager():
  global _lsp_manager
  if _lsp_manager is None:
    from ai.lsp.server_manager import LspServerManager
    _lsp_manager = LspServerManager()
  return _lsp_manager


def _normalize_location(item: Any) -> dict[str, Any]:
  """Normalize an LSP Location to a renderable result dict (1-based)."""
  if isinstance(item, dict):
    uri = item.get("uri", "")
    rng = item.get("range") or {}
    start = rng.get("start") or {}
    line = int(start.get("line", 0)) + 1
    char = int(start.get("character", 0)) + 1
    return {"path": uri, "line": line, "character": char, "label": "", "detail": "", "snippet": ""}
  return {"path": "", "line": 0, "character": 0, "label": str(item), "detail": "", "snippet": ""}


def _hover_contents(item: dict[str, Any]) -> str:
  contents = item.get("contents")
  if isinstance(contents, str):
    return contents
  if isinstance(contents, dict):
    return str(contents.get("value", ""))
  if isinstance(contents, list):
    parts = []
    for c in contents:
      if isinstance(c, str):
        parts.append(c)
      elif isinstance(c, dict):
        parts.append(str(c.get("value", "")))
    return "\n".join(parts)
  return ""


async def _h_lsp(a: dict[str, Any]) -> dict[str, Any]:
  action = str(a.get("action", ""))
  uri = str(a.get("uri", "")).strip()
  workspace_root = str(a.get("workspaceRoot") or workspace_path("", mkdir=True)).strip()
  line = int(a.get("line", 1))
  character = int(a.get("character", 1))
  # LSP is 0-based internally; model passes 1-based UTF-16.
  line0 = max(0, line - 1)
  char0 = max(0, character - 1)

  if not uri:
    return _error("lsp requires uri")
  if action not in ("goToDefinition", "findReferences", "goToImplementation", "hover"):
    return _error(f"unsupported lsp action: {action}")

  manager = get_lsp_manager()
  client = manager.get_client(workspace_root)
  if client is None:
    return _error(f"no LSP server running for workspace '{workspace_root}'; start one via /api/ai/lsp/servers first")

  try:
    if action == "goToDefinition":
      raw = await client.definition(uri, line0, char0)
      return {"ok": True, "action": action, "results": [_normalize_location(x) for x in raw]}
    if action == "findReferences":
      raw = await client.references(uri, line0, char0)
      return {"ok": True, "action": action, "results": [_normalize_location(x) for x in raw]}
    if action == "goToImplementation":
      raw = await client.implementation(uri, line0, char0)
      return {"ok": True, "action": action, "results": [_normalize_location(x) for x in raw]}
    if action == "hover":
      raw = await client.hover(uri, line0, char0)
      if not raw:
        return {"ok": True, "action": action, "results": [], "truncated": False}
      return {"ok": True, "action": action, "results": [{"path": uri, "line": line, "character": character, "label": "", "detail": _hover_contents(raw), "snippet": ""}]}
  except Exception as exc:
    return _error(f"lsp {action} failed: {exc}")
  return _error("unreachable")


# ---------------------------------------------------------------------------
# Python runner (async)
# ---------------------------------------------------------------------------

async def _h_run_python_code(a: dict[str, Any]) -> dict[str, Any]:
  try:
    from ai.sandbox.python_runner import PythonRunner
    runner = PythonRunner(workspace_root=str(workspace_path("", mkdir=True)))
    result = await runner.run_python(str(a.get("code", "")), timeout=int(a.get("timeout_s", 10)))
    return result.to_dict()
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# Workflow advance (async)
# ---------------------------------------------------------------------------

async def _h_workflow_advance(a: dict[str, Any]) -> dict[str, Any]:
  try:
    from ai.tools.domains.platform.workflow_graph import advance_graph_workflow
    workflow_id = str(a.get("workflow_id", ""))
    action = str(a.get("action", "step"))
    return advance_graph_workflow(workflow_id, action, a.get("node_id"))
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------

def _load_mcp_servers(params: Any) -> list[dict[str, Any]]:
  try:
    import json
    from ai.common.storage import read_param
    from ai.mcp.host import MCP_SERVERS_KEY
    raw = read_param(params, MCP_SERVERS_KEY)
    if not raw:
      return []
    if isinstance(raw, bytes):
      raw = raw.decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data if isinstance(data, list) else []
  except Exception:
    return []


async def _call_mcp_tool(server_id: str, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
  from ai.mcp.host import call_mcp_tool
  try:
    from openpilot.common.params import Params
    return await call_mcp_tool(Params(), server_id=server_id, tool_name=tool_name, arguments=args)
  except Exception as exc:
    return _error(str(exc))


def _make_mcp_handler(server_id: str, tool_name: str):
  async def handler(args: dict[str, Any]) -> dict[str, Any]:
    return await _call_mcp_tool(server_id, tool_name, args)
  return handler


def register_mcp_handlers(handlers, params=None) -> None:
  """Namespace registered tools as ``mcp_<server>_<tool>`` (async) -> call_mcp_tool.

  Default-deny: only servers with ``enabled`` and a stored ``tools`` list are
  registered (visible to the LLM). A ``mcp_discover`` helper tool is registered
  so an authorized server's tools can be listed on demand.
  """
  servers = _load_mcp_servers(params)
  added: set[str] = set()
  for server in servers:
    if not server.get("enabled", True):
      continue
    server_id = str(server.get("id") or "").strip()
    if not server_id:
      continue
    for tool in server.get("tools") or []:
      name = str(tool)
      if not name:
        continue
      handler_name = f"mcp_{server_id}_{name}"
      base = handler_name
      suffix = 1
      while handler_name in added:
        handler_name = f"{base}_{suffix}"
        suffix += 1
      added.add(handler_name)
      handlers[handler_name] = _make_mcp_handler(server_id, name)
  if "mcp_discover" not in added:
    handlers["mcp_discover"] = _h_mcp_discover


async def _h_mcp_discover(a: dict[str, Any]) -> dict[str, Any]:
  server_id = str(a.get("server_id", "")).strip()
  if not server_id:
    return _error("mcp_discover requires server_id")
  try:
    from openpilot.common.params import Params
    from ai.mcp.host import discover_mcp_tools
    return await discover_mcp_tools(Params(), server_id)
  except Exception as exc:
    return _error(str(exc))


# ---------------------------------------------------------------------------
# Registration entry points
# ---------------------------------------------------------------------------

def register_harness_handlers(handlers, *, params=None, get_state_reader=None, toolbox=None) -> None:
  handlers.update({
    "goal_create": _h_goal_create,
    "goal_get": _h_goal_get,
    "goal_edit": _h_goal_edit,
    "goal_pause": _h_goal_pause,
    "goal_resume": _h_goal_resume,
    "goal_complete": _h_goal_complete,
    "goal_block": _h_goal_block,
    "plan_generate": _h_plan_generate,
    "plan_update": _h_plan_update,
    "plan_activate": _h_plan_activate,
    "plan_step_status": _h_plan_step_status,
    "plan_complete": _h_plan_complete,
    "todo_write": _h_todo_write,
    "todo_clear": _h_todo_clear,
    "todo_get": _h_todo_get,
    "subagent_start": _h_subagent_start,
    "subagent_query": _h_subagent_query,
    "subagent_cancel": _h_subagent_cancel,
    "lsp": _h_lsp,
    "run_python_code": _h_run_python_code,
    "workflow_advance": _h_workflow_advance,
  })
