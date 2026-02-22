# Implementation Plan: 定时任务功能 (Scheduled Tasks)

**Branch**: `013-scheduled-tasks` | **Date**: 2026-02-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-scheduled-tasks/spec.md`

## Summary

实现定时任务功能，允许用户创建、管理和执行定时任务。采用 APScheduler + 脚本文件的执行模式，通过 PostgreSQL 持久化调度任务，集成到现有管理面板弹窗中。支持一次性、每日、每周、每月四种计划类型，用户数据按目录隔离，任务执行通过 Langfuse 追踪。

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, APScheduler (with PostgreSQL job store), asyncpg, deepagents, langfuse
- Frontend: React 19, Vite 7, TypeScript
**Storage**: PostgreSQL (scheduled_tasks, task_executions 表), 文件系统 (脚本文件和日志)
**Testing**: pytest (backend), vitest (frontend)
**Target Platform**: Linux server (Docker), Web browser (frontend)
**Project Type**: Web application (frontend + backend)
**Performance Goals**:
- 任务列表加载 < 3s (100 任务)
- 立即运行启动 < 5s
- 调度准确率 99% (1分钟误差内)
**Constraints**:
- 单次执行超时 15 分钟
- 最大并发执行 5 个任务
- 脚本文件大小 < 64KB
- 执行日志保留 90 天
**Scale/Scope**:
- 支持 100+ 任务/用户
- 5 并发执行
- 1 重试/失败 (5分钟延迟)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Agent 隔离 | ✅ PASS | 定时任务执行通过 AIME 路由，复用现有 Agent 架构，不创建新 Agent |
| II. 注册驱动发现 | ✅ PASS | 不涉及新 Agent 注册，复用现有 AIME planner |
| III. 流式优先 | ✅ PASS | 任务执行结果保存为对话记录，立即运行可通过 SSE 反馈进度 |
| IV. 包扩展性 | ✅ PASS | 不涉及新 Agent 类型，无需修改包加载机制 |
| V. 简洁性 | ✅ PASS | 采用 APScheduler 现有库，PostgreSQL job store 复用现有数据库 |
| VI. 测试优先 | ✅ PASS | 将为调度服务、脚本管理、API 端点编写单元测试和集成测试 |
| VII. 分层依赖 | ✅ PASS | API → Service (ScheduledTaskService) → Repository → Database |
| VIII. 接口优先 | ✅ PASS | 将在 contracts/ 定义 API 接口后再实现 |
| IX. 安全边界 | ✅ PASS | 用户目录隔离，权限验证，脚本文件通过 service 访问 |

**Gate Result**: ✅ PASS - All principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/013-scheduled-tasks/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── scheduled_tasks/           # 新增：定时任务模块
│   ├── __init__.py
│   ├── models.py              # Pydantic models
│   ├── database.py            # Repository 层
│   ├── service.py             # Service 层 (ScheduledTaskService)
│   ├── scheduler.py           # APScheduler 配置和管理
│   ├── executor.py            # 任务执行器
│   └── router.py              # API 端点
├── tests/
│   └── scheduled_tasks/       # 新增：测试目录
│       ├── test_models.py
│       ├── test_service.py
│       ├── test_scheduler.py
│       └── test_api.py

frontend/src/
├── api/
│   └── scheduledTasks.ts      # 新增：API 客户端
├── components/
│   └── Admin/
│       └── ScheduledTasks/    # 新增：定时任务组件
│           ├── TaskList.tsx
│           ├── TaskForm.tsx
│           ├── TaskHistory.tsx
│           └── index.tsx
└── hooks/
    └── useScheduledTasks.ts   # 新增：状态管理 hook

data/
└── scheduled_tasks/           # 新增：运行时数据目录
    └── {user_id}/
        ├── scripts/
        └── logs/

infra/migrations/versions/
└── xxx_create_scheduled_tasks_tables.py  # 新增：数据库迁移
```

**Structure Decision**: Web application structure, extending existing backend/frontend layout with new `scheduled_tasks` module following existing patterns (auth/, conversations/).

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Phase Completion Status

### Phase 0: Research ✅ Complete

- [research.md](./research.md) - APScheduler integration patterns, FastAPI lifecycle, concurrency, retry, timeout, triggers

### Phase 1: Design & Contracts ✅ Complete

- [data-model.md](./data-model.md) - Database schema, entities, state transitions, file system structure
- [contracts/api.yaml](./contracts/api.yaml) - OpenAPI 3.1 specification for all endpoints
- [quickstart.md](./quickstart.md) - Development setup and testing guide
- CLAUDE.md updated with new technologies

### Phase 2: Task Generation (Pending)

Run `/speckit.tasks` to generate tasks.md with implementation tasks.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scheduler | APScheduler 4.x | Async-first, PostgreSQL persistence, FastAPI integration |
| Job Store | SQLAlchemyDataStore | Reuse existing PostgreSQL, auto table creation |
| Timeout | asyncio.wait_for() | Python stdlib, async-native, precise control |
| Retry | In-function logic | APScheduler has no built-in retry, flexible conditions |
| Concurrency | max_concurrent_jobs=5 | APScheduler native, prevents resource exhaustion |
| Observability | Langfuse tracing | Consistent with existing AIME architecture |
