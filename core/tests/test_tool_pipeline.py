"""Tests for ai.core.tools.pipeline."""

import asyncio
import unittest

from ai.core.tools.pipeline import (
  ToolDefinition,
  ToolPipeline,
  ToolResult,
  build_tool_result,
  classify_result_kind,
  truncate_content_head_tail,
)


class ToolPipelineTestCase(unittest.TestCase):
  def test_unknown_tool(self):
    pipeline = ToolPipeline()
    result = asyncio.run(pipeline.execute("id", "missing", "{}"))
    self.assertFalse(result["ok"])
    self.assertIn("not implemented", result["error"])

  def test_sync_tool(self):
    pipeline = ToolPipeline()
    pipeline.register(ToolDefinition(
      name="echo",
      description="echo",
      parameters={"type": "object", "properties": {}},
      handler=lambda args: {"ok": True, "echo": args.get("x")},
    ))
    result = asyncio.run(pipeline.execute("id", "echo", '{"x": 1}'))
    self.assertTrue(result["ok"])
    self.assertEqual(result["echo"], 1)

  def test_structured_result_and_utf8_retention(self):
    self.assertEqual(classify_result_kind({"ok": True, "content": "文本"}), "content")
    self.assertEqual(build_tool_result(3).value, 3)
    retained = truncate_content_head_tail("头" * 50 + "尾" * 50, 32)
    self.assertLessEqual(len(retained.encode("utf-8")), 32)
    self.assertIn("truncated", retained)

  def test_post_waterfall_runs_inner_to_outer(self):
    pipeline = ToolPipeline({"echo": lambda args: {"ok": True, "value": "x"}})
    calls = []

    async def outer(ctx, result, next_stage):
      calls.append("outer-before")
      result = await next_stage()
      calls.append("outer-after")
      result.value["outer"] = True
      return result

    async def inner(ctx, result, next_stage):
      calls.append("inner-before")
      result = await next_stage()
      calls.append("inner-after")
      result.value["inner"] = True
      return result

    pipeline.add_post_waterfall(outer)
    pipeline.add_post_waterfall(inner)
    result = asyncio.run(pipeline.execute("id", "echo", "{}"))
    self.assertTrue(result["outer"])
    self.assertTrue(result["inner"])
    self.assertEqual(calls, ["outer-before", "inner-before", "inner-after", "outer-after"])

  def test_guard_blocks(self):
    pipeline = ToolPipeline()

    def guard(args):
      if args.get("x") == 1:
        return "blocked"
      return None

    pipeline.register(ToolDefinition(
      name="gated",
      description="gated",
      parameters={"type": "object", "properties": {}},
      handler=lambda args: {"ok": True},
      guard=guard,
    ))
    result = asyncio.run(pipeline.execute("id", "gated", '{"x": 1}'))
    self.assertFalse(result["ok"])
    self.assertEqual(result["error"], "blocked")


if __name__ == "__main__":
  unittest.main()
