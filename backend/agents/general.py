"""General fallback deep agent — orchestrates all tools and specialists."""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from backend.registry import AGENT_REGISTRY, get_all_tools, register_agent

GENERAL_PROMPT = """\
You are a general-purpose orchestration agent for complex, multi-step tasks.

You have two strategies:
1. **Direct**: Use your tools directly for simple sub-tasks.
2. **Delegate**: Use the task() tool to delegate to specialist subagents for focused work.

For complex, multi-step problems:
- Break the problem into sub-tasks.
- Decide which to handle yourself and which to delegate.
- You can run multiple task() calls in parallel for independent sub-tasks.
- Synthesize all results into a comprehensive final answer.

Prefer delegation to specialists when their expertise matches the sub-task."""


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

    agent = create_deep_agent(
        model=model,
        tools=get_all_tools(),
        subagents=subagent_specs,
        system_prompt=GENERAL_PROMPT,
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
