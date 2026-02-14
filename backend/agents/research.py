"""Research deep agent — web research, current events, topic comparisons."""

import logging
from datetime import datetime

from deepagents import create_deep_agent

from backend.llm import get_model
from backend.registry import register_agent
from backend.research_prompts import RESEARCHER_INSTRUCTIONS
from backend.research_tools import tavily_search, think_tool
from backend.skills import SKILL_REGISTRY

logger = logging.getLogger(__name__)

_tools = [tavily_search, think_tool]

# Skills to bind to the research agent (loaded from SKILL_REGISTRY)
_BOUND_SKILLS = ["pdf", "web-scraping"]


def _get_skill_context() -> str:
    """Load skill instructions for bound skills."""
    skill_sections = []
    for skill_name in _BOUND_SKILLS:
        skill = SKILL_REGISTRY.get(skill_name)
        if skill:
            skill_sections.append(skill.load_instructions())
            logger.info(f"Bound skill '{skill_name}' to research agent")
        else:
            logger.debug(f"Skill '{skill_name}' not found in registry")
    return "\n\n".join(skill_sections)


def _build_system_prompt() -> str:
    """Build the research agent system prompt with bound skills."""
    base_prompt = RESEARCHER_INSTRUCTIONS.format(date=datetime.now().strftime("%Y-%m-%d"))
    skill_context = _get_skill_context()
    if skill_context:
        return f"{base_prompt}\n\n# Skills\n\n{skill_context}"
    return base_prompt


_agent = create_deep_agent(
    model=get_model("research"),
    tools=_tools,
    system_prompt=_build_system_prompt(),
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
