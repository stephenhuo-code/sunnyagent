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
from uuid import UUID

from backend.aime.models import Actor, SubtaskSpec
from backend.registry import AGENT_REGISTRY, AgentEntry
from backend.services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


class ActorFactory:
    """Factory for selecting and instantiating actors.

    Uses the AGENT_REGISTRY to find agents and match capabilities.
    Implements the selection priority defined in the AIME architecture.
    Supports filtering agents by user's enabled plugins.
    """

    def __init__(self, user_id: UUID | str | None = None):
        """Initialize the Actor Factory.

        Args:
            user_id: Optional user ID for plugin filtering. If provided,
                    only agents from enabled plugins will be considered.
                    Accepts UUID or string representation.
        """
        # Convert string to UUID if needed
        if isinstance(user_id, str):
            self.user_id = UUID(user_id)
        else:
            self.user_id = user_id
        self._disabled_plugins: set[str] | None = None
        logger.info(f"ActorFactory initialized (user_id={self.user_id})")

    async def _get_disabled_plugins(self) -> set[str]:
        """Get the set of disabled plugin names for the current user.

        Cached for the lifetime of this factory instance.
        """
        if self._disabled_plugins is None:
            if self.user_id:
                from backend.plugins.database import get_disabled_plugin_names
                self._disabled_plugins = await get_disabled_plugin_names(self.user_id)
            else:
                self._disabled_plugins = set()
        return self._disabled_plugins

    def _is_agent_enabled(self, entry: AgentEntry, disabled_plugins: set[str]) -> bool:
        """Check if an agent is enabled for the current user.

        Args:
            entry: Agent registry entry
            disabled_plugins: Set of disabled plugin names

        Returns:
            True if the agent is enabled (not in disabled list)
        """
        plugin_name = f"{entry.source}:{entry.name}"
        return plugin_name not in disabled_plugins

    async def select_actor(self, spec: SubtaskSpec) -> Actor:
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

        # Create Langfuse span for actor selection
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        context_manager = None
        span = None

        if langfuse_client:
            try:
                context_manager = langfuse_client.start_as_current_observation(
                    as_type="span",
                    name="actor-factory-select",
                    input={
                        "explicit_agent": spec.explicit_agent,
                        "capabilities": spec.capabilities,
                        "description_preview": spec.description[:100] if spec.description else None,
                    },
                )
                span = context_manager.__enter__()
            except Exception:
                pass

        try:
            # Priority 1: Explicit agent specification
            if spec.explicit_agent:
                logger.info(f"[select_actor] Using explicit agent path")
                actor = self._select_explicit_agent(spec)
                if span:
                    span.update(output={"selected_actor": actor.name, "path": "explicit"})
                return actor

            # Priority 2: Capability matching (with user plugin filtering)
            if spec.capabilities:
                logger.info(f"[select_actor] Using capability matching path")
                disabled_plugins = await self._get_disabled_plugins()
                match = self.match_by_capabilities(spec.capabilities, disabled_plugins)
                if match:
                    entry, score = match
                    logger.info(
                        f"[select_actor] Selected '{entry.name}' via capability match "
                        f"(score={score})"
                    )
                    actor = self._create_actor_from_entry(entry, spec)
                    if span:
                        span.update(output={
                            "selected_actor": actor.name,
                            "path": "capability_match",
                            "score": score,
                        })
                    return actor

            # Priority 3: Generic fallback
            logger.info("[select_actor] Using generic fallback path")
            actor = self.create_generic_actor(spec)
            if span:
                span.update(output={"selected_actor": actor.name, "path": "generic_fallback"})
            return actor

        finally:
            if context_manager:
                try:
                    context_manager.__exit__(None, None, None)
                except Exception:
                    pass

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
        self, required: list[str], disabled_plugins: set[str] | None = None
    ) -> tuple[AgentEntry, int] | None:
        """Find best matching agent by capabilities.

        Scoring:
        - Each matching capability adds 1 to score
        - Preset agents get +0.5 tiebreaker bonus
        - Returns agent with highest score
        - Agents from disabled plugins are excluded

        Args:
            required: List of required capabilities
            disabled_plugins: Set of disabled plugin names to exclude

        Returns:
            Tuple of (matched entry, score) or None if no match
        """
        if not required:
            return None

        logger.debug(f"[match_by_capabilities] Matching required={required}")
        required_set = set(required)
        best_match: tuple[AgentEntry, float] | None = None
        disabled_plugins = disabled_plugins or set()

        for entry in AGENT_REGISTRY.values():
            if not entry.capabilities:
                continue

            # Skip disabled agents
            if not self._is_agent_enabled(entry, disabled_plugins):
                logger.debug(f"[match_by_capabilities] Skipping disabled agent: {entry.name}")
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

        Args:
            spec: Subtask specification

        Returns:
            Generic Actor with standard tools
        """
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
