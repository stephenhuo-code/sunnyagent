"""Import agent modules to trigger registration.

Order matters:
1. Skills are loaded first (global skill registry)
2. Built-in specialists (research, sql) register next
3. Package agents (from packages/ directory) register next
4. General agent must be last — it discovers all previously registered agents/skills
"""

from backend.skills import load_all_skills

# Load global skills before agents (agents can reference skills)
load_all_skills()

from backend.agents import research, sql  # noqa: F401
from backend.agents.loader import load_package_agents
from backend.agents.general import build_general_agent

# Load downloaded agent packages before building the general agent.
load_package_agents()

# General agent must be built after all specialists are registered.
build_general_agent()
