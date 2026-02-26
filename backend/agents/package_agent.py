"""Package Agent - custom agent for package plugins.

Uses LangGraph's create_react_agent instead of deepagents to have
full control over the tool list. This prevents unwanted filesystem
browsing (ls) while keeping necessary file operations (read_file).
"""

import logging
from typing import Sequence

from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from backend.llm import get_model
from backend.skills import SKILL_REGISTRY, get_skill_summaries
from backend.tools.file_tools import read_file
from backend.tools.sandbox import (
    execute_python,
    execute_python_with_file,
    execute_python_with_input,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompt Template
# =============================================================================

_PACKAGE_AGENT_PROMPT = """\
{agent_memory}

---

## 可用工具

你有以下工具可用：

1. **文件读取** (`read_file`)：读取文件内容
   - 使用上下文中提供的文件路径
   - 支持 CSV、Excel、PDF、Word 等格式

2. **代码执行**：
   - `execute_python`: 执行 Python 代码
   - `execute_python_with_input`: 执行代码并处理输入文件
   - `execute_python_with_file`: 执行代码并生成输出文件

3. **技能激活** (`activate_skill`)：加载专业指令

## 重要指南

**文件访问规则**：
- 只使用上下文中提供的文件路径
- 不要尝试搜索或浏览文件系统
- 使用 `read_file(file_path="...")` 直接读取

## 可用技能

{skills_section}

---

**请始终用中文回复用户。**
"""


# =============================================================================
# Activate Skill Tool
# =============================================================================


@tool
def activate_skill(skill_name: str) -> str:
    """激活一个技能以获取详细指令。

    当用户的请求与某个技能的描述匹配时使用此工具。
    技能指令会告诉你如何完成任务。

    Args:
        skill_name: 要激活的技能名称（如 "pdf", "docx"）

    Returns:
        完整的技能指令，或错误消息（如果未找到）。
    """
    skill = SKILL_REGISTRY.get(skill_name)
    if skill:
        return skill.load_instructions()
    return f"未知技能: {skill_name}。可用技能: {', '.join(SKILL_REGISTRY.keys())}"


# =============================================================================
# Tool Factory
# =============================================================================


def create_package_tools(plugin_name: str) -> list[BaseTool]:
    """Create tools for a package agent.

    Args:
        plugin_name: The plugin name (e.g., "package:data")

    Returns:
        List of tools available to the package agent

    Note:
        No `ls` tool - agents must use paths from context.
        This prevents unwanted filesystem browsing.
    """
    # Core tools for package agents
    return [
        read_file,  # File reading (supports absolute paths)
        execute_python,  # Simple code execution
        execute_python_with_input,  # Code execution with input files
        execute_python_with_file,  # Code execution with output files
        activate_skill,  # Skill activation
    ]


# =============================================================================
# Agent Factory
# =============================================================================


def create_package_agent(
    name: str,
    agents_md_content: str,
    checkpointer: BaseCheckpointSaver | None = None,
    tools: Sequence[BaseTool] | None = None,
) -> CompiledStateGraph:
    """Create a package agent using LangGraph's create_react_agent.

    This is a simpler alternative to deepagents.create_deep_agent that gives
    full control over the tool list.

    Args:
        name: Agent name (used for model selection)
        agents_md_content: Content of AGENTS.md file (system prompt/memory)
        checkpointer: Optional checkpointer for state persistence
        tools: Optional custom tools (defaults to standard package tools)

    Returns:
        Compiled LangGraph agent
    """
    # Get model for this agent
    model = get_model(name)

    # Build tools
    plugin_name = f"package:{name}"
    agent_tools = list(tools) if tools else create_package_tools(plugin_name)

    # Build system prompt
    skills_section = get_skill_summaries()
    system_prompt = _PACKAGE_AGENT_PROMPT.format(
        agent_memory=agents_md_content,
        skills_section=skills_section,
    )

    # Create agent using LangGraph's create_react_agent
    agent = create_react_agent(
        model=model,
        tools=agent_tools,
        prompt=system_prompt,
        checkpointer=checkpointer,
        name=name,
    )

    logger.info(f"Created package agent '{name}' with {len(agent_tools)} tools")
    return agent
