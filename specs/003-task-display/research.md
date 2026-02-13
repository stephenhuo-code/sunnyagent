# Research: Task Display Mode Redesign

**Feature**: 003-task-display
**Date**: 2025-02-13

## Research Tasks

### 1. LangGraph stream_mode="updates" 行为

**Decision**: 使用 `stream_mode=["messages", "updates"]` 捕获状态变化

**Rationale**:
- LangGraph `astream()` 支持多种流模式组合
- `updates` 模式返回 `{node_name: state_update_dict}`，可捕获 `todos` 等状态变化
- 当前 stream_handler.py 已启用 `["messages", "updates"]`，但 `updates` 未被处理
- 只需添加 `updates` 处理逻辑，无需修改 Agent 代码

**Alternatives Considered**:
- 自定义 Middleware 主动发射事件：增加复杂度，需要修改 Agent 创建逻辑
- 使用 `stream_mode="custom"` + StreamWriter：需要在 Agent 代码中手动调用

### 2. DeepAgents TodoListMiddleware 集成

**Decision**: 直接监听 `todos` 状态变化，转换为 `todos_updated` 事件

**Rationale**:
- TodoListMiddleware 已在 DeepAgents 中实现
- `write_todos` 工具修改 `todos` 状态，通过 `updates` 流模式自动暴露
- Todo 数据结构简单：`{ content: string, status: "pending" | "in_progress" | "completed" }`
- 前端可直接映射 Todo 列表到任务树节点

**Alternatives Considered**:
- 自定义任务管理 Middleware：重复造轮子
- 修改 TodoListMiddleware 源码：破坏框架封装

### 3. SubAgentMiddleware task() 调用追踪

**Decision**: 通过 `tool_call_start`/`tool_call_result` 事件名称检测 `task` 工具调用

**Rationale**:
- SubAgentMiddleware 的 `task()` 工具调用会产生 `tool_call_start` 事件
- 工具名称为 `task`，可在 stream_handler 中特殊处理
- 将 `task` 工具调用转换为 `task_spawned` 事件
- 将 `task` 工具结果转换为 `task_completed` 事件

**Alternatives Considered**:
- 修改 SubAgentMiddleware 发射自定义事件：需要 fork 框架
- 在 Agent 中添加显式事件发射：增加 Agent 代码复杂度

### 4. SSE 事件 ID 追踪（断点恢复）

**Decision**: 使用 `Last-Event-ID` HTTP header 实现断点恢复

**Rationale**:
- SSE 规范支持 `Last-Event-ID` header
- 后端需为每个事件分配递增 ID
- 前端 EventSource 自动发送 `Last-Event-ID` 于重连请求
- 后端根据 ID 从断点继续发送

**Alternatives Considered**:
- 客户端维护事件缓存：增加前端复杂度
- 不支持断点恢复：用户体验差

### 5. React 状态管理策略

**Decision**: 扩展现有 `useChat` hook，使用 `useReducer` 管理复杂状态

**Rationale**:
- 现有 `useChat` hook 已处理 SSE 事件
- 新增 `todos`、`tasks` 状态字段
- 使用 `useReducer` 替代多个 `useState`，便于管理状态转换
- 保持与现有代码风格一致

**Alternatives Considered**:
- 引入 Redux/Zustand：过度工程化
- 创建新的 hook：代码分散，难以维护

### 6. 任务树组件性能优化

**Decision**: 使用 React `memo` + `useMemo` 避免不必要的重渲染

**Rationale**:
- 任务树需支持 10+ 并行任务
- 每次 `todos_updated` 只需更新变化的节点
- `memo` 组件 + `key` 属性确保精确更新
- 展开/折叠使用本地状态，不触发全局重渲染

**Alternatives Considered**:
- 虚拟列表：任务数量有限（<20），无需虚拟化
- Immutable.js：增加依赖，React 已有浅比较

## Resolved Clarifications

| Item | Resolution |
|------|------------|
| stream_mode 配置 | 使用 `["messages", "updates"]`，处理两种流 |
| task 工具识别 | 通过工具名称 `task` 识别子 Agent 调用 |
| 事件 ID 格式 | 递增整数，后端维护计数器 |
| 状态管理 | 扩展 useChat hook + useReducer |
| 性能策略 | React.memo + useMemo |

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| deepagents | >=0.2.6 | TodoListMiddleware, SubAgentMiddleware |
| langgraph | existing | astream with multiple stream modes |
| React | 19 | memo, useMemo, useReducer |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| updates 流模式数据格式变化 | Low | Medium | 版本锁定 deepagents/langgraph |
| 前端状态同步延迟 | Low | Low | 事件 ID 追踪 + 断点恢复 |
| 组件性能问题 | Low | Medium | memo 优化 + 性能测试 |
