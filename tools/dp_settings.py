"""Compatibility shim — use sp_settings for sunnypilot."""

from ai.tools.sp_settings import list_dp_settings, list_sp_settings

__all__ = ["list_dp_settings", "list_sp_settings"]
