"""Actor Factory - selects and instantiates actors for subtasks.

The Actor Factory is responsible for selecting the appropriate agent
based on SubtaskSpec requirements.

Selection Priority:
1. Explicit agent (explicit_agent field) - must be used if specified
2. Capability matching - preset and package agents compete
3. Generic fallback - when no match found
"""

import logging
from typing import Any

from backend.aime.models import Actor, SubtaskSpec
from backend.registry import AGENT_REGISTRY, AgentEntry

logger = logging.getLogger(__name__)


class ActorFactory:
    """Factory for selecting and instantiating actors.

    Uses the AGENT_REGISTRY to find agents and match capabilities.
    Implements the selection priority defined in the AIME architecture.
    """

    def __init__(self):
        """Initialize the Actor Factory."""
        logger.info("ActorFactory initialized")

    def select_actor(self, spec: SubtaskSpec) -> Actor:
        """Select and instantiate actor for a subtask.

        Selection priority:
        1. explicit_agent - must use if specified
        2. capability matching - find best match
        3. generic fallback - when no match found

        Args:
            spec: Subtask specification from Planner

        Returns:
            Configured Actor ready for execution

        Raises:
            ValueError: If explicit_agent specified but not found in registry
        """
        logger.info(
            f"[select_actor] Starting - explicit_agent={spec.explicit_agent}, "
            f"capabilities={spec.capabilities}"
        )

        # Priority 1: Explicit agent specification
        if spec.explicit_agent:
            logger.info(f"[select_actor] Using explicit agent path")
            return self._select_explicit_agent(spec)

        # Priority 2: Capability matching
        if spec.capabilities:
            logger.info(f"[select_actor] Using capability matching path")
            match = self.match_by_capabilities(spec.capabilities)
            if match:
                entry, score = match
                logger.info(
                    f"[select_actor] Selected '{entry.name}' via capability match "
                    f"(score={score})"
                )
                return self._create_actor_from_entry(entry, spec)

        # Priority 3: Generic fallback
        logger.info("[select_actor] Using generic fallback path")
        return self.create_generic_actor(spec)

    def _select_explicit_agent(self, spec: SubtaskSpec) -> Actor:
        """Select explicitly specified agent.

        Args:
            spec: Subtask spec with explicit_agent set

        Returns:
            Actor for the specified agent

        Raises:
            ValueError: If agent not found in registry
        """
        agent_name = spec.explicit_agent
        assert agent_name is not None

        if agent_name not in AGENT_REGISTRY:
            available = list(AGENT_REGISTRY.keys())
            raise ValueError(
                f"Agent '{agent_name}' not found in registry. "
                f"Available agents: {available}"
            )

        entry = AGENT_REGISTRY[agent_name]
        logger.info(f"Selected explicit agent: {agent_name}")
        return self._create_actor_from_entry(entry, spec)

    def match_by_capabilities(
        self, required: list[str]
    ) -> tuple[AgentEntry, int] | None:
        """Find best matching agent by capabilities.

        Scoring:
        - Each matching capability adds 1 to score
        - Preset agents get +0.5 tiebreaker bonus
        - Returns agent with highest score

        Args:
            required: List of required capabilities

        Returns:
            Tuple of (matched entry, score) or None if no match
        """
        if not required:
            return None

        logger.debug(f"[match_by_capabilities] Matching required={required}")
        required_set = set(required)
        best_match: tuple[AgentEntry, float] | None = None

        for entry in AGENT_REGISTRY.values():
            if not entry.capabilities:
                continue

            # Count matching capabilities
            entry_caps = set(entry.capabilities)
            matches = len(required_set & entry_caps)

            if matches == 0:
                continue

            # Calculate score with tiebreaker
            score = float(matches)
            if entry.source == "preset":
                score += 0.5  # Preset agents win ties

            if best_match is None or score > best_match[1]:
                best_match = (entry, score)
                logger.debug(
                    f"[match_by_capabilities] New best: {entry.name} (score={score})"
                )

        if best_match:
            logger.debug(
                f"[match_by_capabilities] Final match: {best_match[0].name} "
                f"(score={int(best_match[1])})"
            )
            return (best_match[0], int(best_match[1]))
        logger.debug("[match_by_capabilities] No match found")
        return None

    def create_generic_actor(self, spec: SubtaskSpec) -> Actor:
        """Create a generic actor as fallback.

        Uses the 'general' agent if registered, otherwise creates
        a dynamic generic actor with standard tools.

        Args:
            spec: Subtask specification

        Returns:
            Generic Actor with standard tools
        """
        # Use 'general' agent if available
        if "general" in AGENT_REGISTRY:
            entry = AGENT_REGISTRY["general"]
            return self._create_actor_from_entry(entry, spec)

        # Create dynamic generic actor
        from backend.aime.actors.generic import create_generic_actor

        logger.info("Creating dynamic generic actor")
        return create_generic_actor(spec)

    def _create_actor_from_entry(
        self, entry: AgentEntry, spec: SubtaskSpec
    ) -> Actor:
        """Create Actor from AgentEntry.

        Args:
            entry: Registry entry for the agent
            spec: Subtask specification

        Returns:
            Configured Actor
        """
        # Load skill persona if skill task
        persona = None
        if spec.skill_name:
            from backend.skills import SKILL_REGISTRY

            skill = SKILL_REGISTRY.get(spec.skill_name)
            if skill:
                # Use skill instructions as persona context
                persona = skill.load_instructions()
                logger.debug(f"Loaded skill persona for: {spec.skill_name}")

        return Actor(
            name=entry.name,
            graph=entry.graph,
            tools=entry.tools,
            persona=persona,
        )

    def get_agent_for_capability(self, capability: str) -> str | None:
        """Get agent name that best matches a single capability.

        Convenience method for simple routing decisions.

        Args:
            capability: Required capability

        Returns:
            Agent name or None if no match
        """
        match = self.match_by_capabilities([capability])
        if match:
            return match[0].name
        return None
