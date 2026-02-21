# 011 - AIME Checkpointer 统一管理

## 背景

当前架构存在冗余：

```
main.py
├── build_supervisor() → 返回 supervisor graph
│   └── 仅用于 aget_state() 读取历史消息
└── stream_aime_response() → AIMEPlanner
    └── 完全绕过 supervisor 路由逻辑
```

`build_supervisor()` 返回的 supervisor graph：
- **路由逻辑（route tool）**：在 AIME 架构中完全没用到
- **唯一用途**：提供 `aget_state()` 读取 LangGraph checkpoints

## 目标

1. 移除 `build_supervisor()` 的路由逻辑
2. 让 AIME 架构统一管理 checkpointer 和历史消息读取
3. 简化启动流程

## 当前 Checkpointer 使用情况

| 组件 | 使用方式 | 来源 |
|------|----------|------|
| sql agent | `create_deep_agent(..., checkpointer=get_checkpointer())` | checkpointer_store |
| research agent | `create_deep_agent(..., checkpointer=get_checkpointer())` | checkpointer_store |
| package agents | `create_deep_agent(..., checkpointer=get_checkpointer())` | checkpointer_store |
| supervisor | `builder.compile(checkpointer=checkpointer)` | main.py 传入 |
| chat.py | `_agent.aget_state(config)` | supervisor graph |

## 问题分析

1. **supervisor graph 的 checkpoints 和 agent graph 的 checkpoints 是分开的**
   - supervisor 有自己的消息历史
   - 各 agent 也有自己的消息历史
   - 读取历史时只读 supervisor 的，可能不完整

2. **AIME 架构直接调用 agent graph**
   - 绕过 supervisor，消息不会保存到 supervisor 的 checkpoints
   - 但 `get_thread_history()` 只读 supervisor 的 checkpoints

## 方案选项

### 方案 A：AIME 自建消息存储（推荐）

不依赖 LangGraph checkpointer，AIME 自己管理消息历史：

```python
# backend/aime/message_store.py
class MessageStore:
    """AIME 消息存储 - 使用 PostgreSQL"""

    async def save_message(self, thread_id: str, role: str, content: str):
        """保存消息到数据库"""

    async def get_history(self, thread_id: str) -> list[dict]:
        """读取线程历史消息"""
```

**优点**：
- 完全控制消息格式和存储
- 不依赖 LangGraph 内部实现
- 可以存储更多元数据（token 用量、耗时等）

**缺点**：
- 需要新建数据库表
- 需要迁移现有历史数据

### 方案 B：复用 LangGraph Checkpointer

创建一个最小化的 graph 仅用于 checkpointer 访问：

```python
# backend/aime/history.py
def get_history_graph(checkpointer):
    """创建最小化 graph 用于读取历史"""
    builder = StateGraph(MessagesState)
    builder.add_node("noop", lambda x: x)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile(checkpointer=checkpointer)
```

**优点**：
- 改动小，向后兼容
- 复用现有 checkpointer 基础设施

**缺点**：
- 仍然依赖 LangGraph checkpointer 内部结构
- 消息历史分散在多个 graph 的 checkpoints 中

### 方案 C：保留现状，仅清理代码

保留 `build_supervisor()` 但移除路由逻辑：

```python
def build_history_accessor(checkpointer):
    """创建历史访问器（替代 build_supervisor）"""
    # 仅编译一个空 graph 用于 aget_state
    ...
```

**优点**：
- 改动最小
- 风险低

**缺点**：
- 没有解决根本问题
- 仍然有概念混乱

## 推荐方案

**方案 A**：AIME 自建消息存储

理由：
1. AIME 架构已经有 `ContextManager` 管理任务上下文，消息存储是自然延伸
2. 可以统一存储格式，便于未来扩展（如消息搜索、导出）
3. 彻底解耦 AIME 和 LangGraph 的实现细节

## 实现计划

### Phase 1：新建消息存储

1. 创建 `messages` 表
2. 实现 `MessageStore` 类
3. 在 `AIMEPlanner` 中保存消息

### Phase 2：迁移历史读取

1. 修改 `get_thread_history()` 使用 `MessageStore`
2. 移除 `chat.py` 中的 `_agent` 依赖

### Phase 3：清理遗留代码

1. 移除 `build_supervisor()` 或简化为 `build_history_accessor()`
2. 移除 `set_agent()` / `get_agent()`
3. 更新 `main.py` 启动流程

### Phase 4：数据迁移（可选）

1. 迁移现有 LangGraph checkpoints 中的消息到新表
2. 或保留旧数据，仅新对话使用新存储

## 数据库设计

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(32) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system', 'tool'
    content TEXT NOT NULL,
    metadata JSONB,  -- tool_calls, token_usage, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),

    INDEX idx_messages_thread_id (thread_id),
    INDEX idx_messages_created_at (created_at)
);
```

## 影响范围

### 需要修改的文件

- `backend/main.py` - 移除 build_supervisor 调用
- `backend/core/chat.py` - 移除 _agent 依赖
- `backend/supervisor.py` - 移除 build_supervisor 或重命名
- `backend/aime/planner.py` - 添加消息保存
- 新增 `backend/aime/message_store.py`
- 新增 `infra/migrations/xxx_create_messages_table.py`

### 可以保留的文件

- `backend/checkpointer_store.py` - 各 agent 仍需要 checkpointer
- 各 agent 文件 - 无需修改

## 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 历史消息丢失 | 高 | 保留旧 checkpointer，渐进迁移 |
| 消息格式不兼容 | 中 | 设计通用格式，兼容现有前端 |
| 性能问题 | 低 | 使用索引，按需分页加载 |

## 验收标准

1. `get_thread_history()` 返回完整消息历史
2. 新对话消息正确保存和读取
3. `build_supervisor()` 被移除或大幅简化
4. 启动流程更简洁
