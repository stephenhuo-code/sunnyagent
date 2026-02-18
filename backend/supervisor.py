"""LangGraph Supervisor — routes user messages to specialist deep agents.

Architecture:
    User message → Supervisor (LLM router) → Specialist agent | Direct response
    Specialist finishes → END

The supervisor is itself a `create_agent` graph so its text responses stream
token-by-token.  When it needs to delegate, it calls the `route` tool which
returns a `Command(goto=...)` that the parent StateGraph uses to jump to the
correct specialist subgraph node.

AIME Mode (005-aime-supervisor):
    User message → IntentAnalyzer → AIMEPlanner → Action handling
    - direct_reply: Stream response directly
    - delegate: Route to specialist via Actor Factory
    - plan: Decompose into subtasks
    - clarify: Ask clarification questions
"""

import logging
from typing import Any, AsyncGenerator

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Checkpointer, Command

from backend.aime.context import AgentContext
from backend.llm import get_model
from backend.registry import AGENT_REGISTRY, get_agent_descriptions

logger = logging.getLogger(__name__)

ROUTER_PROMPT_TEMPLATE = """\
You are a routing supervisor. Analyze the user's message and decide what to do.

## Available Specialist Agents
{agent_descriptions}

## Routing Rules (in priority order)
1. **Explicit routing** (message starts with [ROUTE_TO: agent_name]) → immediately route to that agent.
2. **File uploads** (message contains [用户上传了以下文件]) → route to "general".
3. **Skill requests** (message starts with [SKILL:]) → route to "general".
4. Simple greetings, general knowledge, math → respond directly, do NOT route.
5. Task clearly matches ONE specialist → call the route tool with that agent name.
6. Complex, multi-step, or cross-domain tasks → route to "general" (the orchestrator).
7. Ambiguous → ask the user for clarification.

When responding directly, just write the answer as normal text.
When routing, call the route tool with the agent name and a clear task description."""


def build_supervisor(checkpointer: Checkpointer | None = None):
    """Build and compile the top-level supervisor graph.

    This triggers agent registration via ``import backend.agents`` and wires
    every registered agent as a subgraph node reachable through the ``route``
    tool.

    Args:
        checkpointer: Optional checkpointer for conversation persistence.

    Returns:
        A compiled ``StateGraph`` ready for ``ainvoke`` / ``astream``.
    """
    # --- trigger agent registration ---
    import backend.agents  # noqa: F401

    model = get_model("supervisor")

    router_prompt = ROUTER_PROMPT_TEMPLATE.format(
        agent_descriptions=get_agent_descriptions()
    )

    # --- routing tool ---
    agent_names = list(AGENT_REGISTRY.keys())

    agent_names_str = ", ".join(agent_names)

    @tool(description=f"Route the user's request to a specialist agent. agent_name must be one of: {agent_names_str}.")
    def route(agent_name: str, task_description: str) -> Command:
        """Route the user's request to a specialist agent."""
        if agent_name not in agent_names:
            return Command(resume=f"Unknown agent '{agent_name}'. Choose from: {agent_names}")
        return Command(goto=agent_name, graph=Command.PARENT)

    # --- supervisor agent (create_agent → streams text) ---
    supervisor_agent = create_agent(
        model=model,
        tools=[route],
        system_prompt=router_prompt,
    )

    # --- build the parent StateGraph ---
    builder = StateGraph(MessagesState)
    builder.add_node("supervisor", supervisor_agent)

    for name, entry in AGENT_REGISTRY.items():
        builder.add_node(name, entry.graph)
        builder.add_edge(name, END)

    builder.add_edge(START, "supervisor")

    return builder.compile(checkpointer=checkpointer)


# =============================================================================
# AIME-based Supervisor (005-aime-supervisor)
# =============================================================================


def get_aime_planner():
    """Get or create the AIME Planner singleton.

    Lazy initialization to avoid import cycles.

    Returns:
        AIMEPlanner instance
    """
    from backend.aime.planner import AIMEPlanner

    # Trigger agent registration
    import backend.agents  # noqa: F401

    return AIMEPlanner()


async def stream_aime_response(
    thread_id: str,
    message: str,
    context: AgentContext | dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream AIME response as SSE events.

    This is the AIME equivalent of stream_agent_response() from stream_handler.py.
    Uses AIMEPlanner for intent analysis and action handling.

    Args:
        thread_id: Conversation thread ID
        message: User message
        context: AgentContext or legacy dict (for backwards compatibility)

    Yields:
        SSE event dicts compatible with stream_handler.py format
    """
    planner = get_aime_planner()

    async for event in planner.process(
        message=message,
        thread_id=thread_id,
        context=context,
    ):
        yield event
