"""Generate fork-specific skill/doc drafts from AI repo analysis (human review required)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai.fork.analyze_fork import analyze_fork_with_ai, load_cached_analysis
from ai.fork.repo_scan import compact_scan_for_api, derive_fork_identity, scan_openpilot_repo

AI_DIR = Path(__file__).resolve().parent.parent
DRAFTS_DIR = AI_DIR / "data" / "fork_drafts"


def _slug_for_drafts(identity: dict[str, Any], analysis: dict[str, Any] | None) -> str:
  if analysis and analysis.get("fork_identity"):
    return re.sub(r"[^\w./-]+", "-", str(analysis["fork_identity"]))[:80]
  return re.sub(r"[^\w./-]+", "-", str(identity.get("fork_id", "fork")))[:80]


def _draft_paths(slug: str) -> dict[str, Path]:
  base = DRAFTS_DIR / slug.replace("/", "__")
  return {
    "base": base,
    "skill": base / "FORK_SKILL.md",
    "tools": base / "tools_notes.md",
    "manifest": base / "manifest.json",
  }


def build_fork_context(root: Path, analysis_payload: dict[str, Any] | None = None) -> dict[str, Any]:
  scan = scan_openpilot_repo(root)
  identity = derive_fork_identity(scan)
  analysis = (analysis_payload or {}).get("analysis")
  return {
    "identity": identity,
    "scan": compact_scan_for_api(scan),
    "analysis": analysis,
    "fork_id": _slug_for_drafts(identity, analysis),
    "fork_label": (analysis or {}).get("fork_name") or identity.get("fork_label"),
  }


async def generate_fork_drafts(
  params: Any,
  *,
  openpilot_root: Path | None = None,
  force_analyze: bool = False,
) -> dict[str, Any]:
  """Run AI repo analysis (if needed) then draft skill/doc notes."""
  from ai.client import chat_completion_collect, load_config_from_params
  from ai.system.paths import openpilot_root as default_root

  root = openpilot_root or default_root()
  config = load_config_from_params(params)
  if not config.is_configured:
    return {"ok": False, "error": config.configuration_error or "AI not configured"}

  analysis_result = await analyze_fork_with_ai(params, root, force=force_analyze)
  if not analysis_result.get("ok"):
    return analysis_result

  ctx = build_fork_context(root, analysis_result)
  slug = ctx["fork_id"]
  paths = _draft_paths(slug)
  paths["base"].mkdir(parents=True, exist_ok=True)

  system = (
    "你是 op助手 维护者助手。根据 AI 仓库分析结果，撰写可人工审核的技能草稿与工具说明。"
    "不要自动执行写参；强调安全与停车 offroad。"
  )
  user = f"""基于以下 fork 分析，输出两段 Markdown：

### Section A: FORK_SKILL
YAML frontmatter + 技能正文：本 fork 的调参 Param、工作流、与 op助手 工具的配合。

### Section B: TOOLS_NOTES
bullet 列表：建议更新哪些技能/工具/文档（仅建议，不写代码）。

## 上下文
```json
{json.dumps(ctx, ensure_ascii=False, indent=2)[:14000]}
```
"""

  text, _r, err = await chat_completion_collect(
    config,
    [{"role": "system", "content": system}, {"role": "user", "content": user}],
    timeout_total=240,
  )
  if err:
    return {"ok": False, "error": err, "fork_id": slug, "analysis": analysis_result.get("analysis")}

  skill_part = text
  tools_part = ""
  if "### Section B" in text:
    parts = re.split(r"### Section B:\s*TOOLS_NOTES\s*", text, maxsplit=1)
    skill_part = re.sub(r"^### Section A:.*?\n", "", parts[0], flags=re.S).strip()
    tools_part = parts[1].strip() if len(parts) > 1 else ""

  paths["skill"].write_text(skill_part.strip() + "\n", encoding="utf-8")
  paths["tools"].write_text(tools_part.strip() + "\n", encoding="utf-8")
  manifest = {
    "fork_id": slug,
    "fork_label": ctx.get("fork_label"),
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "model": config.model,
    "provider": config.provider,
    "git_commit": analysis_result.get("git_commit"),
    "paths": {k: str(v) for k, v in paths.items()},
    "analysis_summary": (analysis_result.get("analysis") or {}).get("summary"),
  }
  paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

  return {
    "ok": True,
    "fork_id": slug,
    "fork_label": ctx.get("fork_label"),
    "draft_dir": str(paths["base"]),
    "skill_draft": str(paths["skill"]),
    "tools_notes": str(paths["tools"]),
    "manifest": manifest,
    "analysis": analysis_result.get("analysis"),
    "preview": skill_part[:1500],
  }


def list_fork_drafts() -> list[dict[str, Any]]:
  if not DRAFTS_DIR.is_dir():
    return []
  out: list[dict[str, Any]] = []
  for manifest_path in sorted(DRAFTS_DIR.glob("*/manifest.json")):
    try:
      out.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    except Exception:
      continue
  return out
