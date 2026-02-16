# Quickstart: AIME Development Guide

**Branch**: `005-aime-supervisor` | **Date**: 2026-02-15 | **Plan**: [plan.md](./plan.md)

## Overview

本指南帮助开发者快速理解和扩展 AIME 架构。

---

## 1. 添加新的 Classifier

Intent Analyzer 使用可插拔的 Classifier 链，按优先级执行直到获得确定结果。

### 1.1 创建 Classifier

```python
# backend/aime/intent/classifiers/my_classifier.py

from backend.aime.intent.classifiers.base import ClassifierBase
from backend.aime.intent.models import IntentResult

class MyClassifier(ClassifierBase):
    """自定义分类器示例"""

    @property
    def name(self) -> str:
        return "my_classifier"

    @property
    def priority(self) -> int:
        # 优先级：数字越小越先执行
        # rule_based: 0, keyword_based: 10, llm_based: 100
        return 50  # 在 keyword 和 llm 之间

    async def classify(
        self,
        message: str,
        context: dict | None = None,
        domain: str | None = None,
    ) -> IntentResult | None:
        # 返回 IntentResult 表示确定分类
        # 返回 None 表示传递给下一个 Classifier

        if self._matches_my_pattern(message):
            return IntentResult(
                action="delegate",
                confidence=0.9,
                capabilities=["my_capability"],
            )

        return None  # 传递给下一个

    def _matches_my_pattern(self, message: str) -> bool:
        # 自定义匹配逻辑
        return "my_keyword" in message.lower()
```

### 1.2 注册 Classifier

```python
# backend/aime/intent/analyzer.py

from backend.aime.intent.classifiers.my_classifier import MyClassifier

class IntentAnalyzer:
    def __init__(self):
        self.classifiers = [
            RuleBasedClassifier(),
            KeywordClassifier(),
            MyClassifier(),       # 添加到链中
            LLMClassifier(),
        ]
        # 按优先级排序
        self.classifiers.sort(key=lambda c: c.priority)
```

---

## 2. 扩展 Agent Capabilities

### 2.1 预设 Agent 添加能力

```python
# backend/agents/research.py

from backend.registry import register_agent

register_agent(
    name="research",
    description="Web research specialist",
    graph=agent,
    capabilities=[
        "web_search",
        "news_search",
        "academic_search",
        "my_new_capability",  # 添加新能力
    ],
    source="preset",
)
```

### 2.2 自定义 Agent 声明能力

在 `packages/my-agent/AGENTS.md` frontmatter 中声明：

```yaml
---
name: my-agent
description: My custom agent for specific tasks
capabilities:
  - my_capability
  - another_capability
---
# My Agent

System prompt and instructions here...
```

### 2.3 更新能力映射（可选）

```python
# backend/aime/intent/models.py

CAPABILITY_AGENT_MAP = {
    # 现有映射...
    "web_search": "research",

    # 新增映射（仅供 IntentAnalyzer 参考）
    "my_capability": "my-agent",
}
```

**注意**: 实际 Agent 选择由 Actor Factory 从 AGENT_REGISTRY 动态计算，此映射仅作为 IntentAnalyzer 的快速参考。

---

## 3. 创建 Workflow Skill

### 3.1 定义 Workflow Skill

```yaml
# skills/my-workflow/SKILL.md
---
name: my-workflow
description: A multi-step workflow for complex tasks
type: workflow
steps:
  - id: gather
    description: Gather required information
    required_capability: web_search
  - id: analyze
    description: Analyze gathered data
    required_capability: code_execution
  - id: generate
    description: Generate final output
    required_capability: document_generation
---
# My Workflow Instructions

## Overview
This skill guides the execution of a multi-step workflow.

## For Each Step

### gather
Search for relevant information using web search tools.

### analyze
Use Python to analyze the gathered data.

### generate
Create the final document based on analysis results.
```

### 3.2 Planner 处理流程

当用户请求使用 Workflow Skill：

1. **识别 Skill 请求**: IntentAnalyzer 检测到 skill 关键词或显式 `[SKILL: my-workflow]`
2. **加载 Skill 元信息**: Planner 从 `WORKFLOW_SKILLS` 获取步骤定义
3. **展开为子任务**: 每个 step 生成一个 SubtaskSpec
4. **Actor Factory 处理**: 为每个子任务选择合适的 Agent，注入 Skill Instructions

```python
# Planner 展开逻辑
def _create_subtasks_for_skill(self, skill_name: str) -> list[SubtaskSpec]:
    workflow_info = WORKFLOW_SKILLS.get(skill_name)

    if workflow_info:
        # Workflow Skill: 展开为多个子任务
        return [
            SubtaskSpec(
                id=str(uuid4()),
                skill_name=skill_name,
                skill_step_id=step.id,
                description=step.description,
                capabilities=[step.required_capability] if step.required_capability else [],
                depends_on=self._get_step_dependencies(i),
            )
            for i, step in enumerate(workflow_info.steps)
        ]
    else:
        # Atomic Skill: 单个子任务
        return [SubtaskSpec(id=str(uuid4()), skill_name=skill_name, description="...")]
```

---

## 4. 测试 AIME 组件

### 4.1 单元测试 Intent Analyzer

```python
# tests/unit/aime/test_intent_analyzer.py

import pytest
from backend.aime.intent.analyzer import IntentAnalyzer
from backend.aime.intent.models import IntentResult

@pytest.fixture
def analyzer():
    return IntentAnalyzer()

@pytest.mark.asyncio
async def test_simple_greeting(analyzer):
    result = await analyzer.analyze("你好")
    assert result.action == "direct_reply"
    assert result.confidence > 0.8

@pytest.mark.asyncio
async def test_explicit_routing(analyzer):
    result = await analyzer.analyze("[ROUTE_TO: research] 搜索AI新闻")
    assert result.action == "delegate"
    # explicit routing should have high confidence
    assert result.confidence >= 1.0

@pytest.mark.asyncio
async def test_complex_task(analyzer):
    result = await analyzer.analyze(
        "分析最近三个月的质量数据，找出良率最低的产线，并生成报告"
    )
    assert result.action == "plan"
    assert "database" in result.capabilities or "code_execution" in result.capabilities
```

### 4.2 单元测试 Actor Factory

```python
# tests/unit/aime/test_actor_factory.py

import pytest
from backend.aime.actor_factory import ActorFactory
from backend.aime.models import SubtaskSpec

@pytest.fixture
def factory():
    return ActorFactory()

def test_explicit_agent_selection(factory):
    spec = SubtaskSpec(
        id="task-001",
        description="Test task",
        explicit_agent="research",
    )
    actor = factory.select_actor(spec)
    assert actor.name == "research"

def test_capability_matching(factory):
    spec = SubtaskSpec(
        id="task-002",
        description="Search task",
        capabilities=["web_search"],
    )
    actor = factory.select_actor(spec)
    assert actor.name == "research"

def test_fallback_to_generic(factory):
    spec = SubtaskSpec(
        id="task-003",
        description="Unknown task",
        capabilities=["unknown_capability"],
    )
    actor = factory.select_actor(spec)
    assert actor.name == "generic"
```

### 4.3 集成测试

```python
# tests/integration/test_aime_flow.py

import pytest
from backend.aime.planner import AIMEPlanner

@pytest.mark.asyncio
async def test_simple_query_flow():
    planner = AIMEPlanner()
    events = []

    async for event in planner.process("你好", thread_id="test-thread"):
        events.append(event)

    # Should have text_delta and done events
    event_types = [e["event"] for e in events]
    assert "text_delta" in event_types
    assert "done" in event_types
    # Should NOT have task events for simple query
    assert "task_spawned" not in event_types

@pytest.mark.asyncio
async def test_complex_task_flow():
    planner = AIMEPlanner()
    events = []

    async for event in planner.process(
        "分析数据并生成报告",
        thread_id="test-thread"
    ):
        events.append(event)

    # Should have planning events
    event_types = [e["event"] for e in events]
    assert "todos_updated" in event_types
    assert "task_spawned" in event_types
    assert "task_completed" in event_types
```

---

## 5. 调试技巧

### 5.1 启用详细日志

```python
# backend/aime/intent/analyzer.py

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class IntentAnalyzer:
    async def analyze(self, message: str, context: dict | None = None) -> IntentResult:
        logger.debug(f"Analyzing message: {message[:100]}...")

        for classifier in self.classifiers:
            result = await classifier.classify(message, context, self._domain)
            logger.debug(f"{classifier.name}: {result}")
            if result is not None:
                logger.info(f"Classified by {classifier.name}: {result.action}")
                return result

        # Fallback
        return IntentResult(action="clarify", confidence=0.3)
```

### 5.2 SSE 事件调试

在浏览器开发者工具中查看 EventSource 消息：

```javascript
// 在控制台执行
const es = new EventSource('/api/chat');
es.onmessage = (e) => console.log('SSE:', JSON.parse(e.data));
```

### 5.3 查看 Progress List 状态

```python
# 在 Planner 中添加调试方法
class AIMEPlanner:
    def debug_progress(self) -> dict:
        return {
            "total": len(self.progress.items),
            "pending": sum(1 for i in self.progress.items.values() if i.status == "pending"),
            "in_progress": sum(1 for i in self.progress.items.values() if i.status == "in_progress"),
            "completed": sum(1 for i in self.progress.items.values() if i.status == "completed"),
            "items": [
                {"id": i.task_id, "status": i.status, "agent": i.assigned_agent}
                for i in self.progress.items.values()
            ],
        }
```

---

## 6. 常见问题

### Q: 为什么我的自定义 Agent 没有被选中？

检查以下几点：
1. `AGENTS.md` frontmatter 格式是否正确（YAML 语法）
2. `capabilities` 是否与 SubtaskSpec 中的要求匹配
3. 是否有更高分的 Agent 被选中（检查日志）

### Q: Workflow Skill 步骤没有按顺序执行？

确保 `depends_on` 正确设置：
```python
# 每个步骤依赖前一个
depends_on=[previous_step_id] if i > 0 else []
```

### Q: 意图识别不准确？

1. 检查 Classifier 优先级顺序
2. 添加更多关键词到 KeywordClassifier
3. 调整 LLMClassifier 的 prompt

---

## 参考资料

- [AIME 论文](./AIME.pdf): ByteDance 的 AIME 架构设计
- [spec.md](./spec.md): 完整功能规格
- [data-model.md](./data-model.md): 核心数据结构
- [contracts/](./contracts/): 接口定义
