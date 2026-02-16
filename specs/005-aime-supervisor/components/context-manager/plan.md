# Implementation Plan: Context Manager

**Branch**: `005-aime-supervisor` | **Date**: 2026-02-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/005-aime-supervisor/components/context-manager/spec.md`

## Summary

ContextManager 是 AIME 架构的核心组件，负责任务间上下文传递。采用 LRU Cache + PostgreSQL 双层存储架构，支持滑动过期（7天）、长上下文智能摘要、I/O 类型自动分类和会话恢复。集成到 Planner 的任务执行流程中，解决多任务场景下后续任务无法获取前置任务输出的问题。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, asyncpg, LangChain (LLM 调用)
**Storage**: PostgreSQL (task_contexts 表) + 内存 LRU Cache
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux server (Docker)
**Project Type**: Web application (backend component)
**Performance Goals**:
- 缓存命中: <100ms
- DB 恢复: <100ms
- 摘要生成: <3s
**Constraints**:
- 内存占用: <50MB (100 会话 × 5 任务)
- 过期时间: 7 天滑动过期
**Scale/Scope**: 100 并发会话，每会话 5 个任务

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | ContextManager 是独立服务组件，不是 Agent |
| II. 注册驱动发现 | N/A | 不涉及 Agent 注册 |
| III. 流式优先 | ✅ PASS | 不直接生成 SSE，但不阻塞流式响应 |
| IV. 包扩展性 | N/A | 不涉及包 Agent |
| V. 简洁性 | ✅ PASS | 最小化设计，仅实现必需功能 |
| VI. 测试优先 | ✅ PASS | 计划包含单元测试和集成测试 |
| VII. 分层依赖 | ✅ PASS | Planner → ContextManager → db.py |
| VIII. 接口优先 | ✅ PASS | 定义明确接口 (store, get, prepare_for_task) |
| IX. 安全边界 | ✅ PASS | thread_id 级别隔离，防止跨会话访问 |

**Gate Result**: ✅ PASS - 无违规

## Project Structure

### Documentation (this feature)

```text
specs/005-aime-supervisor/components/context-manager/
├── spec.md              # Feature specification (完成)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── context_manager.py
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── aime/
│   ├── context_manager.py    # 核心实现 (新增)
│   ├── models.py             # SubtaskSpec 扩展 (修改)
│   └── planner.py            # 集成点 (修改)
└── db.py                     # 数据库连接池 (已有)

infra/
└── migrations/
    └── versions/
        └── xxx_create_task_contexts.py  # 数据库迁移 (新增)

tests/
└── aime/
    ├── test_context_manager.py          # 单元测试 (新增)
    └── test_context_manager_integration.py  # 集成测试 (新增)
```

**Structure Decision**: 遵循现有 AIME 架构，ContextManager 作为 `backend/aime/` 下的新模块，与 Planner、ActorFactory 平级。

## Complexity Tracking

> No violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 无 | - | - |
