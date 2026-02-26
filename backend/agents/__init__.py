"""Import agent modules to trigger registration.

Order matters:
1. Skills are loaded first (global skill registry)
2. Built-in specialists (research, sql) register next
3. Package agents (from packages/ directory) register next
"""

from backend.skills import load_all_skills

# Load global skills before agents (agents can reference skills)
load_all_skills()

from backend.agents import research, sql  # noqa: F401
from backend.agents.loader import load_package_agents
from backend.agents.package_agent import create_package_agent, create_package_tools

# Load downloaded agent packages
load_package_agents()

__all__ = [
    "create_package_agent",
    "create_package_tools",
    "load_package_agents",
]
