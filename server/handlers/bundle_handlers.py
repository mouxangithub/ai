"""API handlers — bundle/profile listing and expansion (P1-2)."""
from __future__ import annotations

import json
from typing import Any

from aiohttp import web

from openpilot.common.params import Params

from ai.system.paths import workspace_path


def _json(data: Any, status: int = 200) -> web.Response:
  return web.Response(
    text=json.dumps(data, ensure_ascii=False, default=str),
    status=status,
    content_type="application/json",
  )


def _bundle_store():
  from ai.bundle.store import BundleStore
  return BundleStore(store_dir=workspace_path("ai_bundles", mkdir=True))


def _current_profile(params: Params | None) -> dict[str, Any]:
  from ai.common.storage import read_param_bool, read_param, read_param_str
  return {
    "sandboxMode": read_param(params, "ai_sandbox_mode", "read-only"),
    "sandboxShell": read_param_bool(params, "ai_sandbox_shell", True),
    "externalizeResults": read_param_bool(params, "ai_externalize_results", True),
    "externalizeThreshold": read_param(params, "ai_externalize_threshold", 8192),
    "mcpServers": read_param(params, "ai_mcp_servers", "[]"),
    "agentLoop": read_param_bool(params, "ai_use_agent_loop", True),
  }


async def api_bundle(request: web.Request) -> web.Response:
  """GET: list bundles. POST: install a stored bundle (atomic fetch/validate)."""
  store = _bundle_store()
  if request.method == "GET":
    return _json({"ok": True, "bundles": [m.to_dict() for m in store.list_bundles()]})
  try:
    body = await request.json()
  except Exception:
    return _json({"ok": False, "error": "Invalid JSON"}, status=400)
  bundle_id = str(body.get("bundleId") or body.get("bundle_id") or "").strip()
  install_dir = str(body.get("installDir") or body.get("install_dir") or "").strip()
  if not bundle_id:
    return _json({"ok": False, "error": "bundleId required"}, status=400)
  try:
    target = install_dir or str(workspace_path("ai_bundle_runtime", mkdir=True))
    manifest = store.install_bundle(bundle_id, target, clean=True)
    return _json({"ok": True, "bundle": manifest.to_dict(), "installDir": target})
  except Exception as e:
    return _json({"ok": False, "error": str(e)}, status=400)


async def api_profile_current(request: web.Request) -> web.Response:
  """GET: current effective profile (sandbox, spill, mcp, agent loop)."""
  params: Params = request.app.get("params") or Params()
  return _json({"ok": True, "profile": _current_profile(params)})