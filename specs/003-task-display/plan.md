# Implementation Plan: Task Display Mode Redesign

**Branch**: `003-task-display` | **Date**: 2025-02-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-task-display/spec.md`

## Summary

重新设计前端任务显示模式，支持三种场景（快速回答、专有 Agent、自主规划）的三层显示结构（思考区、执行区、结果区）。后端扩展 SSE 事件契约，基于 DeepAgents Middleware 架构实现状态驱动的事件发射。

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, LangGraph, DeepAgents, React 19, Vite 7
**Storage**: PostgreSQL (via asyncpg + LangGraph AsyncPostgresSaver)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Web (Linux server backend, modern browsers frontend)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: SSE 事件到 UI 渲染 <100ms, 展开/折叠操作 <50ms
**Constraints**: 支持 10+ 并行任务无卡顿, 向后兼容现有 SSE 事件
**Scale/Scope**: 现有用户基础, 新增 3 个 SSE 事件类型, 增强 3 个现有事件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | 不创建新 Agent，仅扩展流式事件 |
| II. 注册驱动发现 | ✅ PASS | 不涉及 Agent 注册，使用现有 Middleware |
| III. 流式优先 | ✅ PASS | 核心功能：扩展 SSE 事件支持三层显示 |
| IV. 包扩展性 | ✅ PASS | 不涉及包 Agent |
| V. 简洁性 | ✅ PASS | 复用 DeepAgents TodoListMiddleware/SubAgentMiddleware，最小新增代码 |
| VI. 测试优先 | ✅ PASS | 计划包含前后端测试 |
| VII. 分层依赖 | ✅ PASS | stream_handler 扩展不引入新依赖层 |
| VIII. 接口优先 | ✅ PASS | SSE 事件契约已在 spec 中定义 |
| IX. 安全边界 | ✅ PASS | 不涉及代码执行或权限变更 |

**Gate Result**: ✅ PASS - 可进入 Phase 0

### Post-Phase 1 Re-check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | 设计不修改任何 Agent 代码 |
| II. 注册驱动发现 | ✅ PASS | 不涉及 |
| III. 流式优先 | ✅ PASS | SSE 事件契约已定义，支持流式更新 |
| IV. 包扩展性 | ✅ PASS | 不涉及 |
| V. 简洁性 | ✅ PASS | 复用现有 Middleware，无过度抽象 |
| VI. 测试优先 | ✅ PASS | quickstart.md 包含测试场景 |
| VII. 分层依赖 | ✅ PASS | 前端组件分层清晰（容器 → 节点 → 详情） |
| VIII. 接口优先 | ✅ PASS | contracts/sse-events.ts 定义完整契约 |
| IX. 安全边界 | ✅ PASS | 不涉及敏感操作 |

**Post-Design Gate Result**: ✅ PASS - 可进入 Phase 2 (tasks)

## Project Structure

### Documentation (this feature)

```text
specs/003-task-display/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (SSE event schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── stream_handler.py    # 扩展：处理 updates 流模式，发射新事件
├── middleware/          # 新增目录
│   └── event_emission.py # EventEmissionMiddleware (可选)
└── agents/
    └── (现有 Agent 无需修改)

frontend/
├── src/
│   ├── types/
│   │   └── index.ts     # 扩展 SSE 事件类型定义
│   ├── hooks/
│   │   └── useChat.ts   # 扩展事件处理逻辑
│   └── components/
│       ├── ThinkingBubble.tsx   # 新增：思考区组件
│       ├── TaskTree.tsx         # 新增：任务树组件
│       ├── TaskNode.tsx         # 新增：任务节点组件
│       ├── ToolCallList.tsx     # 新增：工具调用列表
│       └── MessageBubble.tsx    # 修改：集成三层结构
└── tests/
    └── components/      # 组件测试
```

**Structure Decision**: Web application structure (Option 2), 后端扩展 stream_handler.py，前端新增组件实现三层显示。

## Complexity Tracking

> No violations requiring justification.

