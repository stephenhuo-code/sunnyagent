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
from backend.tools.sandbox import (
    execute_python,
    execute_python_with_file,
    execute_python_with_input,
)

logger = logging.getLogger(__name__)


_GENERIC_SYSTEM_PROMPT = """\
你是一个通用 AI 助手，能够处理各种任务。

**重要：你必须始终用中文回复用户。**

## 能力

1. **代码执行**：
   - `execute_python`: 执行简单 Python 代码（无文件输入）
   - `execute_python_with_input`: 执行代码并处理输入文件（支持上传文件和项目文件）
     - 文件会被复制到容器的 `/input/` 目录
     - 可直接使用 `pd.read_csv('/input/文件名.csv')` 读取
     - 参数 `project_id`: 如果是项目文件，必须提供此参数
     - 可选参数 `output_filename` 用于生成可下载文件
   - `execute_python_with_file`: 执行代码并生成可下载文件（无输入文件）

2. **文件读取**：使用 read_file 预览文件内容
   - 返回文本内容（用于查看文件结构）
   - 大文件数据处理请使用 execute_python_with_input

3. **技能激活**：使用 activate_skill 加载专业指令

## 处理用户文件的正确模式

1. **查看上下文中的 [可用文件] 获取 file_id（和 project_id）**
2. **使用 execute_python_with_input 工具**：
   - `input_file_ids`: 文件 ID 列表
   - `project_id`: 如果是项目文件，必须提供项目 ID
   - `code`: 使用 `/input/{{原始文件名}}` 路径访问文件

示例：
```python
# 如果上下文显示：数据.csv (file_id: abc123, project_id: proj-456)
# 工具参数：
# input_file_ids: ["abc123"]
# project_id: "proj-456"
# code:
import pandas as pd
df = pd.read_csv('/input/数据.csv')
print(df.describe())
# 如果需要输出文件：
df.to_excel('/output/result.xlsx', index=False)
```

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


def create_generic_actor(
    spec: SubtaskSpec | None = None,
    step_capabilities: list[str] | None = None,
) -> Actor:
    """Create a generic actor with standard tools.

    Args:
        spec: Optional subtask specification for context
        step_capabilities: Optional step-level capability restrictions
            - None: Use all tools (default)
            - []: No tools (text_only mode)
            - ["file_read", "code_execution"]: Only specified capabilities

    Returns:
        Generic Actor ready for execution
    """
    from langchain_core.tools import BaseTool, tool

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

    # Capability to tool mapping
    capability_tool_map: dict[str, list[BaseTool]] = {
        "file_read": [read_file],
        "code_execution": [execute_python, execute_python_with_input, execute_python_with_file],
        "skill_activation": [activate_skill],
    }

    # Filter tools based on step_capabilities
    if step_capabilities is None:
        # Default: all tools
        tools: list[BaseTool] = [
            execute_python,
            execute_python_with_input,
            execute_python_with_file,
            read_file,
            activate_skill,
        ]
    elif len(step_capabilities) == 0:
        # text_only mode: no tools
        tools = []
        logger.info("[create_generic_actor] text_only mode - no tools")
    else:
        # Filter by capabilities
        tools = []
        for cap in step_capabilities:
            if cap in capability_tool_map:
                tools.extend(capability_tool_map[cap])
        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_tools: list[BaseTool] = []
        for t in tools:
            if t.name not in seen:
                seen.add(t.name)
                unique_tools.append(t)
        tools = unique_tools
        logger.info(f"[create_generic_actor] capabilities={step_capabilities} -> tools={[t.name for t in tools]}")

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
