"""Platform extensions — sessions, MCP, learned skills, user profile, toolsets."""

from __future__ import annotations

from typing import Any, Callable

from openpilot.common.params import Params

from ai.mcp.host import call_mcp_tool, discover_mcp_tools, list_mcp_servers, upsert_mcp_server
from ai.tools.session_index import (
  get_session_history,
  list_sessions_brief,
  rebuild_from_params,
  search_sessions,
)
from ai.tools.skill_learning import approve_learned_skill, list_learned_skills, propose_learned_skill
from ai.tools.toolsets import list_toolsets
from ai.tools.memory_store import get_memory, append_note
from ai.workspace import read_workspace_file, write_workspace_file

PLATFORM_TOOL_META: dict[str, dict[str, Any]] = {
  "sessions_list": {"label": "会话列表", "group": "read", "default_enabled": True, "driving": True},
  "sessions_history": {"label": "会话历史", "group": "read", "default_enabled": True, "driving": True},
  "sessions_send": {"label": "跨会话投递", "group": "write", "default_enabled": True, "driving": True},
  "search_past_conversations": {"label": "搜索历史对话", "group": "read", "default_enabled": True, "driving": True},
  "reindex_session_search": {"label": "重建会话索引", "group": "config", "default_enabled": True, "driving": True},
  "list_toolsets": {"label": "工具集列表", "group": "read", "default_enabled": True, "driving": True},
  "list_mcp_servers": {"label": "MCP 服务列表", "group": "read", "default_enabled": True, "driving": True},
  "manage_mcp_server": {"label": "管理 MCP 服务", "group": "config", "default_enabled": True, "driving": True},
  "call_mcp_tool": {"label": "调用 MCP 工具", "group": "read", "default_enabled": True, "driving": True},
  "discover_mcp_tools": {"label": "发现 MCP 工具", "group": "read", "default_enabled": True, "driving": True},
  "list_learned_skills": {"label": "已学技能列表", "group": "read", "default_enabled": True, "driving": True},
  "propose_learned_skill": {"label": "提议新技能", "group": "memory", "default_enabled": True, "driving": True},
  "approve_learned_skill": {"label": "批准技能", "group": "config", "default_enabled": True, "driving": True},
  "get_user_profile": {"label": "用户画像", "group": "read", "default_enabled": True, "driving": True},
  "update_user_profile": {"label": "更新用户画像", "group": "memory", "default_enabled": True, "driving": True},
}

PLATFORM_SCHEMAS: list[dict[str, Any]] = [
  {"type": "function", "function": {"name": "sessions_list", "description": "List recent chat sessions with id, title, message count.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []}}},
  {"type": "function", "function": {"name": "sessions_history", "description": "Read message history for a session id.", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["session_id"]}}},
  {"type": "function", "function": {"name": "sessions_send", "description": "Append a note to another session as assistant context (stored in memory + notification).", "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["session_id", "message"]}}},
  {"type": "function", "function": {"name": "search_past_conversations", "description": "Full-text search across past chat sessions.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}},
  {"type": "function", "function": {"name": "reindex_session_search", "description": "Rebuild FTS index from device session store.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "list_toolsets", "description": "List available toolset groups (driving_readonly, offroad_full, etc.).", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "list_mcp_servers", "description": "List configured MCP server bridges.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "manage_mcp_server", "description": "Add or update an MCP stdio server config.", "parameters": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "command": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "enabled": {"type": "boolean"}}, "required": ["id", "command"]}}},
  {"type": "function", "function": {"name": "discover_mcp_tools", "description": "Call MCP tools/list for a server and cache tool names.", "parameters": {"type": "object", "properties": {"server_id": {"type": "string"}}, "required": ["server_id"]}}},
  {"type": "function", "function": {"name": "call_mcp_tool", "description": "Invoke a tool on a configured MCP server.", "parameters": {"type": "object", "properties": {"server_id": {"type": "string"}, "tool_name": {"type": "string"}, "arguments": {"type": "object"}}, "required": ["server_id", "tool_name"]}}},
  {"type": "function", "function": {"name": "list_learned_skills", "description": "List agent-proposed learned skills.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "propose_learned_skill", "description": "Save a reusable skill draft from a completed workflow.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "body"]}}},
  {"type": "function", "function": {"name": "approve_learned_skill", "description": "Approve a pending learned skill for future prompts.", "parameters": {"type": "object", "properties": {"skill_id": {"type": "string"}}, "required": ["skill_id"]}}},
  {"type": "function", "function": {"name": "get_user_profile", "description": "Read USER.md profile and vehicle profile.", "parameters": {"type": "object", "properties": {}, "required": []}}},
  {"type": "function", "function": {"name": "update_user_profile", "description": "Update USER.md preferences text.", "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "append": {"type": "boolean"}}, "required": ["content"]}}},
]


def make_platform_handlers(
  *,
  params: Params,
) -> dict[str, Callable[..., Any]]:
  p = params

  def h_sessions_list(args: dict[str, Any]) -> dict[str, Any]:
    return list_sessions_brief(p, limit=int(args.get("limit") or 20))

  def h_sessions_history(args: dict[str, Any]) -> dict[str, Any]:
    return get_session_history(p, str(args.get("session_id") or ""), limit=int(args.get("limit") or 40))

  def h_sessions_send(args: dict[str, Any]) -> dict[str, Any]:
    sid = str(args.get("session_id") or "")
    msg = str(args.get("message") or "").strip()
    if not sid or not msg:
      return {"ok": False, "error": "session_id and message required"}
    append_note(p, f"[会话 {sid[:8]}] {msg}", tags=["sessions_send", f"session:{sid[:12]}"])
    try:
      from ai.tools.notifications import push_notification
      push_notification("跨会话消息", msg[:200], level="info")
    except Exception:
      pass
    return {"ok": True, "sessionId": sid, "delivered": "memory+notification"}

  def h_search_past(args: dict[str, Any]) -> dict[str, Any]:
    return search_sessions(str(args.get("query") or ""), limit=int(args.get("limit") or 8))

  def h_reindex_sessions(_a: dict[str, Any]) -> dict[str, Any]:
    return rebuild_from_params(p)

  def h_list_toolsets(_a: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "toolsets": list_toolsets()}

  def h_list_mcp(_a: dict[str, Any]) -> dict[str, Any]:
    return list_mcp_servers(p)

  def h_manage_mcp(args: dict[str, Any]) -> dict[str, Any]:
    return upsert_mcp_server(p, args)

  async def h_discover_mcp(args: dict[str, Any]) -> dict[str, Any]:
    return await discover_mcp_tools(p, str(args.get("server_id") or ""))

  async def h_call_mcp(args: dict[str, Any]) -> dict[str, Any]:
    return await call_mcp_tool(
      p,
      server_id=str(args.get("server_id") or ""),
      tool_name=str(args.get("tool_name") or ""),
      arguments=args.get("arguments") if isinstance(args.get("arguments"), dict) else {},
    )

  def h_list_learned(_a: dict[str, Any]) -> dict[str, Any]:
    return list_learned_skills(p)

  def h_propose_learned(args: dict[str, Any]) -> dict[str, Any]:
    return propose_learned_skill(
      p,
      title=str(args.get("title") or ""),
      body=str(args.get("body") or ""),
      tags=args.get("tags"),
    )

  def h_approve_learned(args: dict[str, Any]) -> dict[str, Any]:
    return approve_learned_skill(p, str(args.get("skill_id") or ""))

  def h_get_user_profile(_a: dict[str, Any]) -> dict[str, Any]:
    mem = get_memory(p)
    return {
      "ok": True,
      "userMd": read_workspace_file("user"),
      "vehicleProfile": mem.get("vehicle_profile") or {},
      "notesCount": len(mem.get("notes") or []),
    }

  def h_update_user_profile(args: dict[str, Any]) -> dict[str, Any]:
    content = str(args.get("content") or "").strip()
    if not content:
      return {"ok": False, "error": "content required"}
    if args.get("append"):
      prev = read_workspace_file("user")
      content = (prev + "\n\n" + content).strip() if prev else content
    write_workspace_file("user", content)
    return {"ok": True, "chars": len(content)}

  return {
    "sessions_list": h_sessions_list,
    "sessions_history": h_sessions_history,
    "sessions_send": h_sessions_send,
    "search_past_conversations": h_search_past,
    "reindex_session_search": h_reindex_sessions,
    "list_toolsets": h_list_toolsets,
    "list_mcp_servers": h_list_mcp,
    "manage_mcp_server": h_manage_mcp,
    "discover_mcp_tools": h_discover_mcp,
    "call_mcp_tool": h_call_mcp,
    "list_learned_skills": h_list_learned,
    "propose_learned_skill": h_propose_learned,
    "approve_learned_skill": h_approve_learned,
    "get_user_profile": h_get_user_profile,
    "update_user_profile": h_update_user_profile,
  }
