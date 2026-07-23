"""Session compaction — summarize long conversations into memory."""

from __future__ import annotations

import json
from typing import Any

from openpilot.common.params import Params

from ai.client import AIConfig, chat_completion_collect
from ai.tools.memory_store import append_note

COMPACT_AFTER_USER_TURNS = 24
_KEEP_RECENT_USER_TURNS = 8


def _count_user_turns(messages: list[dict[str, Any]]) -> int:
  return sum(1 for m in messages if m.get("role") == "user")


def _split_for_compaction(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  """Return (to_compact, to_keep). Keeps last N user turns and following assistant/tool msgs."""
  if not messages:
    return [], []
  user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
  if len(user_indices) <= _KEEP_RECENT_USER_TURNS:
    return [], messages
  cut_idx = user_indices[-_KEEP_RECENT_USER_TURNS]
  return messages[:cut_idx], messages[cut_idx:]


def _message_text(content: Any) -> str:
  if isinstance(content, str):
    return content
  if isinstance(content, list):
    parts = []
    for p in content:
      if isinstance(p, dict) and p.get("type") == "text":
        parts.append(str(p.get("text") or ""))
    return " ".join(parts)
  return str(content or "")


async def maybe_compact_messages(
  messages: list[dict[str, Any]],
  params: Params,
  config: AIConfig,
  *,
  session_id: str = "",
  force: bool = False,
) -> list[dict[str, Any]]:
  """If conversation is long, summarize older turns and store in memory."""
  if not force and _count_user_turns(messages) < COMPACT_AFTER_USER_TURNS:
    return messages

  old_msgs, keep_msgs = _split_for_compaction(messages)
  if not old_msgs and not force:
    return messages
  if force and not old_msgs:
    old_msgs, keep_msgs = messages[:-2], messages[-2:] if len(messages) > 2 else ([], messages)

  transcript_lines: list[str] = []
  for m in old_msgs[-40:]:
    role = m.get("role", "?")
    text = _message_text(m.get("content"))
    if text:
      transcript_lines.append(f"{role}: {text[:800]}")
  if not transcript_lines:
    return messages

  prompt = (
    "Summarize this openpilot assistant conversation for long-term memory. "
    "Focus on vehicle issues, tuning decisions, file paths, and user preferences. "
    "Use concise bullet points in Chinese when the user wrote in Chinese.\n\n"
    + "\n".join(transcript_lines)
  )
  content, _, err = await chat_completion_collect(
    config,
    [
      {"role": "system", "content": "You produce compact session summaries for an automotive AI assistant."},
      {"role": "user", "content": prompt},
    ],
    max_tokens=1200,
    timeout_total=90,
  )
  if err or not content.strip():
    return messages

  tags = ["compaction"]
  if session_id:
    tags.append(f"session:{session_id[:12]}")
  append_note(params, f"[会话摘要]\n{content.strip()}", tags=tags)

  summary_msg = {
    "role": "system",
    "content": (
      "[Earlier conversation summarized and saved to memory]\n"
      + content.strip()
    ),
  }
  return [summary_msg] + keep_msgs


def compaction_status(messages: list[dict[str, Any]]) -> dict[str, Any]:
  turns = _count_user_turns(messages)
  return {
    "userTurns": turns,
    "compactAfter": COMPACT_AFTER_USER_TURNS,
    "needsCompaction": turns >= COMPACT_AFTER_USER_TURNS,
  }
