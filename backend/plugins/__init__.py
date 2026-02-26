"""Plugin management module for SunnyAgent.

This module provides:
- Unified plugin management (agents and skills)
- User-level plugin state (enable/disable)
- Plugin upload and sharing
- Rating system for package/shared plugins
"""

from backend.plugins.models import (
    CommandInfo,
    PluginInfo,
    PluginRatingInfo,
    PluginRatingRequest,
    PluginSource,
    PluginStateUpdateRequest,
    PluginType,
    PluginUploadResponse,
    SkillStepInfo,
    SkillType,
)

__all__ = [
    "CommandInfo",
    "PluginInfo",
    "PluginRatingInfo",
    "PluginRatingRequest",
    "PluginSource",
    "PluginStateUpdateRequest",
    "PluginType",
    "PluginUploadResponse",
    "SkillStepInfo",
    "SkillType",
]
