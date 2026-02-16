# Data Model: AIME Agent Core

**Branch**: `005-aime-supervisor` | **Date**: 2026-02-15 | **Plan**: [plan.md](./plan.md)

## Overview

本文档定义 AIME 架构的核心数据结构，作为实现的契约基础。

---

## 1. Intent Module

### 1.1 Action Type

```python
from typing import Literal

Action = Literal["direct_reply", "delegate", "plan", "clarify"]
```

| Action | 说明 | 后续行为 |
|--------|------|----------|
| `direct_reply` | 简单问题，直接回复 | Planner 生成文本响应 |
| `delegate` | 单任务，委派专业 Agent | 创建 1 个 SubtaskSpec |
| `plan` | 复杂任务，需要规划 | 创建 N 个 SubtaskSpec |
| `clarify` | 意图不清，需要追问 | 返回 clarify_questions |

### 1.2 IntentResult

```python
from dataclasses import dataclass, field

@dataclass
class IntentResult:
    """意图分析结果"""

    # ===== 核心决策 =====
    action: Action                               # Planner 下一步行为
    confidence: float = 0.0                      # 置信度 (0.0-1.0)

    # ===== 路由信息 (delegate/plan 时使用) =====
    capabilities: list[str] = field(default_factory=list)  # 所需能力
    domain: str = "general"                      # 领域标识

    # ===== 澄清信息 (clarify 时使用) =====
    clarify_questions: list[str] | None = None   # 追问问题列表
```

**使用示例**:
```python
# 简单问候
IntentResult(action="direct_reply", confidence=0.95)

# 搜索任务
IntentResult(
    action="delegate",
    confidence=0.88,
    capabilities=["web_search"],
)

# 复杂分析
IntentResult(
    action="plan",
    confidence=0.92,
    capabilities=["database", "code_execution", "document_generation"],
    domain="quality",
)

# 意图不清
IntentResult(
    action="clarify",
    confidence=0.35,
    clarify_questions=["您需要分析什么数据？", "输出什么格式？"],
)
```

---

## 2. Planner Module

### 2.1 SubtaskSpec

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SubtaskSpec:
    """Planner 输出的子任务规格，传递给 Actor Factory"""

    id: str                                      # 唯一标识 (UUID)
    description: str                             # 任务描述

    # ===== Skill 相关 =====
    skill_name: str | None = None                # Skill 名称 (有值则为 Skill 任务)
    skill_step_id: str | None = None             # Workflow Skill 的步骤 ID

    # ===== Agent 选择 =====
    explicit_agent: str | None = None            # 用户显式指定的 Agent
    capabilities: list[str] = field(default_factory=list)  # 所需能力

    # ===== 依赖管理 =====
    depends_on: list[str] = field(default_factory=list)    # 前置任务 ID 列表
    context: dict[str, Any] | None = None        # 上下文数据 (前置任务结果)
```

**使用示例**:
```python
# 普通搜索任务
SubtaskSpec(
    id="task-001",
    description="搜索最新的AI新闻",
    capabilities=["web_search"],
)

# 用户指定 Agent
SubtaskSpec(
    id="task-002",
    description="执行 SQL 查询",
    explicit_agent="sql",
)

# Skill 任务
SubtaskSpec(
    id="task-003",
    description="生成 PDF 报告",
    skill_name="pdf",
)

# Workflow Skill 步骤
SubtaskSpec(
    id="task-004",
    description="搜索研究资料",
    skill_name="research-report",
    skill_step_id="search",
    capabilities=["web_search"],
)

# 有依赖的任务
SubtaskSpec(
    id="task-005",
    description="分析搜索结果",
    capabilities=["code_execution"],
    depends_on=["task-004"],
)
```

### 2.2 ProgressItem

```python
from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime

TaskStatus = Literal["pending", "in_progress", "completed", "error", "cancelled"]

@dataclass
class ProgressItem:
    """Progress Manager 中的单个任务状态"""

    task_id: str
    description: str
    status: TaskStatus = "pending"
    result: Any = None                           # 执行结果
    error: str | None = None                     # 错误信息
    retry_count: int = 0                         # 重试次数
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_agent: str | None = None            # 分配的 Agent 名称
```

### 2.3 ProgressList

```python
from dataclasses import dataclass, field

@dataclass
class ProgressList:
    """Planner 维护的全局进度列表"""

    items: dict[str, ProgressItem] = field(default_factory=dict)

    def add(self, spec: SubtaskSpec) -> None:
        """添加新任务"""
        self.items[spec.id] = ProgressItem(
            task_id=spec.id,
            description=spec.description,
        )

    def mark_in_progress(self, task_id: str, agent: str) -> None:
        """标记任务开始执行"""
        if task_id in self.items:
            item = self.items[task_id]
            item.status = "in_progress"
            item.started_at = datetime.now()
            item.assigned_agent = agent

    def mark_completed(self, task_id: str, result: Any) -> None:
        """标记任务完成"""
        if task_id in self.items:
            item = self.items[task_id]
            item.status = "completed"
            item.completed_at = datetime.now()
            item.result = result

    def mark_error(self, task_id: str, error: str) -> None:
        """标记任务失败"""
        if task_id in self.items:
            item = self.items[task_id]
            item.status = "error"
            item.error = error
            item.retry_count += 1

    def get_ready_tasks(self) -> list[str]:
        """获取可执行的任务 (依赖已完成)"""
        # 实现依赖检查逻辑
        ...

    def to_todos(self) -> list[dict]:
        """转换为 todos 格式 (用于 SSE todos_updated 事件)"""
        return [
            {
                "content": item.description,
                "status": "completed" if item.status == "completed"
                          else "in_progress" if item.status == "in_progress"
                          else "pending",
            }
            for item in self.items.values()
        ]
```

---

## 3. Actor Factory Module

### 3.1 Actor

```python
from dataclasses import dataclass
from typing import Any
from langgraph.graph.state import CompiledStateGraph

@dataclass
class Actor:
    """Actor Factory 输出的执行单元"""

    name: str                                    # Agent 名称
    graph: CompiledStateGraph                    # 可执行的 LangGraph
    tools: list[Any] = field(default_factory=list)
    persona: str | None = None                   # 角色描述 (来自 Skill)
```

### 3.2 AgentEntry (扩展)

```python
from dataclasses import dataclass, field
from typing import Literal, Any
from langgraph.graph.state import CompiledStateGraph

AgentSource = Literal["preset", "package"]

@dataclass
class AgentEntry:
    """注册的 Agent 元信息 (扩展现有结构)"""

    name: str
    description: str
    graph: CompiledStateGraph
    tools: list[Any] = field(default_factory=list)
    icon: str = "bot"
    show_in_selector: bool = True

    # ===== 新增字段 =====
    capabilities: list[str] = field(default_factory=list)  # 声明的能力
    source: AgentSource = "preset"                         # 来源标识
```

**预设 Agent 能力声明**:

| Agent | capabilities |
|-------|-------------|
| research | `["web_search", "news_search", "academic_search"]` |
| sql | `["database", "sql_query"]` |
| generic | `["code_execution", "file_processing", "document_generation"]` |

---

## 4. Skills Module (扩展)

### 4.1 SkillStep

```python
from dataclasses import dataclass

@dataclass
class SkillStep:
    """Workflow Skill 的单个步骤"""

    id: str                                      # 步骤 ID
    description: str                             # 步骤描述
    required_capability: str | None = None       # 所需能力 (用于 Agent 匹配)
```

### 4.2 WorkflowSkillInfo

```python
from dataclasses import dataclass

@dataclass
class WorkflowSkillInfo:
    """Workflow Skill 的步骤定义 (仅 Planner 使用)"""

    name: str                                    # Skill 名称
    steps: list[SkillStep]                       # 步骤列表
```

### 4.3 Registry 结构

```python
# backend/skills/registry.py

# 现有 (保持不变)
SKILL_REGISTRY: dict[str, SkillEntry] = {}

# 新增
WORKFLOW_SKILLS: dict[str, WorkflowSkillInfo] = {}
```

---

## 5. 能力映射表

```python
# backend/aime/intent/models.py

CAPABILITY_AGENT_MAP: dict[str, str] = {
    # 搜索类
    "web_search": "research",
    "news_search": "research",
    "academic_search": "research",

    # 数据库类
    "database": "sql",
    "sql_query": "sql",

    # 通用类
    "code_execution": "generic",
    "file_processing": "generic",
    "document_generation": "generic",

    # 预留扩展
    "knowledge_base": "knowledge",
}
```

**说明**: 此映射仅供 IntentAnalyzer 快速参考，实际 Agent 选择由 Actor Factory 从 AGENT_REGISTRY 动态计算。

---

## 6. SSE 事件格式 (兼容性参考)

### 6.1 todos_updated

```typescript
interface TodosUpdatedEvent {
  todos: Array<{
    content: string;
    status: "pending" | "in_progress" | "completed";
  }>;
  timestamp: string;  // ISO 8601
}
```

### 6.2 task_spawned

```typescript
interface TaskSpawnedEvent {
  task_id: string;
  subagent_type: string;
  description: string;
}
```

### 6.3 task_completed

```typescript
interface TaskCompletedEvent {
  task_id: string;
  duration_ms: number;
  status: "success" | "error";
}
```

### 6.4 thinking

```typescript
interface ThinkingEvent {
  content: string;
  type?: "planning" | "replanning" | "routing";
}
```

---

## 7. 状态流转图

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │ dispatch
                           ▼
                    ┌─────────────┐
             ┌──────│ in_progress │──────┐
             │      └──────┬──────┘      │
             │             │             │
        error│             │success      │timeout
             │             │             │
             ▼             ▼             ▼
      ┌──────────┐  ┌───────────┐  ┌───────────┐
      │  error   │  │ completed │  │ cancelled │
      └────┬─────┘  └───────────┘  └───────────┘
           │
           │ retry (< 3)
           ▼
    ┌─────────────┐
    │   pending   │ (重新排队)
    └─────────────┘
```

---

## 下一步

1. 创建 `contracts/` 目录，定义模块接口
2. 创建 `quickstart.md` 开发者指南
3. 运行 `/speckit.tasks` 生成任务列表
