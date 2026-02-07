"""Research deep agent — web research, current events, topic comparisons."""

from datetime import datetime

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from backend.registry import register_agent
from backend.research_prompts import RESEARCHER_INSTRUCTIONS
from backend.research_tools import tavily_search, think_tool

_tools = [tavily_search, think_tool]

_agent = create_deep_agent(
    model=init_chat_model("anthropic:claude-sonnet-4-5-20250929", temperature=0.0),
    tools=_tools,
    system_prompt=RESEARCHER_INSTRUCTIONS.format(
        date=datetime.now().strftime("%Y-%m-%d")
    ),
    name="research",
)

register_agent(
    name="research",
    description=(
        "Web research, current events, topic comparisons. "
        "Searches the internet and returns reports with citations."
    ),
    graph=_agent,
    tools=_tools,
    icon="search",
)
