"""
Tool domain index — maps builtin agents to tool modules (progressive packaging).

Domains:
  core      — agent_tools.py, diagnostics, memory, rag
  tune      — presets, tune_*, maneuver_*, route_scoring
  vehicle   — vehicle_platform, mads, sp_settings, car_porting
  can       — cabana, adaptation, dbc
  secoc     — tsk_*, secoc_lookup
  devops    — git_*, github_*, ota_*, branch
  cloud     — konik_*, sunnylink_*, comma_cloud
  pc        — pc_dev_tools, devops_tools
  media     — route_media, route_analysis, vision
"""

from __future__ import annotations

DOMAIN_MODULES: dict[str, list[str]] = {
  "core": [
    "ai.tools.agent_tools",
    "ai.tools.diagnostics_tools",
    "ai.tools.memory_store",
    "ai.tools.rag_store",
  ],
  "tune": [
    "ai.tools.presets",
    "ai.tools.sp_presets",
    "ai.tools.tune_snapshot_store",
    "ai.tools.route_scoring_tools",
    "ai.tools.maneuver_tools",
  ],
  "vehicle": [
    "ai.tools.vehicle_platform",
    "ai.tools.mads_tools",
    "ai.tools.sp_settings",
    "ai.tools.car_porting_tools",
  ],
  "can": [
    "ai.cabana",
    "ai.tools.adaptation",
    "ai.tools.fingerprint_lib",
  ],
  "secoc": [
    "ai.tools.tsk_tools",
    "ai.tools.secoc_lookup",
  ],
  "devops": [
    "ai.tools.git_tools",
    "ai.tools.github_actions_tools",
    "ai.tools.branch_tools",
    "ai.tools.ota_tools",
  ],
  "cloud": [
    "ai.tools.konik_connect_tools",
    "ai.tools.sunnylink_tools",
    "ai.tools.comma_cloud_tools",
  ],
  "pc": [
    "ai.tools.pc_dev_tools",
    "ai.tools.devops_tools",
  ],
  "media": [
    "ai.tools.route_tools",
    "ai.tools.route_analysis_tools",
    "ai.tools.route_media_tools",
  ],
}

AGENT_DOMAINS: dict[str, list[str]] = {
  "triage": ["core", "tune", "secoc"],
  "tune": ["tune"],
  "route": ["media", "tune"],
  "adapt": ["can", "tune"],
  "secoc": ["secoc", "tune"],
  "devops": ["devops"],
  "cloud": ["cloud"],
  "pc": ["pc", "media"],
}


def domain_module_names(domain: str) -> list[str]:
  from ai.tools.domains import core, tune, devops
  mapping = {
    "core": core.MODULES,
    "tune": tune.MODULES,
    "devops": devops.MODULES,
    "vehicle": tune.MODULES,
    "can": ("ai.cabana", "ai.tools.adaptation", "ai.tools.fingerprint_lib"),
    "secoc": ("ai.tools.tsk_tools", "ai.tools.secoc_lookup"),
    "cloud": ("ai.tools.konik_connect_tools", "ai.tools.sunnylink_tools", "ai.tools.comma_cloud_tools"),
    "pc": ("ai.tools.pc_dev_tools", "ai.tools.devops_tools"),
    "media": ("ai.tools.route_tools", "ai.tools.route_analysis_tools", "ai.tools.route_media_tools"),
  }
  return list(mapping.get(domain, ()))
