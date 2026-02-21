# 011 - 简化 Supervisor 架构

## 背景

### 当前架构问题

```
backend/supervisor.py（混合文件）
├── 【传统 Supervisor】Lines 54-105 ← 在 AIME 中没用到
│   ├── build_supervisor()
│   ├── supervisor_agent (create_agent)
│   ├── route tool
│   └── ROUTER_PROMPT_TEMPLATE
│
└── 【AIME 入口】Lines 108-155 ← 当前使用
    ├── get_aime_planner()
    └── stream_aime_response()
```

**问题**：
1. `build_supervisor()` 返回完整 supervisor graph，但 AIME 完全绕过路由逻辑
2. `supervisor_agent` 和 `route` tool 从未被调用
3. AIME 入口函数和传统 supervisor 混在同一个文件
4. 概念混乱：文件名叫 "supervisor" 但实际主要功能是 AIME

### AIME 和 LangGraph 的关系

经过深入分析，发现：

```
AIME 层（编排）                    LangGraph 层（执行+持久化）
┌──────────────────┐              ┌──────────────────┐
│ ProgressManager  │ ←任务进度    │                  │
│ (内存)           │              │                  │
├──────────────────┤              │  Checkpointer    │
│ ContextManager   │ ←任务间上下文│  (消息历史)      │
│ (PostgreSQL)     │              │                  │
└──────────────────┘              └──────────────────┘
         ↓                                 ↑
    AIMEPlanner ──调用→ agent.astream() ──┘
                   或
                  agent.aupdate_state()
```

**关键发现**：
- AIME 有自己的状态管理（ProgressManager、ContextManager）
- 但**消息历史仍然依赖 LangGraph checkpointer**
- 自建消息存储复杂度高且不必要

---

## 目标

1. 删除 `supervisor.py`，移除传统 supervisor 逻辑
2. 将 `build_history_graph()` 放到 `checkpointer_store.py`
3. 将 AIME 入口函数移到 `backend/aime/__init__.py`
4. 保留 LangGraph checkpointer 用于消息持久化

---

## 修改后的 AIME 架构

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         用户请求                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    backend/aime/__init__.py                 │
│                                                             │
│  stream_aime_response(thread_id, message, context)          │
│       │                                                     │
│       └──→ get_aime_planner() ──→ AIMEPlanner.process()    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    backend/aime/planner.py                  │
│                                                             │
│  AIMEPlanner                                                │
│  ├── IntentAnalyzer → 意图分析                              │
│  ├── ActorFactory → Agent 选择                              │
│  ├── ProgressManager → 任务进度追踪                          │
│  └── ContextManager → 任务间上下文                           │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌──────────┐    ┌──────────┐    ┌──────────┐
       │direct_   │    │delegate  │    │ plan     │
       │reply     │    │          │    │          │
       └──────────┘    └──────────┘    └──────────┘
              │               │               │
              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│               backend/checkpointer_store.py                 │
│                                                             │
│  get_history_graph().aupdate_state()  ← 保存消息            │
│  get_history_graph().aget_state()     ← 读取历史            │
│                                                             │
│  get_checkpointer()  ← 各 Agent 使用                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Checkpointer                    │
│                  (PostgreSQL / SQLite)                      │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件职责

| 组件 | 位置 | 职责 |
|------|------|------|
| `stream_aime_response()` | `backend/aime/__init__.py` | AIME 公开 API，聊天入口 |
| `get_aime_planner()` | `backend/aime/__init__.py` | 获取 AIMEPlanner 单例 |
| `AIMEPlanner` | `backend/aime/planner.py` | 意图分析、任务编排、执行 |
| `IntentAnalyzer` | `backend/aime/intent/` | 分析用户意图 |
| `ActorFactory` | `backend/aime/actor_factory.py` | 选择合适的 Agent |
| `ProgressManager` | `backend/aime/progress_manager.py` | 任务进度追踪（内存） |
| `ContextManager` | `backend/aime/context_manager.py` | 任务间上下文（PostgreSQL） |
| `build_history_graph()` | `backend/checkpointer_store.py` | 创建最小化 graph 用于消息持久化 |
| `get_history_graph()` | `backend/checkpointer_store.py` | 获取 history graph |
| `get_checkpointer()` | `backend/checkpointer_store.py` | 获取 checkpointer（各 Agent 使用） |

### 消息持久化流程

**直接回复（direct_reply）**：
```python
# AIMEPlanner._handle_direct_reply()
async for chunk in model.astream(...):
    yield chunk  # 流式输出
    output_text += chunk

# 保存到 LangGraph checkpointer
history_graph = get_history_graph()
await history_graph.aupdate_state(
    {"configurable": {"thread_id": thread_id}},
    {"messages": [HumanMessage(...), AIMessage(...)]}
)
```

**委托执行（delegate/plan）**：
```python
# 通过 agent.astream() 自动保存
config = {"configurable": {"thread_id": thread_id}}
async for chunk in agent.astream(input, config):
    yield chunk
# LangGraph 自动保存消息到 checkpointer
```

**历史读取**：
```python
# core/chat.py - get_thread_history()
history_graph = get_history_graph()
state = await history_graph.aget_state({"configurable": {"thread_id": thread_id}})
messages = state.values.get("messages", [])
```

---

## 文件结构对比

### 修改前

```
backend/
├── supervisor.py              # 混合：传统 supervisor + AIME 入口
│   ├── ROUTER_PROMPT_TEMPLATE # 没用
│   ├── build_supervisor()     # 没用的路由逻辑
│   ├── supervisor_agent       # 没用
│   ├── route tool             # 没用
│   ├── get_aime_planner()     # AIME 入口
│   └── stream_aime_response() # AIME 入口
│
├── checkpointer_store.py      # 只管理 checkpointer
│   ├── set_checkpointer()
│   ├── get_checkpointer()
│   └── clear_checkpointer()
│
├── aime/
│   ├── planner.py             # AIMEPlanner
│   ├── actor_factory.py       # ActorFactory
│   ├── context_manager.py     # ContextManager
│   ├── progress_manager.py    # ProgressManager
│   └── intent/                # IntentAnalyzer
│
└── core/
    └── chat.py
        ├── set_agent() / get_agent()  # 管理 _agent
        └── 使用 _agent.aget_state()
```

### 修改后

```
backend/
├── checkpointer_store.py      # 管理 checkpointer + history_graph
│   ├── set_checkpointer()
│   ├── get_checkpointer()
│   ├── clear_checkpointer()
│   ├── build_history_graph()  # 新增
│   ├── set_history_graph()    # 新增
│   └── get_history_graph()    # 新增
│
├── aime/
│   ├── __init__.py            # 新增：AIME 公开 API
│   │   ├── get_aime_planner()
│   │   └── stream_aime_response()
│   ├── planner.py             # AIMEPlanner
│   ├── actor_factory.py       # ActorFactory
│   ├── context_manager.py     # ContextManager
│   ├── progress_manager.py    # ProgressManager
│   └── intent/                # IntentAnalyzer
│
└── core/
    └── chat.py
        └── 使用 get_history_graph().aget_state()

# 删除
# ├── supervisor.py  ← 完全删除
```

---

## 实现计划

### Phase 1：扩展 checkpointer_store.py

```python
# backend/checkpointer_store.py
"""Shared checkpointer and history graph store."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

_checkpointer: BaseCheckpointSaver | None = None
_history_graph: CompiledStateGraph | None = None


def set_checkpointer(checkpointer: BaseCheckpointSaver) -> None:
    """Set the global checkpointer. Must be called before agents are created."""
    global _checkpointer
    _checkpointer = checkpointer


def get_checkpointer() -> BaseCheckpointSaver | None:
    """Get the global checkpointer."""
    return _checkpointer


def clear_checkpointer() -> None:
    """Clear the global checkpointer and history graph."""
    global _checkpointer, _history_graph
    _checkpointer = None
    _history_graph = None


def build_history_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Create minimal graph for checkpointer access.

    Used for:
    - aget_state(): Read message history
    - aupdate_state(): Save messages (AIME direct_reply)
    """
    import backend.agents  # noqa: F401  # Trigger agent registration

    builder = StateGraph(MessagesState)
    builder.add_node("noop", lambda x: x)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile(checkpointer=checkpointer)


def set_history_graph(graph: CompiledStateGraph) -> None:
    """Set the global history graph."""
    global _history_graph
    _history_graph = graph


def get_history_graph() -> CompiledStateGraph | None:
    """Get the global history graph for aget_state/aupdate_state."""
    return _history_graph
```

### Phase 2：创建 backend/aime/__init__.py

```python
# backend/aime/__init__.py
"""AIME (Autonomous Intent-driven Multi-agent Executor) module.

Public API:
- stream_aime_response(): Main entry point for chat
- get_aime_planner(): Get planner singleton
"""

from typing import Any, AsyncGenerator

from backend.aime.context import AgentContext
from backend.aime.planner import AIMEPlanner

_planner: AIMEPlanner | None = None


def get_aime_planner() -> AIMEPlanner:
    """Get or create the AIME Planner singleton."""
    global _planner
    if _planner is None:
        import backend.agents  # noqa: F401
        _planner = AIMEPlanner()
    return _planner


async def stream_aime_response(
    thread_id: str,
    message: str,
    context: AgentContext | dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream AIME response as SSE events.

    Args:
        thread_id: Conversation thread ID
        message: User message
        context: AgentContext or legacy dict

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
```

### Phase 3：更新调用方

**main.py**：
```python
# 修改前
from backend.supervisor import build_supervisor
from backend.core.chat import set_agent
_agent = build_supervisor(checkpointer=_checkpointer)
set_agent(_agent)

# 修改后
from backend.checkpointer_store import build_history_graph, set_history_graph
_history_graph = build_history_graph(checkpointer=_checkpointer)
set_history_graph(_history_graph)
```

**core/chat.py**：
```python
# 修改前
from backend.supervisor import stream_aime_response
from backend.core.chat import get_agent
state = await get_agent().aget_state(config)

# 修改后
from backend.aime import stream_aime_response
from backend.checkpointer_store import get_history_graph
state = await get_history_graph().aget_state(config)
```

**aime/planner.py**：
```python
# 修改前
from backend.core.chat import get_agent
agent = get_agent()
await agent.aupdate_state(...)

# 修改后
from backend.checkpointer_store import get_history_graph
history_graph = get_history_graph()
await history_graph.aupdate_state(...)
```

### Phase 4：删除 supervisor.py

完全删除 `backend/supervisor.py`。

---

## 修改文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/checkpointer_store.py` | 扩展 | 新增 `build_history_graph()`, `set/get_history_graph()` |
| `backend/aime/__init__.py` | 新建 | AIME 公开 API |
| `backend/main.py` | 修改 | 更新 import 和调用 |
| `backend/core/chat.py` | 修改 | 更新 import，移除 `set_agent/get_agent` |
| `backend/aime/planner.py` | 修改 | `get_agent()` → `get_history_graph()` |
| `backend/supervisor.py` | **删除** | 完全移除 |

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Import 循环 | 高 | 使用延迟导入 `import backend.agents` |
| 消息历史读取失败 | 高 | 保留 `aget_state` 调用方式不变 |
| 消息保存失败 | 高 | 保留 `aupdate_state` 调用方式不变 |
| planner.py 依赖问题 | 中 | 检查所有 `get_agent()` 调用位置 |

---

## 验收标准

1. `supervisor.py` 被完全删除
2. AIME 入口函数从 `backend/aime` 导入
3. 历史消息正确读取和保存
4. 多轮对话上下文正确
5. 所有类型检查通过
6. 启动流程更简洁

---

## 简化程度

- 删除 `supervisor.py`（~155 行）
- 移除无用的 supervisor 逻辑
- 职责更清晰：
  - `checkpointer_store.py`：管理持久化基础设施
  - `backend/aime/`：AIME 业务逻辑
  - `core/chat.py`：HTTP 端点
