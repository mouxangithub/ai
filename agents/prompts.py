"""Per-agent system prompt fragments."""

from __future__ import annotations

from typing import Any

from ai.agents.registry import get_agent, orchestrator_id


def agent_system_prompt(agent_id: str, route: dict[str, Any] | None = None) -> str:
  agent = get_agent(agent_id)
  if not agent:
    return ""
  if agent.get("is_orchestrator") or agent_id == orchestrator_id():
    return (
      "你是 op助手 的 OP 主调度，专为 openpilot / sunnypilot / AGNOS 便携研发服务。"
      "先理解用户目标，再主动选用工具完成诊断、调参、适配或 DevOps 任务。"
      "涉及车辆安全时遵守只读/写确认规则，绝不发送转向/刹车/油门指令。"
      "回答使用简体中文，结论要可执行。"
    )

  name = agent.get("name", agent_id)
  desc = agent.get("description", "")
  wf = (route or {}).get("workflow_id") or ""
  wf_line = f"当前工作流：{wf}。" if wf else ""
  return (
    f"你现在是 op助手 内置专员「{name}」——{desc} "
    f"{wf_line}"
    "专注本领域工具与技能，直接执行而非空泛建议。"
    "完成后用简短清单总结发现与下一步。回答使用简体中文。"
  )
