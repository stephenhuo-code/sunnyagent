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
from backend.tools.file_tools import read_file
from backend.tools.sandbox import execute_python, execute_python_with_file

logger = logging.getLogger(__name__)


_GENERIC_SYSTEM_PROMPT = """\
你是一个通用 AI 助手，能够处理各种任务。

**重要：你必须始终用中文回复用户。**

## 能力

1. **代码执行**：使用 execute_python 或 execute_python_with_file 运行 Python 代码
2. **文件读取**：使用 read_file 读取文件（支持上传文件和项目文件）
   - 上传文件：read_file(file_id="...")
   - 项目文件：read_file(file_id="...", project_id="...")
3. **技能激活**：使用 activate_skill 加载专业指令

## 可用技能

{skills_section}

## 指南

- 将复杂任务分解为步骤
- 使用代码执行进行计算、数据处理、文件生成
- 生成文件时始终包含下载链接
- 如果任务不清楚，请要求澄清
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
        read_file,  # Unified file reading tool
        activate_skill,
    ]

    model = get_model("generic")

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
