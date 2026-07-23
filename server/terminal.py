"""Interactive web terminal — PTY bridge (Hermes-inspired, AGNOS/Linux)."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import sys
from typing import Any

from aiohttp import web

from openpilot.common.swaglog import cloudlog

from ai.system.paths import openpilot_root


_RESIZE_PREFIX = "\x1b[RESIZE:"
_sessions: dict[str, dict[str, Any]] = {}


def _shell_command() -> list[str]:
  if platform.system() == "Windows":
    return ["powershell.exe", "-NoLogo"]
  bash = shutil.which("bash") or "/bin/bash"
  return [bash, "--login"]


async def _pty_available() -> bool:
  return platform.system() != "Windows" and os.name == "posix"


async def terminal_ws(request: web.Request) -> web.WebSocketResponse:
  params = request.app.get("params")
  if not await _pty_available():
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.send_str(
      "PTY terminal requires Linux/macOS (AGNOS). "
      "On Windows dev, use WSL or the AI shell tools.\r\n"
    )
    await ws.close()
    return ws

  import pty
  import termios
  import fcntl
  import struct

  ws = web.WebSocketResponse(heartbeat=30.0)
  await ws.prepare(request)
  cloudlog.info("aid: terminal ws connected")
  await ws.send_str(
    "\x1b[33mop助手终端\x1b[0m — Shell + AI（自然语言或 ? 前缀调用 op助手）；"
    "行驶中可用诊断命令；禁止转向/刹车/油门等控车操作。\r\n"
  )

  master_fd, slave_fd = pty.openpty()
  env = os.environ.copy()
  env["TERM"] = "xterm-256color"
  env["PWD"] = str(openpilot_root())
  proc = await asyncio.create_subprocess_exec(
    *_shell_command(),
    stdin=slave_fd,
    stdout=slave_fd,
    stderr=slave_fd,
    cwd=str(openpilot_root()),
    env=env,
    preexec_fn=os.setsid,
  )
  os.close(slave_fd)

  loop = asyncio.get_event_loop()

  def _set_winsize(cols: int, rows: int) -> None:
    try:
      winsize = struct.pack("HHHH", rows, cols, 0, 0)
      fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except Exception:
      pass

  async def _read_pty() -> None:
    try:
      while True:
        data = await loop.run_in_executor(None, os.read, master_fd, 4096)
        if not data:
          break
        await ws.send_bytes(data)
    except Exception:
      pass

  reader_task = asyncio.create_task(_read_pty())

  try:
    async for msg in ws:
      if msg.type == web.WSMsgType.BINARY:
        os.write(master_fd, msg.data)
      elif msg.type == web.WSMsgType.TEXT:
        text = msg.data or ""
        if text.startswith(_RESIZE_PREFIX) and text.endswith("]"):
          try:
            inner = text[len(_RESIZE_PREFIX):-1]
            cols_s, rows_s = inner.split(";", 1)
            _set_winsize(int(cols_s), int(rows_s))
          except Exception:
            pass
          continue
        os.write(master_fd, text.encode("utf-8", errors="replace"))
      elif msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.CLOSED, web.WSMsgType.ERROR):
        break
  finally:
    reader_task.cancel()
    try:
      os.close(master_fd)
    except Exception:
      pass
    if proc.returncode is None:
      proc.terminate()
      try:
        await asyncio.wait_for(proc.wait(), timeout=2)
      except asyncio.TimeoutError:
        proc.kill()
    cloudlog.info("aid: terminal ws disconnected")
  return ws


def register_terminal_routes(app: web.Application) -> None:
  app.router.add_get("/api/ai/terminal/ws", terminal_ws)
