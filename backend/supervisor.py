"""LangGraph Supervisor — routes user messages to specialist deep agents.

Architecture:
    User message → Supervisor (LLM router) → Specialist agent | Direct response
    Specialist finishes → END

The supervisor is itself a `create_agent` graph so its text responses stream
token-by-token.  When it needs to delegate, it calls the `route` tool which
returns a `Command(goto=...)` that the parent StateGraph uses to jump to the
correct specialist subgraph node.
"""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Checkpointer, Command

from backend.registry import AGENT_REGISTRY, get_agent_descriptions

ROUTER_PROMPT_TEMPLATE = """\
You are a routing supervisor. Analyze the user's message and decide what to do.

## Available Specialist Agents
{agent_descriptions}

## Routing Rules
1. Simple greetings, general knowledge, math → respond directly, do NOT route.
2. Task clearly matches ONE specialist → call the route tool with that agent name.
3. Complex, multi-step, or cross-domain tasks → route to "general" (the orchestrator).
4. Ambiguous → ask the user for clarification.

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

    model = init_chat_model("anthropic:claude-sonnet-4-5-20250929", temperature=0.0)

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
