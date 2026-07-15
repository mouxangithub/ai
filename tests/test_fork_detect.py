"""Tests for fork detection."""

from __future__ import annotations

import unittest
from pathlib import Path

from ai.fork.detect_fork import detect_fork, list_profiles
from ai.install.integrate_openpilot import collect_ai_params


class TestDetectFork(unittest.TestCase):
  def test_list_profiles(self):
    profiles = list_profiles()
    self.assertGreaterEqual(len(profiles), 3)
    ids = {p.get("id") for p in profiles}
    self.assertIn("dragonpilot", ids)
    self.assertIn("openpilot", ids)

  def test_detect_dragonpilot_tree(self):
    root = Path(__file__).resolve().parents[2]
    out = detect_fork(root)
    self.assertTrue(out.get("ok"))
    self.assertIn(out.get("fork_id"), ("dragonpilot", "openpilot", "carrotpilot", "sunnypilot", "iqpilot"))


class TestIntegrateParams(unittest.TestCase):
  def test_collect_ai_params(self):
    ai_dir = Path(__file__).resolve().parents[1]
    params = collect_ai_params(ai_dir)
    self.assertIn("ai_provider", params)
    self.assertIn("ai_first_run_done", params)
    self.assertIn("ai_timezone", params)


if __name__ == "__main__":
  unittest.main()
