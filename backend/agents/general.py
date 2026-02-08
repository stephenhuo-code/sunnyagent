"""General fallback deep agent — orchestrates all tools and specialists."""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

from backend.registry import AGENT_REGISTRY, get_all_tools, register_agent
from backend.skills import SKILL_REGISTRY, get_skill_summaries
from backend.tools.file_tools import read_uploaded_file
from backend.tools.sandbox import execute_python, execute_python_with_file


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
    return f"Unknown skill: {skill_name}. Available skills: {', '.join(SKILL_REGISTRY.keys())}"


def _build_general_prompt() -> str:
    """Build the general agent prompt with skill summaries."""
    skills_section = get_skill_summaries()
    return f"""\
You are a general-purpose orchestration agent for complex, multi-step tasks.

You have two strategies:
1. **Direct**: Use your tools directly for simple sub-tasks.
2. **Delegate**: Use the task() tool to delegate to specialist subagents for focused work.

For complex, multi-step problems:
- Break the problem into sub-tasks.
- Decide which to handle yourself and which to delegate.
- You can run multiple task() calls in parallel for independent sub-tasks.
- Synthesize all results into a comprehensive final answer.

Prefer delegation to specialists when their expertise matches the sub-task.

## File Generation Tools

When using `execute_python_with_file` to generate files (PPT, Word, Excel, PDF, etc.):
- The tool returns a markdown download link on success
- **IMPORTANT**: Always include the download link in your final response to the user
- Format: After describing what you created, add the download link like:
  "下载链接：[📥 点击下载 filename.pptx](/api/files/xxx/filename.pptx)"

## Available Skills

Skills provide specialized instructions for specific tasks. When a user's request
matches a skill description, use activate_skill() to load the full instructions.

{skills_section}"""


def build_general_agent():
    """Build the general agent. Must be called AFTER other agents are registered."""
    model = init_chat_model("anthropic:claude-sonnet-4-5-20250929", temperature=0.0)

    subagent_specs = []
    for entry in AGENT_REGISTRY.values():
        subagent_specs.append(
            {
                "name": entry.name,
                "description": entry.description,
                "system_prompt": f"You are a {entry.name} specialist.",
                "tools": entry.tools,
            }
        )

    # Include activate_skill tool for skill discovery, sandbox tools, and file reading
    all_tools = get_all_tools() + [
        activate_skill,
        execute_python,
        execute_python_with_file,
        read_uploaded_file,
    ]

    agent = create_deep_agent(
        model=model,
        tools=all_tools,
        subagents=subagent_specs,
        system_prompt=_build_general_prompt(),
        name="general",
    )

    register_agent(
        name="general",
        description=(
            "Fallback for complex, multi-step, or cross-domain tasks. "
            "Can use all tools and delegate to any specialist agent."
        ),
        graph=agent,
        icon="sparkles",
    )
