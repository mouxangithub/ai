"""Skill registry with policy-aware invocation."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from ai.skill.models import (
  Skill,
  SkillError,
  SkillInvocation,
  SkillParameter,
  SkillPolicy,
)

_SKILL_BASE_DIR: Path | None = None


def set_skill_base_dir(path: Path | str) -> None:
  global _SKILL_BASE_DIR
  _SKILL_BASE_DIR = Path(path)


def get_skill_registry() -> SkillRegistry:
  base = _SKILL_BASE_DIR
  if base is None:
    from ai.system.paths import workspace_path
    base = Path(workspace_path()) / "ai_skills"
  return SkillRegistry(base)


class SkillRegistry:
  """In-memory skill registry with JSON manifest persistence."""

  def __init__(self, base_dir: Path | str) -> None:
    self.base_dir = Path(base_dir)
    self.base_dir.mkdir(parents=True, exist_ok=True)
    self._lock = threading.RLock()
    self._skills: dict[str, Skill] = {}
    self._load_manifest()

  @property
  def _manifest_path(self) -> Path:
    return self.base_dir / "manifest.json"

  def _load_manifest(self) -> None:
    if not self._manifest_path.exists():
      return
    try:
      with open(self._manifest_path, encoding="utf-8") as f:
        data = json.load(f)
      for item in data.get("skills", []):
        self._skills[item["id"]] = Skill.from_dict(item)
    except (json.JSONDecodeError, OSError, KeyError):
      pass

  def _save_manifest(self) -> None:
    data = {"skills": [s.to_dict() for s in self._skills.values()]}
    tmp = self._manifest_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=2)
      f.flush()
      os.fsync(f.fileno())
    tmp.replace(self._manifest_path)

  def register(
    self,
    skill: Skill,
    handler: Callable[..., Any] | None = None,
  ) -> Skill:
    if handler is not None:
      skill.handler = handler
    with self._lock:
      self._skills[skill.id] = skill
      self._save_manifest()
    return skill

  def register_from_dict(
    self,
    data: dict[str, Any],
    handler: Callable[..., Any] | None = None,
  ) -> Skill:
    skill = Skill.from_dict(data, handler=handler)
    return self.register(skill)

  def unregister(self, skill_id: str) -> bool:
    with self._lock:
      removed = self._skills.pop(skill_id, None) is not None
      if removed:
        self._save_manifest()
    return removed

  def get(self, skill_id: str) -> Skill:
    with self._lock:
      skill = self._skills.get(skill_id)
    if skill is None:
      raise SkillError(f"skill {skill_id} not found", "SKILL_NOT_FOUND")
    return skill

  def list_skills(self) -> list[Skill]:
    with self._lock:
      return list(self._skills.values())

  def _validate_args(self, skill: Skill, args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for param in skill.parameters:
      if param.name in args:
        out[param.name] = args[param.name]
      elif param.required:
        raise SkillError(
          f"missing required parameter {param.name}",
          "SKILL_INVALID_ARGS",
        )
    return out

  def request_invocation(
    self,
    skill_id: str,
    args: dict[str, Any],
    request_id: str | None = None,
    auto_confirm: bool = False,
  ) -> SkillInvocation:
    """Policy-aware invocation. Returns pending for confirm skills unless auto_confirm."""
    skill = self.get(skill_id)
    if skill.policy == "disabled":
      raise SkillError(f"skill {skill_id} is disabled", "SKILL_DISABLED")

    validated = self._validate_args(skill, args)
    invocation = SkillInvocation(
      skill_id=skill_id,
      args=validated,
      status="pending",
      request_id=request_id or uuid.uuid4().hex,
    )

    if skill.policy == "confirm" and not auto_confirm:
      invocation.status = "pending"
      return invocation

    return self._execute(skill, invocation)

  def _execute(self, skill: Skill, invocation: SkillInvocation) -> SkillInvocation:
    if skill.handler is None:
      invocation.status = "error"
      invocation.error = f"skill {skill.id} has no handler"
      return invocation
    invocation.status = "running"
    try:
      invocation.result = skill.handler(**invocation.args)
      invocation.status = "success"
    except Exception as e:
      invocation.status = "error"
      invocation.error = str(e)
    return invocation

  def confirm_invocation(self, request_id: str) -> SkillInvocation | None:
    """Synchronous confirmation placeholder; real flow would persist pending requests."""
    return None

  def build_tool_definitions(self) -> list[dict[str, Any]]:
    """Return OpenAI-style function definitions for registered skills."""
    tools = []
    for skill in self.list_skills():
      if skill.policy == "disabled":
        continue
      properties: dict[str, Any] = {}
      required: list[str] = []
      for param in skill.parameters:
        properties[param.name] = {
          "type": param.type,
          "description": param.description,
        }
        if param.required:
          required.append(param.name)
      tools.append({
        "type": "function",
        "function": {
          "name": skill.id,
          "description": skill.description,
          "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
          },
        },
      })
    return tools
