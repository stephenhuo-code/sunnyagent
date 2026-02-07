"""Import agent modules to trigger registration.

Order matters:
1. Built-in specialists (research, sql) register first
2. Package agents (from packages/ directory) register next
3. General agent must be last — it discovers all previously registered agents
"""

from backend.agents import research, sql  # noqa: F401
from backend.agents.loader import load_package_agents
from backend.agents.general import build_general_agent

# Load downloaded agent packages before building the general agent.
load_package_agents()

# General agent must be built after all specialists are registered.
build_general_agent()
