# Data Model: Context Manager

**Date**: 2026-02-16
**Feature**: ContextManager for AIME task context management

## Entities

### 1. ContextEntry

任务上下文条目，存储任务执行结果及元数据。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| context_id | VARCHAR(64) | PK | 任务 ID（唯一标识） |
| thread_id | UUID | FK(conversations.id), NOT NULL | 会话 ID |
| content | TEXT | NOT NULL | 原始输出内容 |
| summary | TEXT | NULL | 摘要（长上下文时生成） |
| key_data | JSONB | NULL | 结构化关键数据 |
| output_types | TEXT[] | DEFAULT '{}' | 输出类型标签（自动分类） |
| expected_output | TEXT[] | DEFAULT '{}' | 期望输出类型（来自 SubtaskSpec） |
| token_count | INTEGER | DEFAULT 0 | token 估算值 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| last_accessed_at | TIMESTAMP | DEFAULT NOW() | 最后访问时间 |
| expires_at | TIMESTAMP | NOT NULL | 过期时间 |
| metadata | JSONB | DEFAULT '{}' | 额外元数据 |

**Relationships**:
- `thread_id` → `conversations.id` (ON DELETE CASCADE)

**Indexes**:
- `idx_task_contexts_thread_id` (thread_id) - 按会话查询
- `idx_task_contexts_expires_at` (expires_at) - 过期清理
- `idx_task_contexts_output_types` GIN (output_types) - 类型匹配

### 2. SubtaskSpec (扩展)

扩展现有 SubtaskSpec，添加 I/O 声明字段。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| expected_input | list[str] | Optional | 期望输入类型 |
| expected_output | list[str] | Optional | 期望输出类型 |

**Note**: 修改 `backend/aime/models.py`，在现有 SubtaskSpec dataclass 中添加字段。

## State Transitions

### ContextEntry Lifecycle

```
创建 (store)
    │
    ▼
┌─────────┐     访问 (get/prepare)     ┌─────────┐
│  ACTIVE │ ──────────────────────────>│  ACTIVE │
│         │    (延长过期时间)           │ (renewed)│
└─────────┘                            └─────────┘
    │                                       │
    │ 7天无访问                              │ 7天无访问
    ▼                                       ▼
┌─────────┐                            ┌─────────┐
│ EXPIRED │                            │ EXPIRED │
└─────────┘                            └─────────┘
    │                                       │
    │ cleanup_expired()                     │
    ▼                                       ▼
┌─────────┐                            ┌─────────┐
│ DELETED │                            │ DELETED │
└─────────┘                            └─────────┘
```

### 过期规则

- **创建时**: `expires_at = NOW() + 7 days`
- **访问时**: `expires_at = NOW() + 7 days` (滑动过期)
- **过期后**: `is_expired()` 返回 True，不返回数据
- **清理时**: `expires_at < NOW()` 的记录被删除

## Validation Rules

### ContextEntry

1. `context_id` 必须是有效的任务 ID 格式
2. `thread_id` 必须存在于 conversations 表
3. `content` 不能为空
4. `expires_at` 必须大于 `created_at`
5. `output_types` 只能包含预定义的类型值

### Output Types (预定义值)

```python
OUTPUT_TYPES = [
    "financial_report",   # 财务报告
    "revenue_data",       # 营收数据
    "table",              # 表格数据
    "chart",              # 图表
    "code",               # 代码片段
    "analysis_report",    # 分析报告
    "summary",            # 摘要总结
    "file",               # 生成的文件
    "raw_data",           # 原始数据（默认）
]
```

## Database Schema (SQL)

```sql
-- Migration: create_task_contexts_table

CREATE TABLE task_contexts (
    context_id VARCHAR(64) PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    summary TEXT,
    key_data JSONB,
    output_types TEXT[] DEFAULT '{}',
    expected_output TEXT[] DEFAULT '{}',
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_accessed_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_task_contexts_thread_id ON task_contexts(thread_id);
CREATE INDEX idx_task_contexts_expires_at ON task_contexts(expires_at);
CREATE INDEX idx_task_contexts_output_types ON task_contexts USING GIN(output_types);

COMMENT ON TABLE task_contexts IS 'AIME 任务上下文存储，支持滑动过期和 I/O 类型分类';
COMMENT ON COLUMN task_contexts.output_types IS '自动分类的输出类型，如 ["financial_report", "table"]';
COMMENT ON COLUMN task_contexts.expected_output IS '期望的输出类型，来自 SubtaskSpec 声明';
```

## Python Data Classes

```python
# backend/aime/context_manager.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

CONTEXT_EXPIRATION_DAYS = 7
SHORT_CONTEXT_THRESHOLD = 2000


@dataclass
class ContextEntry:
    """任务上下文条目"""

    context_id: str
    thread_id: str
    content: str
    summary: str | None = None
    key_data: dict | None = None
    output_types: list[str] = field(default_factory=list)
    expected_output: list[str] = field(default_factory=list)
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = self.last_accessed_at + timedelta(days=CONTEXT_EXPIRATION_DAYS)

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def touch(self):
        """滑动过期：更新访问时间，延长过期时间"""
        self.last_accessed_at = datetime.now()
        self.expires_at = self.last_accessed_at + timedelta(days=CONTEXT_EXPIRATION_DAYS)
```

```python
# backend/aime/models.py - SubtaskSpec 扩展

@dataclass
class SubtaskSpec:
    """Specification for a subtask."""

    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    skill_name: str | None = None
    skill_step_id: str | None = None
    explicit_agent: str | None = None
    capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    context: dict[str, Any] | None = None

    # I/O 声明（新增）
    expected_input: list[str] = field(default_factory=list)
    expected_output: list[str] = field(default_factory=list)
```
