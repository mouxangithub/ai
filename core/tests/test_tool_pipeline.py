"""Tests for ai.core.tools.pipeline."""

import asyncio
import unittest

from ai.core.tools.pipeline import ToolDefinition, ToolPipeline


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
