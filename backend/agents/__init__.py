"""Import agent modules to trigger registration.

Order matters:
1. Skills are loaded first (global skill registry)
2. Built-in specialists (research, sql) register next
3. Package plugins (from packages/ directory) are registered to PLUGIN_REGISTRY
"""

from backend.skills import load_all_skills

# Load global skills before agents (agents can reference skills)
load_all_skills()

from backend.agents import research, sql  # noqa: F401
from backend.plugins.package_loader import load_package_agents, scan_and_load_new_packages

# Load package plugins (registers to PLUGIN_REGISTRY, not AGENT_REGISTRY)
load_package_agents()

__all__ = [
    "load_package_agents",
    "scan_and_load_new_packages",
]
