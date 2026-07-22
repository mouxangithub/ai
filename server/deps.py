"""Shared server dependencies for op助手 HTTP handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiohttp import web

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

from ai.client import AIConfig, load_config_from_params
from ai.common.storage import read_param, read_param_bool, write_param, write_param_bool
from ai.selfdrive.state import StateReader
from ai.system.admin import is_admin_mode
from ai.tools.agent_tools import filter_tools as filter_agent_tools, make_handlers

_PARAMS = Params()
_STATE_READER: StateReader | None = None
_TOOL_HANDLERS: dict[str, Any] | None = None
_MAX_TOOL_ROUNDS = 64
WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
DEFAULT_PORT = 5090


def params() -> Params:
  return _PARAMS


def openpilot_root() -> Path:
  return Path(__file__).resolve().parent.parent.parent


def get_state_reader() -> StateReader:
  global _STATE_READER
  if _STATE_READER is None:
    try:
      _STATE_READER = StateReader()
    except Exception as e:
      cloudlog.error(f"aid: failed to initialize StateReader: {e}")
      _STATE_READER = StateReader.__new__(StateReader)
      _STATE_READER._params = Params()
      _STATE_READER._sm = None
      _STATE_READER._healthy = False
      _STATE_READER._services = []
  return _STATE_READER


def json_response(data: Any, status: int = 200) -> web.Response:
  return web.Response(
    text=json.dumps(data, ensure_ascii=False, default=str),
    status=status,
    content_type="application/json",
  )


def sse(data: dict[str, Any]) -> bytes:
  return ("data: " + json.dumps(data, ensure_ascii=False, default=str) + "\n\n").encode("utf-8")


def read_param_str(key: str, default: str = "") -> str:
  val = read_param(_PARAMS, key, default)
  return val.decode() if isinstance(val, bytes) else (val or default)


def read_param_bool_val(key: str, default: bool = False) -> bool:
  return read_param_bool(_PARAMS, key, default)


def mask_key(key: str) -> str:
  if not key:
    return ""
  if len(key) <= 8:
    return "•" * len(key)
  return "•" * (len(key) - 4) + key[-4:]


def read_ai_config() -> AIConfig:
  return load_config_from_params(_PARAMS)


def get_tool_handlers() -> dict[str, Any]:
  global _TOOL_HANDLERS
  if _TOOL_HANDLERS is None:
    _TOOL_HANDLERS = make_handlers(
      get_state_reader=get_state_reader,
      params=_PARAMS,
    )
  return _TOOL_HANDLERS


def resolve_max_tool_rounds(value: Any) -> int:
  return _MAX_TOOL_ROUNDS


def filter_tools(enabled: bool, tool_prefs: dict[str, Any], driving: bool = False) -> list[dict[str, Any]] | None:
  return filter_agent_tools(enabled, tool_prefs, driving=driving, admin=is_admin_mode(_PARAMS))
