"""Skill domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

SkillId = str
SkillPolicy = Literal["auto", "confirm", "disabled"]
SkillInvocationStatus = Literal["pending", "allowed", "denied", "running", "success", "error"]
SkillErrorCode = Literal[
  "SKILL_NOT_FOUND",
  "SKILL_DISABLED",
  "SKILL_REQUIRES_CONFIRMATION",
  "SKILL_INVALID_ARGS",
  "SKILL_EXECUTION_ERROR",
]


class SkillError(Exception):
  def __init__(self, message: str, code: SkillErrorCode) -> None:
    super().__init__(message)
    self.message = message
    self.code = code

  def to_dict(self) -> dict[str, Any]:
    return {"ok": False, "error": self.message, "code": self.code}


@dataclass(frozen=True)
class SkillParameter:
  name: str
  type: str
  description: str
  required: bool = True

  def to_dict(self) -> dict[str, Any]:
    return {
      "name": self.name,
      "type": self.type,
      "description": self.description,
      "required": self.required,
    }

  @staticmethod
  def from_dict(data: dict[str, Any]) -> SkillParameter:
    return SkillParameter(
      name=str(data.get("name", "")),
      type=str(data.get("type", "string")),
      description=str(data.get("description", "")),
      required=bool(data.get("required", True)),
    )


@dataclass
class Skill:
  id: SkillId
  name: str
  description: str
  policy: SkillPolicy
  parameters: list[SkillParameter]
  handler: Callable[..., Any] | None = field(default=None, compare=False, repr=False)
  metadata: dict[str, Any] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return {
      "id": self.id,
      "name": self.name,
      "description": self.description,
      "policy": self.policy,
      "parameters": [p.to_dict() for p in self.parameters],
      "metadata": dict(self.metadata),
    }

  @staticmethod
  def from_dict(data: dict[str, Any], handler: Callable[..., Any] | None = None) -> Skill:
    return Skill(
      id=str(data.get("id", "")),
      name=str(data.get("name", "")),
      description=str(data.get("description", "")),
      policy=str(data.get("policy", "confirm")),
      parameters=[SkillParameter.from_dict(p) for p in data.get("parameters", [])],
      handler=handler,
      metadata=dict(data.get("metadata") or {}),
    )


@dataclass
class SkillInvocation:
  skill_id: SkillId
  args: dict[str, Any]
  status: SkillInvocationStatus
  result: Any = None
  error: str | None = None
  request_id: str = ""

  def to_dict(self) -> dict[str, Any]:
    return {
      "skillId": self.skill_id,
      "args": dict(self.args),
      "status": self.status,
      "result": self.result,
      "error": self.error,
      "requestId": self.request_id,
    }

  @staticmethod
  def from_dict(data: dict[str, Any]) -> SkillInvocation:
    return SkillInvocation(
      skill_id=str(data.get("skillId", data.get("skill_id", ""))),
      args=dict(data.get("args") or {}),
      status=str(data.get("status", "pending")),
      result=data.get("result"),
      error=data.get("error") if data.get("error") else None,
      request_id=str(data.get("requestId", data.get("request_id", ""))),
    )
