"""Actor Factory - selects and instantiates actors for subtasks.

The Actor Factory is responsible for selecting the appropriate agent
based on SubtaskSpec requirements.

Selection Priority:
1. Explicit agent (explicit_agent field) - must be used if specified
2. Capability matching - preset agents (AGENT_REGISTRY) and plugins (PLUGIN_REGISTRY) compete
3. Generic fallback - when no match found

Key Design:
- Built-in agents (research, sql) are pre-registered in AGENT_REGISTRY
- Package plugins are registered in PLUGIN_REGISTRY (metadata only)
- Plugin Agent graphs are created dynamically when needed
"""

import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

from backend.aime.models import Actor, SubtaskSpec
from backend.checkpointer_store import get_checkpointer
from backend.llm import get_model
from backend.plugins.registry import PLUGIN_REGISTRY, PluginEntry
from backend.registry import AGENT_REGISTRY, AgentEntry
from backend.services.langfuse_service import get_langfuse_service
from backend.skills import SKILL_REGISTRY, get_skill_summaries

logger = logging.getLogger(__name__)


# =============================================================================
# Plugin Agent System Prompt
# =============================================================================

_PLUGIN_AGENT_PROMPT = """\
## Available Tools

1. **File Reading** (`read_file`): Read file contents
   - Use file paths from context
   - Supports CSV, Excel, PDF, Word formats

2. **Code Execution**:
   - `execute_python`: Execute Python code
   - `execute_python_with_input`: Execute code with input files
   - `execute_python_with_file`: Execute code with output files

3. **Skill Activation** (`activate_skill`): Load specialized instructions

## Important Guidelines

**File Access Rules**:
- Only use file paths provided in context
- Do not attempt to search or browse the filesystem
- Use `read_file(file_path="...")` to read directly

## Available Skills

{skills_section}

---

**Always respond in the user's language.**
"""


# =============================================================================
# Skill Activation Tool
# =============================================================================


@tool
def activate_skill(skill_name: str) -> str:
    """Activate a skill to get detailed instructions.

    Use this tool when the user's request matches a skill's description.
    The skill instructions will tell you how to complete the task.

    Args:
        skill_name: The skill name to activate (e.g., "pdf", "docx")

    Returns:
        Full skill instructions, or error message if not found.
    """
    skill = SKILL_REGISTRY.get(skill_name)
    if skill:
        return skill.load_instructions()
    return f"Unknown skill: {skill_name}. Available skills: {', '.join(SKILL_REGISTRY.keys())}"


# =============================================================================
# Capability to Tool Mapping (Primary Defense Layer)
# =============================================================================

# Maps capability names to the tool names they enable
CAPABILITY_TOOL_MAP: dict[str, list[str]] = {
    "file_read": ["read_file"],
    "code_execution": [
        "execute_python",
        "execute_python_with_input",
        "execute_python_with_file",
    ],
    "skill_activation": ["activate_skill"],
}


def _create_plugin_tools(capabilities: list[str] | None = None) -> list[BaseTool]:
    """Create tool set for plugin agents, optionally filtered by capabilities.

    Args:
        capabilities: Allowed capabilities list
            - None: All tools (default behavior)
            - []: No tools (text_only mode)
            - ["file_read", "code_execution"]: Only matching tools

    Returns:
        Filtered list of tools based on capabilities

    Note:
        No `ls` tool - agents must use paths from context.
        This prevents unwanted filesystem browsing.
    """
    # Import here to avoid circular imports
    from backend.tools.file_tools import read_file
    from backend.tools.sandbox import (
        execute_python,
        execute_python_with_file,
        execute_python_with_input,
    )

    # Map tool names to actual tool objects
    all_tools: dict[str, BaseTool] = {
        "read_file": read_file,
        "execute_python": execute_python,
        "execute_python_with_input": execute_python_with_input,
        "execute_python_with_file": execute_python_with_file,
        "activate_skill": activate_skill,
    }

    # None = return all tools (default behavior)
    if capabilities is None:
        return list(all_tools.values())

    # Empty list = no tools (text_only mode)
    if len(capabilities) == 0:
        logger.info("[_create_plugin_tools] text_only mode - returning no tools")
        return []

    # Filter tools based on capabilities
    allowed_tool_names: set[str] = set()
    for cap in capabilities:
        if cap in CAPABILITY_TOOL_MAP:
            allowed_tool_names.update(CAPABILITY_TOOL_MAP[cap])
        else:
            logger.warning(f"[_create_plugin_tools] Unknown capability: {cap}")

    filtered_tools = [all_tools[name] for name in allowed_tool_names if name in all_tools]
    logger.info(
        f"[_create_plugin_tools] capabilities={capabilities} -> "
        f"tools={[t.name for t in filtered_tools]}"
    )
    return filtered_tools


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

    def _create_plugin_actor(
        self,
        entry: PluginEntry,
        spec: SubtaskSpec,
        step_capabilities: list[str] | None = None,
    ) -> Actor:
        """Dynamically create an Actor for a plugin.

        Called when routing to a plugin instead of a built-in agent.
        The Agent graph is created on-demand rather than at startup.

        Args:
            entry: Plugin metadata from PLUGIN_REGISTRY
            spec: Subtask specification
            step_capabilities: Optional step-level capability restrictions
                - None: Use all tools (default)
                - []: No tools (text_only)
                - ["file_read", ...]: Only specified capabilities

        Returns:
            Configured Actor ready for execution
        """
        # Create tools with capability filtering
        tools = _create_plugin_tools(step_capabilities)

        # Build system prompt
        skills_section = get_skill_summaries()
        system_prompt = _PLUGIN_AGENT_PROMPT.format(skills_section=skills_section)

        # Create agent dynamically
        model = get_model(entry.name)
        graph = create_react_agent(
            model=model,
            tools=tools,
            prompt=system_prompt,
            checkpointer=get_checkpointer(),
            name=entry.name,
        )

        logger.info(f"Dynamically created plugin actor '{entry.name}'")

        # Load skill persona if skill task
        persona = None
        if spec.skill_name:
            skill = SKILL_REGISTRY.get(spec.skill_name)
            if skill:
                persona = skill.load_instructions()
                logger.debug(f"Loaded skill persona for: {spec.skill_name}")

        return Actor(
            name=entry.name,
            graph=graph,
            tools=tools,
            persona=persona,
        )

    async def select_actor(
        self,
        spec: SubtaskSpec,
        step_capabilities: list[str] | None = None,
    ) -> Actor:
        """Select and instantiate actor for a subtask.

        Selection priority:
        1. explicit_agent - must use if specified
        2. capability matching - find best match
        3. generic fallback - when no match found

        Args:
            spec: Subtask specification from Planner
            step_capabilities: Optional step-level capability restrictions
                - None: Use all tools (default)
                - []: No tools (text_only mode)
                - ["file_read", "code_execution"]: Only specified tools

        Returns:
            Configured Actor ready for execution

        Raises:
            ValueError: If explicit_agent specified but not found in registry
        """
        logger.info(
            f"[select_actor] Starting - explicit_agent={spec.explicit_agent}, "
            f"capabilities={spec.capabilities}, step_capabilities={step_capabilities}"
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
                actor = self._select_explicit_agent(spec, step_capabilities)
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
                    # Check if it's a plugin (PluginEntry) or agent (AgentEntry)
                    if isinstance(entry, PluginEntry):
                        logger.info(
                            f"[select_actor] Selected plugin '{entry.name}' via capability match "
                            f"(score={score})"
                        )
                        actor = self._create_plugin_actor(entry, spec, step_capabilities)
                    else:
                        logger.info(
                            f"[select_actor] Selected agent '{entry.name}' via capability match "
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
            actor = self.create_generic_actor(spec, step_capabilities)
            if span:
                span.update(output={"selected_actor": actor.name, "path": "generic_fallback"})
            return actor

        finally:
            if context_manager:
                try:
                    context_manager.__exit__(None, None, None)
                except Exception:
                    pass

    def _select_explicit_agent(
        self,
        spec: SubtaskSpec,
        step_capabilities: list[str] | None = None,
    ) -> Actor:
        """Select explicitly specified agent.

        Checks both AGENT_REGISTRY (built-in agents) and
        PLUGIN_REGISTRY (package plugins).

        Args:
            spec: Subtask spec with explicit_agent set
            step_capabilities: Optional step-level capability restrictions

        Returns:
            Actor for the specified agent

        Raises:
            ValueError: If agent not found in either registry
        """
        agent_name = spec.explicit_agent
        assert agent_name is not None

        # Priority 1: Check built-in agents
        if agent_name in AGENT_REGISTRY:
            entry = AGENT_REGISTRY[agent_name]
            logger.info(f"Selected explicit agent: {agent_name}")
            return self._create_actor_from_entry(entry, spec)

        # Priority 2: Check package plugins
        if agent_name in PLUGIN_REGISTRY:
            entry = PLUGIN_REGISTRY[agent_name]
            logger.info(f"Selected explicit plugin: {agent_name}")
            return self._create_plugin_actor(entry, spec, step_capabilities)

        # Not found - raise error with both registries
        available_agents = list(AGENT_REGISTRY.keys())
        available_plugins = list(PLUGIN_REGISTRY.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. "
            f"Available agents: {available_agents}, "
            f"Available plugins: {available_plugins}"
        )

    def match_by_capabilities(
        self, required: list[str], disabled_plugins: set[str] | None = None
    ) -> tuple[AgentEntry | PluginEntry, int] | None:
        """Find best matching agent or plugin by capabilities.

        Now checks both AGENT_REGISTRY (built-in agents) and
        PLUGIN_REGISTRY (package plugins).

        Scoring:
        - Each matching capability adds 1 to score
        - Preset agents get +0.5 tiebreaker bonus
        - Returns agent/plugin with highest score
        - Agents/plugins from disabled plugins are excluded

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
        best_match: tuple[AgentEntry | PluginEntry, float] | None = None
        disabled_plugins = disabled_plugins or set()

        # Check AGENT_REGISTRY (built-in agents)
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
                    f"[match_by_capabilities] New best agent: {entry.name} (score={score})"
                )

        # Check PLUGIN_REGISTRY (package plugins)
        for entry in PLUGIN_REGISTRY.values():
            if not entry.capabilities:
                continue

            # Check if plugin is disabled
            plugin_name = f"package:{entry.name}"
            if plugin_name in disabled_plugins:
                logger.debug(f"[match_by_capabilities] Skipping disabled plugin: {entry.name}")
                continue

            # Count matching capabilities
            entry_caps = set(entry.capabilities)
            matches = len(required_set & entry_caps)

            if matches == 0:
                continue

            # Calculate score (plugins don't get tiebreaker bonus)
            score = float(matches)

            if best_match is None or score > best_match[1]:
                best_match = (entry, score)
                logger.debug(
                    f"[match_by_capabilities] New best plugin: {entry.name} (score={score})"
                )

        if best_match:
            entry_type = "plugin" if isinstance(best_match[0], PluginEntry) else "agent"
            logger.debug(
                f"[match_by_capabilities] Final match: {best_match[0].name} "
                f"({entry_type}, score={int(best_match[1])})"
            )
            return (best_match[0], int(best_match[1]))
        logger.debug("[match_by_capabilities] No match found")
        return None

    def create_generic_actor(
        self,
        spec: SubtaskSpec,
        step_capabilities: list[str] | None = None,
    ) -> Actor:
        """Create a generic actor as fallback.

        Args:
            spec: Subtask specification
            step_capabilities: Optional step-level capability restrictions

        Returns:
            Generic Actor with standard tools (filtered by capabilities)
        """
        from backend.aime.actors.generic import create_generic_actor

        logger.info(f"Creating dynamic generic actor (step_capabilities={step_capabilities})")
        return create_generic_actor(spec, step_capabilities)

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
