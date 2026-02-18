"""General fallback deep agent — orchestrates all tools and specialists.

DEPRECATION NOTE (005-aime-supervisor):
    This module is being superseded by the AIME architecture:
    - backend/aime/planner.py: AIMEPlanner handles task orchestration
    - backend/aime/actors/generic.py: Generic actor for fallback execution
    - backend/aime/actor_factory.py: Dynamic actor selection

    The 'general' agent is still registered for backwards compatibility
    and is used as the fallback when no specialist matches. Once AIME
    is fully validated, this module may be removed.

    Migration path:
    1. Use stream_aime_response() from backend/supervisor.py
    2. AIMEPlanner will use ActorFactory to select 'general' when needed
"""

from deepagents import create_deep_agent
from langchain_core.tools import tool

from backend.llm import get_model
from backend.registry import AGENT_REGISTRY, get_all_tools, register_agent
from backend.skills import SKILL_REGISTRY, get_skill_summaries
from backend.tools.file_tools import read_file
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
你是一个通用编排代理，负责处理复杂的多步骤任务。

**重要：你必须始终用中文回复用户。**

## 策略

你有两种策略：
1. **直接处理**：对于简单的子任务，直接使用你的工具。
2. **委托**：使用 task() 工具将任务委托给专业子代理。

对于复杂的多步骤问题：
- 将问题分解为子任务
- 决定哪些自己处理，哪些委托
- 对于独立的子任务，可以并行调用多个 task()
- 综合所有结果，给出完整的最终答案

当专家的专业领域与子任务匹配时，优先委托给专家。

## 文件生成工具

使用 `execute_python_with_file` 生成文件（PPT、Word、Excel、PDF 等）时：
- 工具成功时会返回 markdown 下载链接
- **重要**：始终在最终回复中包含下载链接
- 格式："下载链接：[📥 点击下载 filename.pptx](/api/files/xxx/filename.pptx)"

## 可用技能

技能提供特定任务的专业指令。当用户请求匹配某个技能描述时，
使用 activate_skill() 加载完整指令。

{skills_section}"""


def build_general_agent():
    """Build the general agent. Must be called AFTER other agents are registered."""
    model = get_model("general")

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
        read_file,  # Unified file reading tool (replaces read_uploaded_file, read_project_file)
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
        capabilities=["code_execution", "file_generation", "file_processing", "orchestration", "multi_step"],
        source="preset",
    )
