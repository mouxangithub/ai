"""Chat model selection with optional failover chain."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openpilot.common.params import Params

from ai.client import AIConfig, ChatChunk, chat_completion
from ai.common.storage import read_param, write_param

FALLBACKS_PARAM = "ai_model_fallbacks"


def _mask_key(key: str) -> str:
  if not key:
    return ""
  if len(key) <= 8:
    return "•" * len(key)
  return "•" * (len(key) - 4) + key[-4:]


def load_fallback_entries(params: Params | None = None) -> list[dict[str, Any]]:
  """Load raw fallback entries from Params (for settings UI)."""
  params = params or Params()
  raw = read_param(params, FALLBACKS_PARAM)
  if not raw:
    return []
  try:
    if isinstance(raw, bytes):
      raw = raw.decode("utf-8", errors="replace")
    data = json.loads(raw)
  except Exception:
    return []
  if not isinstance(data, list):
    return []
  out: list[dict[str, Any]] = []
  for item in data:
    if not isinstance(item, dict):
      continue
    model = str(item.get("model") or "").strip()
    if not model:
      continue
    out.append({
      "provider": str(item.get("provider") or "").strip(),
      "model": model,
      "apiKey": str(item.get("api_key") or item.get("apiKey") or ""),
      "baseUrl": str(item.get("base_url") or item.get("baseUrl") or ""),
      "label": str(item.get("label") or "").strip(),
    })
  return out


def save_fallback_entries(params: Params, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
  """Persist fallback chain; returns sanitized list."""
  clean: list[dict[str, Any]] = []
  for item in entries or []:
    if not isinstance(item, dict):
      continue
    model = str(item.get("model") or "").strip()
    if not model:
      continue
    row = {
      "provider": str(item.get("provider") or "").strip(),
      "model": model,
    }
    label = str(item.get("label") or "").strip()
    if label:
      row["label"] = label[:64]
    api_key = str(item.get("apiKey") or item.get("api_key") or "").strip()
    if api_key and not api_key.startswith("•"):
      row["api_key"] = api_key
    base_url = str(item.get("baseUrl") or item.get("base_url") or "").strip()
    if base_url:
      row["base_url"] = base_url
    clean.append(row)
  write_param(params, FALLBACKS_PARAM, json.dumps(clean, ensure_ascii=False))
  return clean


def fallbacks_for_api(params: Params, base: AIConfig | None = None) -> list[dict[str, Any]]:
  """Fallback list for GET config — mask secrets, fill provider from primary."""
  base = base or AIConfig(provider="opencode-zen", model="", api_key="")
  out = []
  for item in load_fallback_entries(params):
    out.append({
      "provider": item.get("provider") or base.provider,
      "model": item.get("model", ""),
      "apiKey": _mask_key(item.get("apiKey", "")),
      "baseUrl": item.get("baseUrl", ""),
      "label": item.get("label", ""),
    })
  return out


def _parse_fallbacks(params, base: AIConfig) -> list[AIConfig]:
  out: list[AIConfig] = []
  seen: set[tuple[str, str]] = {(base.provider, base.model)}
  for item in load_fallback_entries(params):
    provider = str(item.get("provider") or base.provider).strip()
    model = str(item.get("model") or "").strip()
    if not model:
      continue
    key = (provider, model)
    if key in seen:
      continue
    seen.add(key)
    out.append(AIConfig(
      provider=provider,
      model=model,
      api_key=str(item.get("apiKey") or item.get("api_key") or base.api_key),
      base_url=str(item.get("baseUrl") or item.get("base_url") or base.base_url or ""),
      system_prompt=base.system_prompt,
      temperature=base.temperature,
      top_p=base.top_p,
      max_tokens=base.max_tokens,
      thinking_enabled=base.thinking_enabled,
      thinking_keep=base.thinking_keep,
    ))
  return out


def resolve_chat_config(
  base: AIConfig,
  params,
  *,
  workflow_id: str = "",
  user_text: str = "",
  body: dict[str, Any] | None = None,
) -> AIConfig:
  """Return the primary chat config."""
  del workflow_id, user_text, body
  return base


def resolve_chat_config_chain(
  base: AIConfig,
  params,
  *,
  workflow_id: str = "",
  user_text: str = "",
  body: dict[str, Any] | None = None,
) -> list[AIConfig]:
  """Primary config followed by fallback profiles from ai_model_fallbacks."""
  del workflow_id, user_text, body
  return [base, *_parse_fallbacks(params, base)]


async def chat_completion_with_failover(
  base: AIConfig,
  params,
  messages: list[dict[str, Any]],
  tools: list[dict[str, Any]] | None = None,
  *,
  body: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[ChatChunk, AIConfig]]:
  """Stream completion; retry next config on error before any output."""
  last_error = ""
  for cfg in resolve_chat_config_chain(base, params, body=body):
    emitted = False
    async for chunk in chat_completion(cfg, messages, tools=tools):
      if chunk.error:
        if not emitted:
          last_error = chunk.error
          break
        yield chunk, cfg
        return
      emitted = True
      yield chunk, cfg
    if emitted:
      return
  yield ChatChunk(error=last_error or "All configured models failed"), base
