"""Generic Actor - fallback actor with standard tools.

The Generic Actor is used when no specialist agent matches the task.
It provides standard capabilities:
- Sandbox code execution
- File tools
- Skill activation
"""

import logging

from deepagents import create_deep_agent

from backend.aime.models import Actor, SubtaskSpec
from backend.llm import get_model
from backend.skills import SKILL_REGISTRY, get_skill_summaries
from backend.tools.file_tools import read_uploaded_file
from backend.tools.sandbox import execute_python, execute_python_with_file

logger = logging.getLogger(__name__)


_GENERIC_SYSTEM_PROMPT = """\
You are a general-purpose AI assistant capable of handling various tasks.

## Capabilities

1. **Code Execution**: Use execute_python or execute_python_with_file to run Python code
2. **File Reading**: Use read_uploaded_file to read user-uploaded files
3. **Skill Activation**: Use activate_skill to load specialized instructions

## Available Skills

{skills_section}

## Guidelines

- Break complex tasks into steps
- Use code execution for calculations, data processing, file generation
- Always include download links when generating files
- Ask for clarification if the task is unclear
"""


def _build_generic_prompt() -> str:
    """Build the generic actor system prompt."""
    skills_section = get_skill_summaries()
    return _GENERIC_SYSTEM_PROMPT.format(skills_section=skills_section)


def create_generic_actor(spec: SubtaskSpec | None = None) -> Actor:
    """Create a generic actor with standard tools.

    Args:
        spec: Optional subtask specification for context

    Returns:
        Generic Actor ready for execution
    """
    from langchain_core.tools import tool

    @tool
    def activate_skill(skill_name: str) -> str:
        """Activate a skill to get detailed instructions.

        Use this when a user's request matches a skill's description.
        The skill instructions will tell you how to accomplish the task.

        Args:
            skill_name: The name of the skill to activate (e.g., "pdf", "docx")

        Returns:
            The full skill instructions, or an error message if not found.
        """
        skill = SKILL_REGISTRY.get(skill_name)
        if skill:
            return skill.load_instructions()
        return f"Unknown skill: {skill_name}. Available: {', '.join(SKILL_REGISTRY.keys())}"

    # Standard tools for generic actor
    tools = [
        execute_python,
        execute_python_with_file,
        read_uploaded_file,
        activate_skill,
    ]

    model = get_model("general")

    # Build system prompt
    system_prompt = _build_generic_prompt()

    # Add skill persona if specified
    if spec and spec.skill_name:
        skill = SKILL_REGISTRY.get(spec.skill_name)
        if skill:
            system_prompt += f"\n\n## Active Skill: {spec.skill_name}\n\n"
            system_prompt += skill.load_instructions()

    # Create the agent graph
    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        name="generic",
    )

    return Actor(
        name="generic",
        graph=agent,
        tools=tools,
        persona=system_prompt if spec and spec.skill_name else None,
    )
