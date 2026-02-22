# Tasks: 定时任务功能 (Scheduled Tasks)

**Input**: Design documents from `/specs/013-scheduled-tasks/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/scheduled_tasks/`
- **Frontend**: `frontend/src/components/Admin/ScheduledTasks/`
- **Tests**: `backend/tests/scheduled_tasks/`
- **Migrations**: `infra/migrations/versions/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and database schema

- [x] T001 Add APScheduler dependency to pyproject.toml: `apscheduler>=4.0.0a5`
- [x] T002 Create backend/scheduled_tasks/ module directory structure with __init__.py
- [x] T003 Create database migration for scheduled_tasks and task_executions tables in infra/migrations/versions/xxx_create_scheduled_tasks_tables.py
- [x] T004 Create data/scheduled_tasks/ runtime directory and add to .gitignore

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement Pydantic models (ScheduledTask, TaskExecution, request/response schemas) in backend/scheduled_tasks/models.py
- [x] T006 [P] Implement APScheduler initialization with SQLAlchemyDataStore in backend/scheduled_tasks/scheduler.py
- [x] T007 [P] Implement trigger factory functions (DateTrigger, CronTrigger) in backend/scheduled_tasks/triggers.py
- [x] T008 Implement repository layer (CRUD for scheduled_tasks, task_executions) in backend/scheduled_tasks/database.py
- [x] T009 Implement script file manager (create, read, update, delete scripts in user directories) in backend/scheduled_tasks/script_manager.py
- [x] T010 Integrate APScheduler lifecycle into FastAPI lifespan in backend/main.py
- [x] T011 [P] Create frontend API client for scheduled tasks in frontend/src/api/scheduledTasks.ts

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 创建定时任务 (Priority: P1) 🎯 MVP

**Goal**: Users can create scheduled tasks with title, prompt, schedule type (once/daily/weekly/monthly), and optional expiry date

**Independent Test**: Create a daily task at 09:00, verify task record saved, script file generated, APScheduler job registered

### Implementation for User Story 1

- [x] T012 [US1] Implement ScheduledTaskService.create_task() with script file generation and APScheduler registration in backend/scheduled_tasks/service.py
- [x] T013 [US1] Implement POST /api/scheduled-tasks endpoint in backend/scheduled_tasks/router.py
- [x] T014 [US1] Implement schedule_config validation for all four schedule types (once/daily/weekly/monthly) in backend/scheduled_tasks/validators.py
- [x] T015 [P] [US1] Create TaskForm component with title, prompt, schedule type selector, date/time pickers in frontend/src/components/Admin/ScheduledTasks/TaskForm.tsx
- [x] T016 [P] [US1] Create schedule type specific inputs (week day selector, month day selector) in frontend/src/components/Admin/ScheduledTasks/ScheduleInputs.tsx
- [x] T017 [US1] Implement useScheduledTasks hook with createTask mutation in frontend/src/hooks/useScheduledTasks.ts
- [x] T018 [US1] Add "定时任务" menu item to Admin Panel sidebar in frontend/src/components/Admin/AdminPanel.tsx
- [x] T019 [US1] Register scheduled_tasks router in backend/api/__init__.py

**Checkpoint**: Users can create all four types of scheduled tasks through the UI

---

## Phase 4: User Story 2 - 管理定时任务列表 (Priority: P1)

**Goal**: Users can view, enable/disable, edit, delete, and run tasks immediately

**Independent Test**: View task list, toggle enable/disable, edit task configuration, delete task, click "Run Now"

### Implementation for User Story 2

- [x] T020 [US2] Implement ScheduledTaskService.list_tasks() with status filter and pagination in backend/scheduled_tasks/service.py
- [x] T021 [US2] Implement ScheduledTaskService.update_task() with script file sync and APScheduler update in backend/scheduled_tasks/service.py
- [x] T022 [US2] Implement ScheduledTaskService.delete_task() with script/log cleanup and APScheduler removal in backend/scheduled_tasks/service.py
- [x] T023 [US2] Implement ScheduledTaskService.toggle_enabled() with APScheduler pause/resume in backend/scheduled_tasks/service.py
- [x] T024 [US2] Implement GET /api/scheduled-tasks (list), GET/PATCH/DELETE /api/scheduled-tasks/{id} endpoints in backend/scheduled_tasks/router.py
- [x] T025 [US2] Implement POST /api/scheduled-tasks/{id}/enable and /disable endpoints in backend/scheduled_tasks/router.py
- [x] T026 [P] [US2] Create TaskList component with "已定时"/"已完成" tabs, status toggle, action buttons in frontend/src/components/Admin/ScheduledTasks/TaskList.tsx
- [x] T027 [P] [US2] Create TaskListItem component with title, schedule display, status switch, action icons in frontend/src/components/Admin/ScheduledTasks/TaskListItem.tsx
- [x] T028 [US2] Add list, update, delete, toggle mutations to useScheduledTasks hook in frontend/src/hooks/useScheduledTasks.ts
- [x] T029 [US2] Create ScheduledTasks index component (page container) in frontend/src/components/Admin/ScheduledTasks/index.tsx
- [x] T030 [US2] Implement task executor with timeout (15min) and retry (1x, 5min delay) logic in backend/scheduled_tasks/executor.py
- [x] T031 [US2] Implement ScheduledTaskService.run_now() for immediate execution in backend/scheduled_tasks/service.py
- [x] T032 [US2] Implement POST /api/scheduled-tasks/{id}/run endpoint in backend/scheduled_tasks/router.py
- [x] T033 [US2] Integrate executor with AIME for AI prompt processing in backend/scheduled_tasks/executor.py
- [x] T034 [US2] Add Langfuse tracing to task execution in backend/scheduled_tasks/executor.py

**Checkpoint**: Full CRUD operations work, tasks can be enabled/disabled, and "Run Now" triggers immediate execution

---

## Phase 5: User Story 3 - 从对话窗口创建定时任务 (Priority: P2)

**Goal**: Users can create scheduled tasks from chat by typing schedule intent (e.g., "每天早上9点执行：分析今日新闻")

**Independent Test**: Type schedule intent in chat, verify task creation modal appears with pre-filled prompt

### Implementation for User Story 3

- [x] T035 [US3] Add scheduled task intent detection to AIME intent analyzer in backend/aime/intent/classifiers/scheduled_task.py
- [x] T036 [US3] Implement schedule intent parser (extract time, frequency, prompt) in backend/scheduled_tasks/intent_parser.py
- [x] T037 [US3] Return schedule_task action from AIME planner when intent detected in backend/aime/planner.py
- [x] T038 [US3] Handle schedule_task SSE event in frontend chat to open TaskForm modal in frontend/src/hooks/useChat.ts
- [x] T039 [US3] Add pre-fill support to TaskForm component for chat-initiated creation in frontend/src/components/Admin/ScheduledTasks/TaskForm.tsx

**Checkpoint**: Users can create tasks directly from chat conversation

---

## Phase 6: User Story 4 - 查看任务执行历史 (Priority: P3)

**Goal**: Users can view execution history for each task, including status, duration, and logs

**Independent Test**: Click history button on a task, view execution list, click execution to see full log

### Implementation for User Story 4

- [x] T040 [US4] Implement TaskExecutionService.list_executions() with pagination in backend/scheduled_tasks/service.py
- [x] T041 [US4] Implement TaskExecutionService.get_execution_detail() with log content in backend/scheduled_tasks/service.py
- [x] T042 [US4] Implement GET /api/scheduled-tasks/{id}/executions and /executions/{eid} endpoints in backend/scheduled_tasks/router.py
- [x] T043 [US4] Implement log file writer during task execution in backend/scheduled_tasks/executor.py
- [x] T044 [P] [US4] Create TaskHistory component with execution list in frontend/src/components/Admin/ScheduledTasks/TaskHistory.tsx
- [x] T045 [P] [US4] Create ExecutionDetail modal with log viewer in frontend/src/components/Admin/ScheduledTasks/ExecutionDetail.tsx
- [x] T046 [US4] Add execution history queries to useScheduledTasks hook in frontend/src/hooks/useScheduledTasks.ts

**Checkpoint**: Users can view complete execution history and logs for any task

---

## Phase 7: Admin Features (Cross-Cutting)

**Purpose**: Admin-only features for viewing all users' tasks and global settings

- [x] T047 Implement admin list all tasks endpoint GET /api/admin/scheduled-tasks in backend/scheduled_tasks/router.py
- [x] T048 Implement global settings endpoints GET/PATCH /api/admin/scheduled-tasks/settings in backend/scheduled_tasks/router.py
- [x] T049 Store global enabled setting in system_settings table or config in backend/scheduled_tasks/settings.py
- [x] T050 Add admin task list view to Admin Panel (read-only, all users) in frontend/src/components/Admin/ScheduledTasks/AdminTaskList.tsx

---

## Phase 8: Polish & Edge Cases

**Purpose**: Handle edge cases, cleanup, and validation

- [x] T051 Implement one-time task completion (move to "completed" after execution) in backend/scheduled_tasks/executor.py
- [x] T052 Implement expiry date check and auto-move to "completed" in backend/scheduled_tasks/cleanup.py
- [x] T053 Implement user deletion cleanup hook (delete all tasks, scripts, logs) in backend/auth/database.py
- [x] T054 Implement 90-day log retention cleanup job in backend/scheduled_tasks/cleanup.py
- [x] T055 Add delete confirmation dialog for running tasks in frontend/src/components/Admin/ScheduledTasks/index.tsx
- [x] T056 Handle monthly 31st fallback to last day of month in backend/scheduled_tasks/triggers.py
- [x] T057 Handle script file missing error gracefully in backend/scheduled_tasks/executor.py
- [x] T058 Run quickstart.md validation and smoke tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational (can run parallel with US1)
- **User Story 3 (Phase 5)**: Depends on US1 (needs TaskForm component)
- **User Story 4 (Phase 6)**: Depends on US2 (needs executor with logging)
- **Admin Features (Phase 7)**: Depends on US2
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (Create) | Foundational | US2 (backend models shared) |
| US2 (Manage) | Foundational | US1 (backend models shared) |
| US3 (Chat) | US1 | - |
| US4 (History) | US2 | - |

### Parallel Opportunities

**Within Foundational (Phase 2)**:
- T006, T007, T011 can run in parallel

**Within User Story 1**:
- T015, T016 (frontend components) can run in parallel

**Within User Story 2**:
- T026, T027 (frontend components) can run in parallel

**Within User Story 4**:
- T044, T045 (frontend components) can run in parallel

---

## Parallel Example: User Story 2

```bash
# After T020-T025 (backend) complete:

# Launch frontend components in parallel:
Task: "Create TaskList component in frontend/src/components/Admin/ScheduledTasks/TaskList.tsx"
Task: "Create TaskListItem component in frontend/src/components/Admin/ScheduledTasks/TaskListItem.tsx"

# Then sequential:
Task: "Add mutations to useScheduledTasks hook"
Task: "Create ScheduledTasks index component"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (4 tasks)
2. Complete Phase 2: Foundational (7 tasks)
3. Complete Phase 3: User Story 1 - Create (8 tasks)
4. Complete Phase 4: User Story 2 - Manage (15 tasks)
5. **STOP and VALIDATE**: Test creating, listing, editing, deleting, enabling/disabling tasks
6. Deploy MVP

### Incremental Delivery

| Milestone | Phases | Value Delivered |
|-----------|--------|-----------------|
| MVP | 1-4 | Create and manage scheduled tasks |
| +Chat | 5 | Create tasks from conversation |
| +History | 6 | View execution logs |
| +Admin | 7 | Admin oversight |
| Production | 8 | Edge cases handled |

### Task Summary

| Phase | Tasks | Priority |
|-------|-------|----------|
| 1. Setup | 4 | Required |
| 2. Foundational | 7 | Required |
| 3. US1 Create | 8 | P1 MVP |
| 4. US2 Manage | 15 | P1 MVP |
| 5. US3 Chat | 5 | P2 |
| 6. US4 History | 7 | P3 |
| 7. Admin | 4 | P2 |
| 8. Polish | 8 | Required |
| **Total** | **58** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 and US2 are both P1 priority and should be completed together for MVP
- Backend tasks generally precede their corresponding frontend tasks
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
