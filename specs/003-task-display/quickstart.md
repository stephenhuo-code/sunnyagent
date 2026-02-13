# Quickstart: Task Display Mode Redesign

**Feature**: 003-task-display
**Date**: 2025-02-13

## Overview

本功能重新设计前端任务显示模式，实现三层结构（思考区、执行区、结果区），支持三种场景的差异化展示。

## Prerequisites

- Node.js 18+ (frontend)
- Python 3.11+ (backend)
- Docker (PostgreSQL)
- 已完成基础环境配置（参考 CLAUDE.md）

## Quick Setup

```bash
# 1. 启动数据库
docker compose up -d

# 2. 后端
uv sync
uv run uvicorn backend.main:app --reload --port 8008

# 3. 前端 (新终端)
cd frontend && npm install && npm run dev
```

## Implementation Checklist

### Backend (stream_handler.py)

- [ ] 处理 `updates` 流模式中的 `todos` 状态变化
- [ ] 识别 `task` 工具调用，转换为 `task_spawned`/`task_completed` 事件
- [ ] 增强 `thinking` 事件，添加 `type` 字段
- [ ] 增强 `tool_call_*` 事件，添加 `task_id` 字段
- [ ] 为每个 SSE 事件添加递增 ID（支持断点恢复）

### Frontend Types (src/types/index.ts)

- [ ] 添加 `Todo` 接口
- [ ] 添加 `SpawnedTask` 接口
- [ ] 扩展 `ThinkingState` 接口
- [ ] 扩展 `ToolCall` 接口（添加 `task_id`）
- [ ] 扩展 `SSEEvent` 联合类型

### Frontend Hook (src/hooks/useChat.ts)

- [ ] 处理 `todos_updated` 事件
- [ ] 处理 `task_spawned` 事件
- [ ] 处理 `task_completed` 事件
- [ ] 处理增强的 `thinking` 事件（带 `type`）
- [ ] 关联 `tool_call_*` 到对应的 `SpawnedTask`

### Frontend Components

- [ ] `ThinkingBubble.tsx` - 思考区组件
  - 显示规划/重规划步骤
  - 支持动画指示器

- [ ] `TaskTree.tsx` - 任务树容器
  - 渲染 Todo 列表或 SpawnedTask 列表
  - 支持空状态

- [ ] `TaskNode.tsx` - 任务节点组件
  - 显示任务名称和状态
  - 展开/折叠功能

- [ ] `ToolCallList.tsx` - 工具调用列表
  - 嵌套在 TaskNode 内
  - 显示工具调用详情

- [ ] `MessageBubble.tsx` - 修改
  - 集成三层结构
  - 根据场景显示/隐藏各层

## Testing

### 场景 1: 快速回答

```bash
# 发送简单消息，应只显示结果区
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "thread_id": "test-1"}'
```

预期：只有 `text_delta` 和 `done` 事件

### 场景 2: 专有 Agent

```bash
# 发送 SQL 查询，应显示单任务节点
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "列出所有表", "agent": "sql", "thread_id": "test-2"}'
```

预期：`task_spawned` → `tool_call_*` (带 task_id) → `task_completed` → `text_delta` → `done`

### 场景 3: 自主规划

```bash
# 发送复杂任务，应显示完整三层结构
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "比较三家公司的市场策略", "thread_id": "test-3"}'
```

预期：`thinking` (type: planning) → `todos_updated` → `task_spawned` (multiple) → ... → `done`

## Event Flow Diagrams

### 快速回答

```
text_delta → text_delta → ... → done
```

### 专有 Agent

```
task_spawned
    ↓
tool_call_start (task_id)
    ↓
tool_call_result (task_id)
    ↓
... (more tool calls)
    ↓
task_completed
    ↓
text_delta
    ↓
done
```

### 自主规划

```
thinking (type: planning)
    ↓
todos_updated (initial list)
    ↓
todos_updated (status: in_progress)
    ↓
task_spawned (t1)
task_spawned (t2)  ← 并行
    ↓
tool_call_start (task_id: t1)
tool_call_start (task_id: t2)
    ↓
tool_call_result (task_id: t1)
task_completed (t1)
todos_updated (t1 completed)
    ↓
... (continue until all done)
    ↓
text_delta
    ↓
done
```

## Troubleshooting

### 事件未触发

1. 检查后端日志，确认 `updates` 流模式有输出
2. 确认 Agent 使用了 TodoListMiddleware（需要 `write_todos` 工具）
3. 检查 SubAgentMiddleware 是否配置

### 前端不显示任务树

1. 检查浏览器 Console 的 SSE 事件日志
2. 确认 `todos_updated` 或 `task_spawned` 事件已接收
3. 检查 React DevTools 中的状态

### 断点恢复不工作

1. 检查后端是否发送了 `id` 字段
2. 检查前端 EventSource 是否发送 `Last-Event-ID` header
3. 检查网络请求中的 header

## References

- [Spec](./spec.md) - 功能规格说明
- [Data Model](./data-model.md) - 数据模型定义
- [Contracts](./contracts/sse-events.ts) - SSE 事件契约
- [Research](./research.md) - 技术调研
