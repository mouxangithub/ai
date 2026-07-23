"""SQLite FTS5 index for cross-session conversation search."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from openpilot.common.params import Params

from ai.common.storage import read_param
from ai.tools.session_store import SESSIONS_KEY, get_sessions

_LOCK = threading.Lock()
_DB: sqlite3.Connection | None = None

SESSIONS_DB = Path(__file__).resolve().parent.parent / "data" / "session_index.db"


def _conn() -> sqlite3.Connection:
  global _DB
  if _DB is not None:
    return _DB
  SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
  _DB = sqlite3.connect(str(SESSIONS_DB), check_same_thread=False)
  _DB.execute("PRAGMA journal_mode=WAL")
  _DB.execute(
    """
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      session_title TEXT,
      role TEXT NOT NULL,
      text TEXT NOT NULL,
      ts INTEGER NOT NULL
    )
    """
  )
  _DB.execute(
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
      session_id, session_title, role, text, content='messages', content_rowid='id'
    )
    """
  )
  _DB.commit()
  return _DB


def _message_text(content: Any) -> str:
  if isinstance(content, str):
    return content.strip()
  if isinstance(content, list):
    parts = []
    for p in content:
      if isinstance(p, dict) and p.get("type") == "text":
        parts.append(str(p.get("text") or ""))
    return " ".join(parts).strip()
  return str(content or "").strip()


def index_session(session: dict[str, Any]) -> int:
  sid = str(session.get("id") or "")
  if not sid:
    return 0
  title = str(session.get("title") or session.get("preview") or sid)[:120]
  now = int(time.time())
  count = 0
  with _LOCK:
    conn = _conn()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    for msg in session.get("messages") or []:
      if not isinstance(msg, dict):
        continue
      role = str(msg.get("role") or "")
      text = _message_text(msg.get("content"))
      if not text or role not in ("user", "assistant", "system"):
        continue
      conn.execute(
        "INSERT INTO messages(session_id, session_title, role, text, ts) VALUES (?,?,?,?,?)",
        (sid, title, role, text[:4000], now),
      )
      count += 1
    conn.commit()
    _rebuild_fts(conn)
  return count


def _rebuild_fts(conn: sqlite3.Connection) -> None:
  conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")


def rebuild_from_params(params: Params | None = None) -> dict[str, Any]:
  params = params or Params()
  data = get_sessions(params)
  total = 0
  for session in data.get("sessions") or []:
    total += index_session(session)
  return {"ok": True, "sessions": len(data.get("sessions") or []), "messagesIndexed": total}


def search_sessions(query: str, *, limit: int = 8) -> dict[str, Any]:
  q = (query or "").strip()
  if not q:
    return {"ok": True, "hits": []}
  with _LOCK:
    conn = _conn()
    rows = conn.execute(
      """
      SELECT m.session_id, m.session_title, m.role, snippet(messages_fts, 3, '…', '…', 12, 64) AS snip, m.ts
      FROM messages_fts f
      JOIN messages m ON m.id = f.rowid
      WHERE messages_fts MATCH ?
      ORDER BY rank
      LIMIT ?
      """,
      (q, limit),
    ).fetchall()
  hits = [
    {
      "sessionId": r[0],
      "sessionTitle": r[1],
      "role": r[2],
      "snippet": r[3],
      "ts": r[4],
    }
    for r in rows
  ]
  return {"ok": True, "query": q, "hits": hits}


def list_sessions_brief(params: Params | None = None, *, limit: int = 20) -> dict[str, Any]:
  data = get_sessions(params or Params())
  sessions = []
  for s in (data.get("sessions") or [])[:limit]:
    sessions.append({
      "id": s.get("id"),
      "title": s.get("title") or s.get("preview") or "",
      "updatedAt": s.get("updatedAt"),
      "messageCount": len(s.get("messages") or []),
    })
  return {"ok": True, "activeId": data.get("activeId"), "sessions": sessions}


def get_session_history(params: Params, session_id: str, *, limit: int = 40) -> dict[str, Any]:
  data = get_sessions(params)
  for s in data.get("sessions") or []:
    if s.get("id") == session_id:
      msgs = []
      for m in (s.get("messages") or [])[-limit:]:
        if not isinstance(m, dict):
          continue
        msgs.append({
          "role": m.get("role"),
          "content": _message_text(m.get("content"))[:2000],
        })
      return {"ok": True, "sessionId": session_id, "title": s.get("title"), "messages": msgs}
  return {"ok": False, "error": f"Session {session_id} not found"}


def append_to_session_index(session_id: str, role: str, content: Any, *, title: str = "") -> None:
  text = _message_text(content)
  if not text or not session_id:
    return
  with _LOCK:
    conn = _conn()
    conn.execute(
      "INSERT INTO messages(session_id, session_title, role, text, ts) VALUES (?,?,?,?,?)",
      (session_id, title[:120], role, text[:4000], int(time.time())),
    )
    conn.commit()
    rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
      "INSERT INTO messages_fts(rowid, session_id, session_title, role, text) VALUES (?,?,?,?,?)",
      (rowid, session_id, title[:120], role, text[:4000]),
    )
    conn.commit()
