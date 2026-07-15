"""Detect which openpilot community fork is installed."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

AI_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = AI_DIR / "fork-profiles"


def _run_git(args: list[str], *, cwd: Path) -> str | None:
  try:
    proc = subprocess.run(
      ["git", *args],
      cwd=str(cwd),
      capture_output=True,
      text=True,
      timeout=20,
    )
  except (OSError, subprocess.TimeoutExpired):
    return None
  if proc.returncode != 0:
    return None
  return (proc.stdout or "").strip()


def _load_profile(path: Path) -> dict[str, Any]:
  data = json.loads(path.read_text(encoding="utf-8"))
  data.setdefault("id", path.stem)
  data["profile_path"] = str(path)
  return data


def list_profiles() -> list[dict[str, Any]]:
  if not PROFILES_DIR.is_dir():
    return []
  out: list[dict[str, Any]] = []
  for path in sorted(PROFILES_DIR.glob("*.json")):
    try:
      out.append(_load_profile(path))
    except Exception:
      continue
  return out


def _git_remotes(root: Path) -> list[str]:
  text = _run_git(["remote", "-v"], cwd=root)
  if not text:
    return []
  remotes: list[str] = []
  for line in text.splitlines():
    parts = line.split()
    if len(parts) >= 2:
      remotes.append(parts[1].lower())
  return remotes


def _git_branch(root: Path) -> str | None:
  return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)


def _score_profile(profile: dict[str, Any], root: Path, remotes: list[str]) -> tuple[int, list[str]]:
  score = 0
  reasons: list[str] = []
  remote_patterns = [p.lower() for p in profile.get("remotes", [])]
  for remote in remotes:
    for pat in remote_patterns:
      if pat in remote:
        score += 50
        reasons.append(f"remote match: {pat}")
  for rel in profile.get("markers", {}).get("paths", []):
    if (root / rel).exists():
      score += 20
      reasons.append(f"marker: {rel}")
  for rel in profile.get("markers", {}).get("files", []):
    if (root / rel).is_file():
      score += 15
      reasons.append(f"file: {rel}")
  content_markers = profile.get("markers", {}).get("file_contains", [])
  for item in content_markers:
    rel = item.get("path", "")
    needle = item.get("contains", "")
    path = root / rel
    if path.is_file() and needle and needle in path.read_text(encoding="utf-8", errors="replace"):
      score += 10
      reasons.append(f"contains: {rel}")
  return score, reasons


def detect_fork(root: Path | None = None) -> dict[str, Any]:
  if root is None:
    from ai.system.paths import openpilot_root

    root = openpilot_root()
  root = root.resolve()
  profiles = list_profiles()
  remotes = _git_remotes(root)
  branch = _git_branch(root)

  best: dict[str, Any] | None = None
  best_score = -1
  best_reasons: list[str] = []
  scored: list[dict[str, Any]] = []

  for profile in profiles:
    score, reasons = _score_profile(profile, root, remotes)
    entry = {"id": profile.get("id"), "label": profile.get("label"), "score": score, "reasons": reasons}
    scored.append(entry)
    if score > best_score:
      best_score = score
      best = profile
      best_reasons = reasons

  fork_id = "openpilot"
  label = "openpilot"
  confidence = "low"
  if best and best_score >= 15:
    fork_id = str(best.get("id", "openpilot"))
    label = str(best.get("label", fork_id))
    confidence = "high" if best_score >= 50 else "medium"

  return {
    "ok": True,
    "openpilot_root": str(root),
    "fork_id": fork_id,
    "fork_label": label,
    "confidence": confidence,
    "score": best_score,
    "reasons": best_reasons,
    "git_branch": branch,
    "git_remotes": remotes[:6],
    "profile": {
      "id": best.get("id") if best else None,
      "label": best.get("label") if best else None,
      "path": best.get("profile_path") if best else None,
      "skills": (best or {}).get("skills", []),
      "docs": (best or {}).get("docs", []),
    },
    "candidates": sorted(scored, key=lambda x: x["score"], reverse=True),
  }


def profile_for_fork(fork_id: str) -> dict[str, Any] | None:
  path = PROFILES_DIR / f"{fork_id}.json"
  if path.is_file():
    return _load_profile(path)
  return None
