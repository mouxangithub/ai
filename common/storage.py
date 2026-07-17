"""Unified read/write: ai_* → config.json, everything else → openpilot Params."""

from __future__ import annotations

from typing import Any

from openpilot.common.params import Params

from ai.common.config_store import get_config_store, is_ai_param
from ai.tools.param_write import put_op_param


def read_param(params: Params | None, key: str, default: Any = None, *, block: bool = False) -> Any:
  if is_ai_param(key):
    return get_config_store().get(key, default)
  p = params or Params()
  try:
    val = p.get(key, block=block)
  except Exception:
    return default
  if val is None:
    return default
  return val


def read_param_bool(params: Params | None, key: str, default: bool = False) -> bool:
  if is_ai_param(key):
    return get_config_store().get_bool(key, default)
  p = params or Params()
  try:
    return p.get_bool(key, block=False)
  except Exception:
    raw = read_param(p, key, None)
    if raw is None:
      return default
    if isinstance(raw, bytes):
      raw = raw.decode(errors="replace")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def write_param(params: Params | None, key: str, value: Any, *, block: bool = False) -> None:
  if is_ai_param(key):
    get_config_store().put(key, value)
    return
  from ai.tools.param_write import put_op_param
  put_op_param(params or Params(), key, value, block=block)


def write_param_bool(params: Params | None, key: str, value: bool, *, block: bool = False) -> None:
  if is_ai_param(key):
    get_config_store().put_bool(key, value)
    return
  p = params or Params()
  p.put_bool(key, value, block=block)


def remove_param(params: Params | None, key: str) -> None:
  if is_ai_param(key):
    get_config_store().remove(key)
    return
  (params or Params()).remove(key)
