# Data Model: Task Display Mode Redesign

**Feature**: 003-task-display
**Date**: 2025-02-13

## Frontend State Entities

### Message (扩展)

现有 `Message` 类型扩展，新增任务相关字段：

```typescript
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  thinking?: ThinkingState;
  files?: FileAttachment[];
  // 新增字段
  todos?: Todo[];                    // 任务列表（来自 todos_updated）
  spawnedTasks?: SpawnedTask[];      // 子 Agent 任务列表
}
```

### Todo

复用 DeepAgents TodoListMiddleware 的数据结构：

```typescript
interface Todo {
  content: string;                                    // 任务描述
  status: "pending" | "in_progress" | "completed";   // 任务状态
}
```

**State Transitions**:
```
pending → in_progress → completed
```

**Validation Rules**:
- `content` 非空字符串
- `status` 必须是三个有效值之一

### SpawnedTask

子 Agent 执行实例：

```typescript
interface SpawnedTask {
  task_id: string;                  // 唯一标识符
  subagent_type: string;            // Agent 类型 (sql, research, etc.)
  description: string;              // 任务描述
  status: "running" | "success" | "error";  // 执行状态
  duration_ms?: number;             // 执行时长（完成后填充）
  toolCalls: ToolCall[];            // 关联的工具调用
}
```

**State Transitions**:
```
(created) → running → success
                   → error
```

**Relationships**:
- SpawnedTask 1:N ToolCall（通过 task_id 关联）

### ToolCall (扩展)

现有 `ToolCall` 类型扩展：

```typescript
interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done" | "error";
  output?: string;
  // 新增字段
  task_id?: string;                 // 关联的 SpawnedTask（可选）
}
```

### ThinkingState (扩展)

现有 `ThinkingState` 类型扩展：

```typescript
interface ThinkingStep {
  type?: "planning" | "replanning" | "routing";  // 思考类型
  content: string;                               // 思考内容
  timestamp: number;                             // 时间戳
}

interface ThinkingState {
  steps: ThinkingStep[];            // 修改：从 string[] 改为 ThinkingStep[]
  isThinking: boolean;
  startTime: number;
  durationSeconds: number;
}
```

## SSE Event Data Structures

### 现有事件（保持兼容）

```typescript
// text_delta - 无变化
interface TextDeltaEvent {
  event: "text_delta";
  data: { text: string };
}

// error - 无变化
interface ErrorEvent {
  event: "error";
  data: { message: string };
}

// done - 无变化
interface DoneEvent {
  event: "done";
  data: {};
}
```

### 增强的现有事件

```typescript
// thinking - 增加 type 字段
interface ThinkingEvent {
  event: "thinking";
  data: {
    type?: "planning" | "replanning" | "routing";  // 可选，向后兼容
    content: string;
  };
}

// tool_call_start - 增加 task_id 字段
interface ToolCallStartEvent {
  event: "tool_call_start";
  data: {
    id: string;
    task_id?: string;              // 可选，向后兼容
    name: string;
    args: Record<string, unknown>;
  };
}

// tool_call_result - 增加 task_id 字段
interface ToolCallResultEvent {
  event: "tool_call_result";
  data: {
    id: string;
    task_id?: string;              // 可选，向后兼容
    name: string;
    status: string;
    output: string;
  };
}
```

### 新增事件

```typescript
// todos_updated - 任务列表变更
interface TodosUpdatedEvent {
  event: "todos_updated";
  data: {
    todos: Todo[];
    timestamp: string;             // ISO 8601 格式
  };
}

// task_spawned - 子 Agent 任务开始
interface TaskSpawnedEvent {
  event: "task_spawned";
  data: {
    task_id: string;
    subagent_type: string;
    description: string;
  };
}

// task_completed - 子 Agent 任务完成
interface TaskCompletedEvent {
  event: "task_completed";
  data: {
    task_id: string;
    duration_ms: number;
    status: "success" | "error";
  };
}
```

### Union Type

```typescript
type SSEEvent =
  | TextDeltaEvent
  | ErrorEvent
  | DoneEvent
  | ThinkingEvent
  | ToolCallStartEvent
  | ToolCallResultEvent
  | TodosUpdatedEvent
  | TaskSpawnedEvent
  | TaskCompletedEvent;
```

## Backend State (stream_handler)

### EventCounter

用于生成事件 ID（断点恢复）：

```python
@dataclass
class EventCounter:
    _counter: int = 0

    def next_id(self) -> str:
        self._counter += 1
        return str(self._counter)
```

### TaskTracker

追踪子 Agent 任务生命周期：

```python
@dataclass
class TaskTracker:
    task_id: str
    subagent_type: str
    description: str
    start_time: float

    def to_spawned_event(self) -> dict:
        return {
            "task_id": self.task_id,
            "subagent_type": self.subagent_type,
            "description": self.description,
        }

    def to_completed_event(self, status: str) -> dict:
        return {
            "task_id": self.task_id,
            "duration_ms": int((time.time() - self.start_time) * 1000),
            "status": status,
        }
```

## Entity Relationships Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Message                                                     │
│  ├─ id: string (PK)                                         │
│  ├─ role: "user" | "assistant"                              │
│  ├─ content: string                                         │
│  ├─ thinking?: ThinkingState                                │
│  ├─ todos?: Todo[]                    ←── todos_updated      │
│  └─ spawnedTasks?: SpawnedTask[]      ←── task_spawned       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  SpawnedTask                                                 │
│  ├─ task_id: string (PK)                                    │
│  ├─ subagent_type: string                                   │
│  ├─ description: string                                     │
│  ├─ status: "running" | "success" | "error"                 │
│  ├─ duration_ms?: number              ←── task_completed     │
│  └─ toolCalls: ToolCall[]                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N (via task_id)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  ToolCall                                                    │
│  ├─ id: string (PK)                                         │
│  ├─ task_id?: string (FK)             ←── tool_call_start    │
│  ├─ name: string                                            │
│  ├─ args: object                                            │
│  ├─ status: "running" | "done" | "error"                    │
│  └─ output?: string                   ←── tool_call_result   │
└─────────────────────────────────────────────────────────────┘
```

## Migration Notes

### 前端状态迁移

1. `ThinkingState.steps` 类型从 `string[]` 改为 `ThinkingStep[]`
2. 需要处理历史消息中旧格式的 `steps`（向后兼容）

### SSE 事件向后兼容

1. 所有新增字段均为可选（`?`）
2. 旧版前端忽略未知事件和未知字段
3. 新版前端需处理字段缺失的情况
