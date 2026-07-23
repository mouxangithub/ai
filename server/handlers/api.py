"""HTTP API handlers (extracted from aid.py)."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web

from openpilot.common.swaglog import cloudlog

from ai.model_router import fallbacks_for_api, load_fallback_entries, save_fallback_entries
from ai.server.deps import (
  filter_tools,
  get_state_reader,
  get_tool_handlers,
  json_response,
  mask_key,
  openpilot_root,
  params,
  read_ai_config,
  read_param_bool_val,
  read_param_str,
  resolve_max_tool_rounds,
  sse,
)
from ai.client import AIConfig, merge_config_from_body, test_connection, list_models
from ai.common.params import (
  AI_DEFAULT_MODELS,
  AI_EMBEDDING_MODEL_CATALOG,
  AI_EMBEDDING_PROVIDER_LABELS,
  AI_EMBEDDING_PROVIDERS,
  AI_PROVIDER_LABELS,
  AI_PROVIDER_MODEL_CATALOG,
  AI_PROVIDERS,
  AI_SAME_MODE_EMBEDDING_MODELS,
)
from ai.common.storage import write_param, write_param_bool
from ai.embedding import DEFAULT_EMBEDDING_MODELS, load_embedding_config
from ai.persona import ensure_default_persona
from ai.skills.loader import list_skills, load_enabled_skill_ids, save_enabled_skill_ids
from ai.system.admin import is_admin_mode
from ai.system.host_env import get_host_environment
from ai.system.safety import ACTION_RULES, is_action_allowed
from ai.system.shell import run_command
from ai.agents.config import agents_enabled_payload
from ai.agents.office import office_snapshot as get_office_snapshot
from ai.agents.orchestrator import detect_orchestration_plan, run_chat_with_agents
from ai.agents.registry import filter_tools_for_agent, get_agent, list_agents, orchestrator_id
from ai.agents.router import resolve_agent_route
from ai.chat_jobs import cancel_job, cancel_jobs_for_session, get_job, list_active_jobs, start_chat_job, wait_for_job
from ai.command_queue import submit_chat_request
from ai.chat_runner import ChatCancelled
from ai.sync_hub import broadcast_config, broadcast_notifications, broadcast_sessions
from ai.tools.agent_tools import tool_meta_for_host
from ai.tools.memory_store import (
  append_note,
  delete_note,
  get_memory,
  update_vehicle_profile,
  sync_vehicle_profile_from_state,
)
from ai.tools.notifications import list_notifications, mark_notifications_read
from ai.tools.rag_store import (
  list_documents,
  remove_document,
  search_documents,
  upsert_document,
  reindex_all,
)
from ai.tools.scheduler import list_tasks, remove_task, upsert_task
from ai.tools.session_store import get_sessions, save_sessions
from ai.tools.workflows import list_workflows
from ai.tools.write_pending import confirm_pending, list_pending
from ai.usage_log import load_usage

_PARAMS = params()
_get_state_reader = get_state_reader
_json_response = json_response
_sse = sse
_read_param_str = read_param_str
_read_param_bool = read_param_bool_val
_mask_key = mask_key
_read_ai_config = read_ai_config
_get_tool_handlers = get_tool_handlers
_resolve_max_tool_rounds = resolve_max_tool_rounds
_filter_tools = filter_tools


async def _parse_chat_body(request: web.Request) -> tuple[dict[str, Any] | None, AIConfig | None, web.Response | None]:
  config = _read_ai_config()
  if not config.is_configured:
    return None, None, _json_response({
      "ok": False,
      "error": config.configuration_error or "AI not configured. Set provider, model, and API key first.",
    }, status=400)

  try:
    body = await request.json()
  except json.JSONDecodeError:
    return None, None, _json_response({"ok": False, "error": "Invalid JSON body."}, status=400)

  raw_messages = body.get("messages", [])
  if not isinstance(raw_messages, list) or not raw_messages:
    return None, None, _json_response({"ok": False, "error": "messages must be a non-empty list."}, status=400)
  return body, config, None


def _prepare_chat_run(body: dict[str, Any]) -> dict[str, Any]:
  tools_enabled = bool(body.get("tools", True))
  tool_prefs = body.get("toolPrefs") or {}
  max_tool_rounds = _resolve_max_tool_rounds(body.get("maxToolRounds"))
  drive_state = _get_state_reader().update(timeout=0)
  try:
    from ai.system.host_env import is_pc_dev
    pc_dev = is_pc_dev()
  except Exception:
    pc_dev = os.name == "nt" or not os.path.isfile("/TICI")

  route = resolve_agent_route(
    body,
    driving=drive_state.is_driving,
    pc_dev=pc_dev,
    params=_PARAMS,
  )
  route_dict = route.to_dict()
  if route.workflow_id and not body.get("workflow"):
    body["workflow"] = route.workflow_id

  from ai.tools.toolsets import resolve_toolset
  toolset_id = resolve_toolset(
    drive_state.is_driving,
    agent_id=route.agent_id,
    explicit=str(body.get("toolset") or body.get("toolsetId") or "").strip(),
  )

  tools = _filter_tools(
    tools_enabled,
    tool_prefs,
    driving=drive_state.is_driving,
    toolset_id=toolset_id,
  ) if tools_enabled else None
  agent = get_agent(route.agent_id)
  if agent and tools:
    tools = filter_tools_for_agent(tools, agent)

  orchestration_plan = None
  if route.agent_id == orchestrator_id() and route.reason == "default":
    plan = detect_orchestration_plan(
      body,
      driving=drive_state.is_driving,
      pc_dev=pc_dev,
      params=_PARAMS,
    )
    if plan:
      orchestration_plan = [p.to_dict() for p in plan]

  return {
    "tools": tools,
    "max_tool_rounds": max_tool_rounds,
    "route": route_dict,
    "orchestration_plan": orchestration_plan,
    "toolset": toolset_id,
  }


def _chat_tools_for_body(body: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, int]:
  prep = _prepare_chat_run(body)
  return prep["tools"], prep["max_tool_rounds"]


async def api_chat(request: web.Request) -> web.Response:
  try:
    body, config, err = await _parse_chat_body(request)
    if err is not None:
      return err
    assert body is not None and config is not None

    prep = _prepare_chat_run(body)
    run_body = {**body, "_config": config, "_agent_route": prep["route"]}
    if prep.get("orchestration_plan"):
      run_body["_orchestration_plan"] = prep["orchestration_plan"]

    async def stream_response():
      response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={"Content-Type": "text/event-stream; charset=utf-8"},
      )
      await response.prepare(request)

      async def emit(event: dict[str, Any]) -> None:
        await response.write(_sse(event))

      try:
        await run_chat_with_agents(
          run_body,
          _PARAMS,
          emit,
          get_state_reader=_get_state_reader,
          get_tool_handlers=_get_tool_handlers,
          tools=prep["tools"],
          max_tool_rounds=prep["max_tool_rounds"],
        )
      except ChatCancelled:
        pass
      await response.write_eof()
      return response

    return await stream_response()
  except Exception as e:
    cloudlog.error(f"aid: api_chat error: {e}")
    return _json_response({"ok": False, "error": f"Internal error: {e}"}, status=500)


async def api_chat_jobs(request: web.Request) -> web.Response:
  """POST: start background job. GET ?sessionId=: list active jobs."""
  if request.method == "GET":
    session_id = str(request.query.get("sessionId", "") or "").strip()
    jobs = list_active_jobs(session_id or None)
    from ai.command_queue import list_queued
    return _json_response({"ok": True, "jobs": jobs, "queue": list_queued(session_id or None)})

  try:
    body, config, err = await _parse_chat_body(request)
    if err is not None:
      return err
    assert body is not None and config is not None

    session_id = str(body.get("sessionId", "") or "").strip()
    prep = _prepare_chat_run(body)
    body = {
      **body,
      "_agent_route": prep["route"],
      **({"_orchestration_plan": prep["orchestration_plan"]} if prep.get("orchestration_plan") else {}),
    }
    queue_mode = str(body.get("queueMode") or body.get("queue_mode") or "steer").strip()
    body["queueMode"] = queue_mode
    drive_state = _get_state_reader().update(timeout=0)

    async def _start(b: dict[str, Any]) -> str:
      return await start_chat_job(
        session_id,
        b,
        _PARAMS,
        get_state_reader=_get_state_reader,
        get_tool_handlers=_get_tool_handlers,
        tools=prep["tools"],
        max_tool_rounds=prep["max_tool_rounds"],
        config=config,
      )

    submit = await submit_chat_request(
      session_id,
      body,
      driving=drive_state.is_driving,
      queue_mode=queue_mode,
      start_fn=_start,
      cancel_session_fn=cancel_jobs_for_session,
    )
    job_id = submit.get("jobId")
    wait = str(request.query.get("wait", "") or body.get("wait", "")).lower() in ("1", "true", "yes")
    timeout_ms = int(request.query.get("timeoutMs") or body.get("timeoutMs") or 60000)
    result: dict[str, Any] = {
      "ok": True,
      "jobId": job_id,
      "sessionId": session_id,
      "runId": job_id,
      "queueMode": submit.get("queueMode"),
      "queued": submit.get("queued", False),
      "queuePosition": submit.get("queuePosition"),
      "action": submit.get("action"),
    }
    if wait and job_id:
      waited = await wait_for_job(job_id, timeout_ms=timeout_ms)
      if waited:
        result["job"] = waited
        result["status"] = waited.get("status")
    return _json_response(result)
  except Exception as e:
    cloudlog.error(f"aid: api_chat_jobs error: {e}")
    return _json_response({"ok": False, "error": f"Internal error: {e}"}, status=500)


async def api_chat_job_detail(request: web.Request) -> web.Response:
  job_id = request.match_info.get("job_id", "")
  if request.method == "DELETE":
    ok = await cancel_job(job_id)
    if not ok:
      return _json_response({"ok": False, "error": "Job not found"}, status=404)
    return _json_response({"ok": True, "cancelled": True})

  since = int(request.query.get("since", "0") or "0")
  job = get_job(job_id, since=since)
  if not job:
    return _json_response({"ok": False, "error": "Job not found"}, status=404)

  wait = str(request.query.get("wait", "")).lower() in ("1", "true", "yes")
  if wait and job.get("status") == "running":
    timeout_ms = int(request.query.get("timeoutMs", "60000") or "60000")
    waited = await wait_for_job(job_id, timeout_ms=timeout_ms)
    if waited:
      job = waited
  return _json_response(job)



async def api_workflows(request: web.Request) -> web.Response:
  return _json_response({"ok": True, "workflows": list_workflows()})


async def api_notifications(request: web.Request) -> web.Response:
  if request.method == "POST":
    mark_notifications_read()
    try:
      await broadcast_notifications()
    except Exception as e:
      cloudlog.warning(f"aid: broadcast_notifications failed: {e}")
    return _json_response({"ok": True})
  unread = request.query.get("unread", "1") != "0"
  return _json_response(list_notifications(unread_only=unread))


async def api_adaptation_bundle(request: web.Request) -> web.Response:
  project_id = request.match_info.get("project_id", "")
  from ai.tools.adaptation import export_adaptation_bundle
  result = export_adaptation_bundle(project_id)
  if not result.get("ok"):
    return _json_response(result, status=404)
  if request.query.get("download") == "1":
    filename = f"adaptation_{project_id}.json"
    return web.Response(
      body=json.dumps(result, ensure_ascii=False, indent=2),
      content_type="application/json",
      headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
  return _json_response(result)


# -----------------------------------------------------------------------------
# Streaming helpers
# -----------------------------------------------------------------------------

def _sse(data: dict[str, Any]) -> bytes:
  return ("data: " + json.dumps(data, ensure_ascii=False, default=str) + "\n\n").encode("utf-8")


# -----------------------------------------------------------------------------
# API handlers
# -----------------------------------------------------------------------------

async def api_bootstrap(request: web.Request) -> web.Response:
  """Single round-trip bootstrap: status + config + providers (faster page load)."""
  try:
    ensure_default_persona(_PARAMS)
    reader = _get_state_reader()
    state = reader.update(timeout=0)
    sync_vehicle_profile_from_state(
      _PARAMS,
      brand=state.brand or "",
      car_fingerprint=state.car_fingerprint or "",
    )
    config = _read_ai_config()
    embed_cfg = load_embedding_config(_PARAMS, config)
    skills_on = load_enabled_skill_ids(_PARAMS)
    from ai.timezone_util import read_ai_timezone_name
    tz_name = read_ai_timezone_name(_PARAMS)
    first_run_done = _read_param_bool("ai_first_run_done")
    try:
      from ai.fork.detect_fork import detect_fork
      fork_detected = detect_fork(openpilot_root())
    except Exception:
      fork_detected = {"ok": False}

    bootstrap_models: list[dict[str, Any]] = [
      {"id": mid} for mid in (AI_PROVIDER_MODEL_CATALOG.get(config.provider) or []) if mid
    ]
    models_source = "catalog"
    if config.is_configured:
      try:
        lm = await list_models(config)
        if lm.get("ok") and lm.get("models"):
          bootstrap_models = lm["models"]
          models_source = str(lm.get("source") or "api")
      except Exception as e:
        cloudlog.warning(f"aid: bootstrap list_models failed: {e}")

    return _json_response({
    "ok": True,
    "driving": state.is_driving,
    "state": state.to_dict(),
    "ai": {
      "configured": config.is_configured,
      "provider": config.provider,
      "model": config.model,
      "configureError": config.configuration_error,
    },
    "providers": AI_PROVIDERS,
    "providerLabels": AI_PROVIDER_LABELS,
    "defaults": AI_DEFAULT_MODELS,
    "modelCatalog": AI_PROVIDER_MODEL_CATALOG,
    "models": bootstrap_models,
    "modelsSource": models_source,
    "config": {
      "provider": config.provider,
      "model": config.model,
      "apiKey": _mask_key(config.api_key),
      "baseUrl": config.base_url,
      "systemPrompt": config.system_prompt,
      "temperature": config.temperature,
      "topP": config.top_p,
      "maxTokens": config.max_tokens,
      "thinkingEnabled": config.thinking_enabled,
      "thinkingKeep": config.thinking_keep,
      "webPin": _mask_key(_read_param_str("ai_web_pin")),
      "timezone": tz_name,
      "configured": config.is_configured,
      "configureError": config.configuration_error,
      "embeddingMode": embed_cfg.mode,
      "embeddingProvider": embed_cfg.provider,
      "embeddingModel": embed_cfg.model,
      "embeddingApiKey": _mask_key(_read_param_str("ai_embedding_api_key")) if embed_cfg.mode == "separate" else "",
      "embeddingBaseUrl": embed_cfg.base_url,
      "embeddingConfigured": embed_cfg.is_configured,
    },
    "embeddingDefaults": DEFAULT_EMBEDDING_MODELS,
    "embeddingProviders": AI_EMBEDDING_PROVIDERS,
    "embeddingProviderLabels": AI_EMBEDDING_PROVIDER_LABELS,
    "embeddingModelCatalog": AI_EMBEDDING_MODEL_CATALOG,
    "embeddingSameModeCatalog": AI_SAME_MODE_EMBEDDING_MODELS,
    "tools": tool_meta_for_host(),
    "hostEnvironment": get_host_environment(),
    "skills": list_skills(),
    "skillsEnabled": sorted(skills_on) if skills_on is not None else None,
    "pinRequired": bool(_read_param_str("ai_web_pin").strip()),
    "adminMode": is_admin_mode(_PARAMS),
    "onboarding": {
      "firstRunDone": first_run_done,
      "showWizard": not first_run_done or not config.is_configured,
    },
    "fork": fork_detected if fork_detected.get("ok") else None,
    "workflows": list_workflows(),
    "agents": list_agents(include_orchestrator=True),
    "agentsConfig": agents_enabled_payload(_PARAMS),
    "office": get_office_snapshot(),
    "notifications": list_notifications(unread_only=True).get("notifications", [])[:5],
    })
  except Exception as e:
    cloudlog.error(f"aid: api_bootstrap error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_status(request: web.Request) -> web.Response:
  try:
    state = _get_state_reader().update(timeout=0)
    config = _read_ai_config()
  except Exception as e:
    return _json_response({"ok": False, "error": str(e)}, status=500)
  return _json_response({
    "ok": True,
    "driving": state.is_driving,
    "state": state.to_dict(),
    "ai": {
      "configured": config.is_configured,
      "provider": config.provider,
      "model": config.model,
    },
  })


async def api_providers(request: web.Request) -> web.Response:
  return _json_response({
    "ok": True,
    "providers": AI_PROVIDERS,
    "providerLabels": AI_PROVIDER_LABELS,
    "defaults": AI_DEFAULT_MODELS,
    "modelCatalog": AI_PROVIDER_MODEL_CATALOG,
    "embeddingProviders": AI_EMBEDDING_PROVIDERS,
    "embeddingProviderLabels": AI_EMBEDDING_PROVIDER_LABELS,
    "embeddingModelCatalog": AI_EMBEDDING_MODEL_CATALOG,
    "embeddingSameModeCatalog": AI_SAME_MODE_EMBEDDING_MODELS,
    "embeddingDefaults": DEFAULT_EMBEDDING_MODELS,
    "rules": {k: {"category": v.category.value, "description": v.description}
              for k, v in ACTION_RULES.items()},
  })


async def api_get_config(request: web.Request) -> web.Response:
  from ai.timezone_util import read_ai_timezone_name

  config = _read_ai_config()
  embed_cfg = load_embedding_config(_PARAMS, config)
  return _json_response({
    "ok": True,
    "config": {
      "provider": config.provider,
      "model": config.model,
      "apiKey": _mask_key(config.api_key),
      "baseUrl": config.base_url,
      "modelFallbacks": fallbacks_for_api(_PARAMS, config),
      "systemPrompt": config.system_prompt,
      "temperature": config.temperature,
      "topP": config.top_p,
      "maxTokens": config.max_tokens,
      "thinkingEnabled": config.thinking_enabled,
      "thinkingKeep": config.thinking_keep,
      "webPin": _mask_key(_read_param_str("ai_web_pin")),
      "timezone": read_ai_timezone_name(_PARAMS),
      "configured": config.is_configured,
      "configureError": config.configuration_error,
      "embeddingMode": embed_cfg.mode,
      "embeddingProvider": embed_cfg.provider,
      "embeddingModel": embed_cfg.model,
      "embeddingApiKey": _mask_key(_read_param_str("ai_embedding_api_key")) if embed_cfg.mode == "separate" else "",
      "embeddingBaseUrl": embed_cfg.base_url,
      "embeddingConfigured": embed_cfg.is_configured,
    },
  })


async def api_post_config(request: web.Request) -> web.Response:
  state = _get_state_reader().update(timeout=0)
  allowed, reason = is_action_allowed("write_ai_config", state, admin=is_admin_mode(_PARAMS))
  if not allowed:
    return _json_response({"ok": False, "error": reason}, status=403)

  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON body."}, status=400)

  def _put(key: str, value: Any) -> None:
    if value is None:
      return
    if isinstance(value, bool):
      write_param_bool(_PARAMS, key, value)
    else:
      write_param(_PARAMS, key, str(value))

  try:
    _put("ai_provider", body.get("provider"))
    _put("ai_model", body.get("model"))
    api_key = body.get("apiKey", "")
    if api_key and not str(api_key).startswith("•"):
      _put("ai_api_key", str(api_key).strip())
    _put("ai_base_url", body.get("baseUrl"))
    _put("ai_system_prompt", body.get("systemPrompt"))
    _put("ai_temperature", body.get("temperature"))
    _put("ai_top_p", body.get("topP"))
    _put("ai_max_tokens", body.get("maxTokens"))
    _put("ai_thinking_enabled", body.get("thinkingEnabled"))
    _put("ai_thinking_keep", body.get("thinkingKeep"))
    web_pin = body.get("webPin", "")
    if web_pin is not None and web_pin != "" and not str(web_pin).startswith("•"):
      _put("ai_web_pin", web_pin)
    elif body.get("clearWebPin"):
      _put("ai_web_pin", "")
    _put("ai_embedding_mode", body.get("embeddingMode"))
    _put("ai_embedding_provider", body.get("embeddingProvider"))
    _put("ai_embedding_model", body.get("embeddingModel"))
    emb_key = body.get("embeddingApiKey", "")
    if emb_key and not str(emb_key).startswith("•"):
      _put("ai_embedding_api_key", emb_key)
    _put("ai_embedding_base_url", body.get("embeddingBaseUrl"))
    tz = body.get("timezone")
    if tz is not None and str(tz).strip():
      _put("ai_timezone", str(tz).strip())
    if "modelFallbacks" in body:
      existing = load_fallback_entries(_PARAMS)
      incoming = body.get("modelFallbacks") or []
      merged: list[dict[str, Any]] = []
      for i, row in enumerate(incoming):
        if not isinstance(row, dict):
          continue
        item = dict(row)
        api_key = str(item.get("apiKey") or item.get("api_key") or "").strip()
        if api_key.startswith("•") and i < len(existing):
          item["apiKey"] = existing[i].get("apiKey") or existing[i].get("api_key") or ""
        merged.append(item)
      save_fallback_entries(_PARAMS, merged)
  except Exception as e:
    cloudlog.error(f"aid: api_post_config failed: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)

  config = _read_ai_config()
  try:
    await broadcast_config(_PARAMS)
  except Exception as e:
    cloudlog.warning(f"aid: broadcast_config failed: {e}")
  return _json_response({
    "ok": True,
    "configured": config.is_configured,
    "configureError": config.configuration_error,
  })


async def api_models(request: web.Request) -> web.Response:
  try:
    saved = _read_ai_config()
    body = None
    if request.method == "POST":
      try:
        body = await request.json()
      except json.JSONDecodeError:
        return _json_response({"ok": False, "error": "Invalid JSON body."}, status=400)
    config = merge_config_from_body(saved, body)
    from ai.client import list_models
    result = await list_models(config)
    return _json_response({
      "ok": bool(result.get("ok")),
      "error": result.get("error"),
      "models": result.get("models", []),
      "configured": config.is_configured,
      "configureError": config.configuration_error,
    })
  except Exception as e:
    cloudlog.error(f"aid: api_models error: {e}")
    return _json_response({"ok": False, "error": f"Internal error: {e}", "models": []}, status=500)


async def api_test_connection(request: web.Request) -> web.Response:
  try:
    saved = _read_ai_config()
    body = None
    if request.method == "POST":
      try:
        body = await request.json()
      except json.JSONDecodeError:
        return _json_response({"ok": False, "error": "Invalid JSON body."}, status=400)
    config = merge_config_from_body(saved, body)
    if not config.is_configured:
      return _json_response({
        "ok": False,
        "error": config.configuration_error or "AI not configured",
        "configured": False,
        "configureError": config.configuration_error,
      })
    result = await test_connection(config)
    return _json_response({
      "ok": bool(result.get("ok")),
      "error": result.get("error"),
      "model_available": result.get("model_available"),
      "models_count": result.get("models_count"),
      "message": result.get("message"),
      "configured": True,
    })
  except Exception as e:
    cloudlog.error(f"aid: api_test_connection error: {e}")
    return _json_response({"ok": False, "error": f"Internal error: {e}"}, status=500)


async def api_skills(request: web.Request) -> web.Response:
  """List or persist enabled agent skills."""
  if request.method == "GET":
    enabled = load_enabled_skill_ids(_PARAMS)
    return _json_response({
      "ok": True,
      "skills": list_skills(),
      "enabled": sorted(enabled) if enabled else None,
    })
  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON"}, status=400)
  ids = body.get("enabled") or []
  if not isinstance(ids, list):
    return _json_response({"ok": False, "error": "enabled must be a list"}, status=400)
  save_enabled_skill_ids(_PARAMS, [str(x) for x in ids if x])
  return _json_response({"ok": True, "enabled": ids})


async def api_tools_meta(request: web.Request) -> web.Response:
  return _json_response({"ok": True, "tools": tool_meta_for_host(), "hostEnvironment": get_host_environment()})


async def api_memory(request: web.Request) -> web.Response:
  if request.method == "GET":
    return _json_response(get_memory(_PARAMS))
  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON"}, status=400)
  if body.get("delete_note_id"):
    return _json_response(delete_note(_PARAMS, str(body["delete_note_id"])))
  if body.get("note"):
    return _json_response(append_note(_PARAMS, body["note"], body.get("tags")))
  if body.get("vehicle_profile"):
    return _json_response(update_vehicle_profile(_PARAMS, body["vehicle_profile"]))
  return _json_response({"ok": False, "error": "Nothing to update"}, status=400)


async def api_scheduler(request: web.Request) -> web.Response:
  if request.method == "GET":
    return _json_response(list_tasks(_PARAMS))
  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON"}, status=400)
  if body.get("nl") or body.get("natural_language"):
    from ai.tools.scheduler import upsert_task_from_nl
    text = str(body.get("nl") or body.get("natural_language") or "")
    return _json_response(upsert_task_from_nl(_PARAMS, text))
  op = body.get("operation", "upsert")
  if op == "remove":
    return _json_response(remove_task(_PARAMS, str(body.get("task_id", ""))))
  return _json_response(upsert_task(
    _PARAMS,
    task_id=body.get("task_id"),
    name=str(body.get("name", "")),
    action=str(body.get("action", "read_last_log")),
    interval_minutes=int(body.get("interval_minutes", 60)),
    enabled=bool(body.get("enabled", True)),
    payload=body.get("payload"),
    trigger=str(body.get("trigger", "interval")),
  ))


async def api_write_confirm(request: web.Request) -> web.Response:
  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON"}, status=400)
  state = _get_state_reader().update(timeout=0)
  allowed, reason = is_action_allowed("write_param", state, admin=is_admin_mode(_PARAMS))
  if not allowed:
    return _json_response({"ok": False, "error": reason}, status=403)
  pending_id = str(body.get("pending_id", ""))
  if not pending_id:
    return _json_response({"ok": False, "error": "pending_id required"}, status=400)
  return _json_response(confirm_pending(_PARAMS, pending_id))


async def api_write_pending(request: web.Request) -> web.Response:
  return _json_response(list_pending(_PARAMS))


async def api_tune_passport(request: web.Request) -> web.Response:
  from ai.tools.tune_passport_store import list_tune_passport
  limit = int(request.query.get("limit", "30"))
  return _json_response(list_tune_passport(limit=limit))


async def api_rag(request: web.Request) -> web.Response:
  config = _read_ai_config()
  embed_cfg = load_embedding_config(_PARAMS, config)
  if request.method == "GET":
    q = request.query.get("q", "")
    if q:
      return _json_response(await search_documents(_PARAMS, q, embed_config=embed_cfg))
    return _json_response(list_documents(_PARAMS))
  try:
    body = await request.json()
  except json.JSONDecodeError:
    return _json_response({"ok": False, "error": "Invalid JSON"}, status=400)
  op = body.get("operation", "upsert")
  if op == "remove":
    return _json_response(remove_document(_PARAMS, str(body.get("doc_id", ""))))
  if op == "reindex":
    return _json_response(await reindex_all(_PARAMS, embed_cfg))
  return _json_response(await upsert_document(
    _PARAMS,
    title=str(body.get("title", "")),
    text=str(body.get("text", "")),
    tags=body.get("tags"),
    doc_id=body.get("doc_id"),
    embed_config=embed_cfg,
    reindex=body.get("reindex", True),
  ))


async def api_sessions(request: web.Request) -> web.Response:
  if request.method == "GET":
    return _json_response(get_sessions(_PARAMS))
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


async def api_dev_assets(request: web.Request) -> web.Response:
  from ai.tools.dev_assets import list_dev_assets, resolve_dev_asset
  if request.method == "GET" and request.match_info.get("kind"):
    kind = request.match_info.get("kind", "")
    name = request.match_info.get("name", "")
    path = resolve_dev_asset(kind, name)
    if path is None:
      return web.Response(status=404, text="Not found")
    return web.FileResponse(path)
  limit = int(request.query.get("limit", "40"))
  return _json_response(list_dev_assets(limit=limit))


async def api_pc_sessions(request: web.Request) -> web.Response:
  try:
    from ai.tools.pc_dev_tools import pc_list_tool_sessions
    return _json_response(pc_list_tool_sessions(limit=int(request.query.get("limit", "20"))))
  except Exception as e:
    return _json_response({"ok": False, "error": str(e)})


async def api_shell(request: web.Request) -> web.Response:
  try:
    state = _get_state_reader().update(timeout=0)
    allowed, reason = is_action_allowed("shell", state, admin=is_admin_mode(_PARAMS))
    if not allowed:
      return _json_response({"ok": False, "error": reason}, status=403)

    try:
      body = await request.json()
    except json.JSONDecodeError:
      return _json_response({"ok": False, "error": "Invalid JSON body."}, status=400)

    command_name = body.get("command", "")
    result = run_command(command_name)
    return _json_response(result)
  except Exception as e:
    cloudlog.error(f"aid: api_shell error: {e}")
    return _json_response({"ok": False, "error": f"Internal error: {e}"}, status=500)


async def api_state(request: web.Request) -> web.Response:
  try:
    reader = _get_state_reader()
    reader.update(timeout=0)
    return _json_response({"ok": True, "data": reader.latest()})
  except Exception as e:
    cloudlog.error(f"aid: api_state error: {e}")
    return _json_response({"ok": False, "error": f"Internal error: {e}"}, status=500)


async def api_usage(request: web.Request) -> web.Response:
  return _json_response({"ok": True, "usage": load_usage(_PARAMS)})


async def api_package_version(request: web.Request) -> web.Response:
  try:
    from ai.version_info import check_update

    fetch = request.query.get("fetch", "1") not in ("0", "false", "no")
    return _json_response(check_update(fetch_remote=fetch))
  except Exception as e:
    cloudlog.error(f"aid: api_package_version error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_package_update(request: web.Request) -> web.Response:
  try:
    from ai.system.host_env import is_pc_dev
    from ai.version_info import run_package_update

    state = _get_state_reader().update(timeout=0)
    if state.is_driving and not is_pc_dev():
      return _json_response({"ok": False, "error": "行驶中无法更新 op助手，请停车后重试。"}, status=403)

    try:
      body = await request.json()
    except (json.JSONDecodeError, ValueError, aiohttp.ClientPayloadError):
      body = {}
    if not body.get("confirm"):
      return _json_response({
        "ok": True,
        "needs_confirmation": True,
        "hint": "将执行 git pull 并重新集成 openpilot。请 POST confirm=true。",
      })

    root = body.get("openpilot_root") or str(openpilot_root())
    result = run_package_update(openpilot_root=str(root))
    status = 200 if result.get("ok") else 500
    return _json_response(result, status=status)
  except Exception as e:
    cloudlog.error(f"aid: api_package_update error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_fork_detect(request: web.Request) -> web.Response:
  try:
    from ai.fork.analyze_fork import analyze_fork_with_ai
    from ai.fork.detect_fork import detect_fork

    root = openpilot_root()
    do_analyze = request.query.get("analyze", "0") in ("1", "true", "yes")
    if do_analyze:
      result = await analyze_fork_with_ai(_PARAMS, root, force=request.query.get("force") in ("1", "true"))
      if result.get("ok"):
        result["detect"] = detect_fork(root)
      return _json_response(result, status=200 if result.get("ok") else 500)
    return _json_response(detect_fork(root))
  except Exception as e:
    cloudlog.error(f"aid: api_fork_detect error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_fork_analyze(request: web.Request) -> web.Response:
  try:
    from ai.fork.analyze_fork import analyze_fork_with_ai

    root = openpilot_root()
    try:
      body = await request.json()
    except (json.JSONDecodeError, ValueError, aiohttp.ClientPayloadError):
      body = {}
    force = bool(body.get("force"))
    result = await analyze_fork_with_ai(_PARAMS, root, force=force)
    if result.get("ok") and result.get("analysis"):
      fid = result["analysis"].get("fork_identity") or result.get("identity", {}).get("fork_id")
      if fid:
        write_param(_PARAMS, "ai_fork_id", str(fid))
        write_param(_PARAMS, "ai_fork_profile_applied", datetime.now(timezone.utc).isoformat())
    return _json_response(result, status=200 if result.get("ok") else 500)
  except Exception as e:
    cloudlog.error(f"aid: api_fork_analyze error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_fork_sync(request: web.Request) -> web.Response:
  try:
    from ai.fork.fork_sync import generate_fork_drafts, list_fork_drafts

    try:
      body = await request.json()
    except (json.JSONDecodeError, ValueError, aiohttp.ClientPayloadError):
      body = {}
    if not body.get("confirm"):
      return _json_response({
        "ok": True,
        "needs_confirmation": True,
        "hint": "AI 将先阅读 openpilot 项目并分析 fork，再生成技能/文档草稿（需人工审核）。POST confirm=true。",
        "drafts": list_fork_drafts()[:5],
      })
    result = await generate_fork_drafts(
      _PARAMS,
      force_analyze=bool(body.get("force_analyze")),
    )
    if result.get("ok") and result.get("fork_id"):
      write_param(_PARAMS, "ai_fork_id", str(result["fork_id"]))
      write_param(_PARAMS, "ai_fork_profile_applied", datetime.now(timezone.utc).isoformat())
    return _json_response(result, status=200 if result.get("ok") else 500)
  except Exception as e:
    cloudlog.error(f"aid: api_fork_sync error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_fork_run_stream(request: web.Request) -> web.Response:
  """SSE stream: scan → analyze → draft with phase/reasoning/content events."""
  try:
    from ai.fork.fork_sync import run_fork_pipeline

    try:
      body = await request.json()
    except (json.JSONDecodeError, ValueError, aiohttp.ClientPayloadError):
      body = {}
    if not body.get("confirm"):
      return _json_response({
        "ok": False,
        "needs_confirmation": True,
        "error": "POST confirm=true to start fork analysis pipeline.",
      }, status=400)

    root = openpilot_root()
    force = bool(body.get("force"))
    skip_draft = bool(body.get("skip_draft"))

    async def stream_response():
      response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache"},
      )
      await response.prepare(request)

      async def emit(event: dict[str, Any]) -> None:
        await response.write(_sse(event))

      result: dict[str, Any] = {"ok": False}
      try:
        result = await run_fork_pipeline(
          _PARAMS,
          root,
          force=force,
          skip_draft=skip_draft,
          emit=emit,
        )
        if result.get("ok") and result.get("fork_id"):
          write_param(_PARAMS, "ai_fork_id", str(result["fork_id"]))
          write_param(_PARAMS, "ai_fork_profile_applied", datetime.now(timezone.utc).isoformat())
        elif result.get("ok") and result.get("analysis"):
          fid = (result.get("analysis") or {}).get("fork_identity") or result.get("identity", {}).get("fork_id")
          if fid:
            write_param(_PARAMS, "ai_fork_id", str(fid))
            write_param(_PARAMS, "ai_fork_profile_applied", datetime.now(timezone.utc).isoformat())
      except Exception as e:
        cloudlog.error(f"aid: api_fork_run_stream pipeline error: {e}")
        await emit({"type": "error", "error": str(e)})
        await emit({"type": "done", "ok": False, "error": str(e)})
      await response.write_eof()
      return response

    return await stream_response()
  except Exception as e:
    cloudlog.error(f"aid: api_fork_run_stream error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_onboarding_complete(request: web.Request) -> web.Response:
  try:
    write_param_bool(_PARAMS, "ai_first_run_done", True)
    config = _read_ai_config()
    return _json_response({
      "ok": True,
      "configured": config.is_configured,
      "configureError": config.configuration_error,
    })
  except Exception as e:
    return _json_response({"ok": False, "error": str(e)}, status=500)


async def api_integrate_openpilot(request: web.Request) -> web.Response:
  try:
    from ai.system.host_env import is_pc_dev
    from ai.install.integrate_openpilot import integrate

    state = _get_state_reader().update(timeout=0)
    if state.is_driving and not is_pc_dev():
      return _json_response({"ok": False, "error": "行驶中无法集成，请停车后重试。"}, status=403)
    root = openpilot_root()
    result = integrate(root, root / "ai", force_compile=bool(request.query.get("force")))
    return _json_response(result, status=200 if result.get("ok") else 500)
  except Exception as e:
    cloudlog.error(f"aid: api_integrate_openpilot error: {e}")
    return _json_response({"ok": False, "error": str(e)}, status=500)


