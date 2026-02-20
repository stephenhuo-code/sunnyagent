# Tasks: Langfuse 可观测性集成

**Input**: Design documents from `/specs/007-langfuse-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, Langfuse deployment, and dependency configuration

- [x] T001 Add `langfuse>=3.0.0` and `httpx` dependencies to pyproject.toml
- [x] T002 [P] Update .env.example with Langfuse environment variables in infra/.env.example
- [x] T003 [P] Add Langfuse service to docker-compose.yml in infra/docker-compose.yml
- [x] T004 Create database migration for langfuse_user_mapping table in infra/migrations/versions/005_create_langfuse_user_mapping.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Langfuse service infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create LangfuseService class with initialization and health check in backend/services/langfuse_service.py
- [x] T006 Create LangfuseAdminClient class for Admin API operations in backend/services/langfuse_admin_client.py
- [x] T007 Add Langfuse initialization to FastAPI lifespan with graceful degradation in backend/main.py
- [x] T008 Create LangfuseUserMapping model in backend/services/langfuse_service.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 & 2 - Agent 执行链路追踪 + 监控 (Priority: P1) 🎯 MVP

**Goal**: 实现 Agent 执行链路的完整追踪，包括 AIME 各组件的 Span 记录，错误追踪，以及利用 Langfuse 内置仪表盘进行监控

**Independent Test**: 发起一次对话请求，在 Langfuse 界面中查看完整的 Trace 记录和监控仪表盘

### Implementation for User Story 1 & 2

- [x] T009 [US1] Add @observe decorator and CallbackHandler injection to AIMEPlanner in backend/aime/planner.py
- [x] T010 [P] [US1] Add custom Span for IntentAnalyzer in backend/aime/intent/analyzer.py
- [x] T011 [P] [US1] Add custom Span for ActorFactory in backend/aime/actor_factory.py
- [x] T012 [P] [US1] Add custom Span for GenericActor execution in backend/aime/planner.py
- [x] T013 [US1] Add propagate_attributes for session_id and user_id in trace context in backend/aime/planner.py
- [x] T014 [US1] Implement error capture with status and stack trace in Span in backend/aime/planner.py
- [x] T015 [US1] Add Token consumption tracking to LLM calls in backend/aime/planner.py
- [ ] T016 [US2] Verify Langfuse dashboard shows Agent metrics (调用次数、成功率、响应时间、Token 消耗) - manual validation

**Checkpoint**: Agent 执行链路追踪功能完成，可在 Langfuse 界面查看 Trace 和监控仪表盘

---

## Phase 4: User Story 5 - 系统管理集成 (Priority: P1)

**Goal**: 从 SunnyAgent 系统管理界面访问 Langfuse，实现账号同步

**Independent Test**: 在系统管理界面点击 Langfuse 链接，验证新窗口打开；创建/禁用用户后验证 Langfuse 账号同步

### Implementation for User Story 5

- [x] T017 [US5] Implement create_user method in LangfuseAdminClient in backend/services/langfuse_admin_client.py
- [x] T018 [P] [US5] Implement disable_user method in LangfuseAdminClient in backend/services/langfuse_admin_client.py
- [x] T019 [P] [US5] Implement delete_user method in LangfuseAdminClient in backend/services/langfuse_admin_client.py
- [x] T020 [US5] Add Langfuse user sync hooks to user CRUD operations in backend/auth/database.py
- [x] T021 [US5] Add Langfuse URL configuration endpoint or constant in backend/services/langfuse_service.py
- [x] T022 [US5] Create SystemSettings component with Langfuse link (opens in new window) in frontend/src/components/Admin/SystemSettings.tsx
- [x] T023 [US5] Add Langfuse health status indicator to SystemSettings in frontend/src/components/Admin/SystemSettings.tsx
- [x] T024 [US5] Integrate SystemSettings into Admin layout in frontend/src/components/Admin/

**Checkpoint**: 系统管理集成完成，管理员可从界面访问 Langfuse，账号自动同步

---

## Phase 5: User Story 3 - 测试数据集与评估 (Priority: P2)

**Goal**: 支持通过 Langfuse Dataset + Experiment 评估 Agent，调用真实的 `/api/chat` 接口

**Independent Test**: 在 Langfuse 中创建测试数据集，运行评估脚本，查看评估结果

### Implementation for User Story 3

- [x] T025 [US3] Create evaluation script template calling /api/chat in scripts/evaluation/run_experiment.py
- [x] T026 [P] [US3] Create sample dataset JSON file for testing in scripts/evaluation/sample_dataset.json
- [x] T027 [US3] Implement LLM-as-a-Judge evaluator configuration in scripts/evaluation/evaluators.py
- [x] T028 [US3] Add documentation for creating datasets and running experiments in scripts/evaluation/README.md

**Checkpoint**: Agent 评估功能完成，开发人员可创建数据集并运行评估

---

## Phase 6: User Story 4 - Prompt Playground (Priority: P3)

**Goal**: 支持在 Langfuse Prompt Playground 中测试 LLM 和 Tool Calling

**Independent Test**: 在 Langfuse Playground 中输入 Prompt，查看 LLM 响应

### Implementation for User Story 4

- [x] T029 [US4] Document Prompt Playground usage with SunnyAgent LLM configuration in docs/langfuse-playground.md
- [x] T030 [US4] Export sample tool JSON schemas for Playground testing in scripts/evaluation/tool_schemas/

**Checkpoint**: Playground 调试支持完成

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, documentation, and final validation

- [x] T031 Implement graceful degradation when Langfuse unavailable (skip tracing, log warning) in backend/services/langfuse_service.py
- [x] T032 [P] Add Langfuse sample rate configuration support in backend/services/langfuse_service.py
- [x] T033 [P] Add timeout handling in Trace (record partial trace on timeout) in backend/aime/planner.py
- [x] T034 Update CLAUDE.md with Langfuse integration information
- [ ] T035 Run quickstart.md validation scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1&2 (Phase 3)**: Depends on Foundational - Core tracing functionality
- **US5 (Phase 4)**: Depends on Foundational - Can run in parallel with Phase 3
- **US3 (Phase 5)**: Depends on Phase 3 (needs tracing working for experiments)
- **US4 (Phase 6)**: Depends on Foundational - Can run in parallel with Phase 3-5
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

```
┌─────────────────┐
│  Setup (P1)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Foundational(P2)│
└────────┬────────┘
         │
    ┌────┴────┬─────────────┐
    │         │             │
    ▼         ▼             ▼
┌───────┐ ┌───────┐    ┌───────┐
│US1&2  │ │  US5  │    │  US4  │
│(P1)   │ │ (P1)  │    │ (P3)  │
└───┬───┘ └───────┘    └───────┘
    │
    ▼
┌───────┐
│  US3  │
│ (P2)  │
└───────┘
```

### Parallel Opportunities

**Setup Phase:**
```
T002 (.env.example) ║ T003 (docker-compose)
```

**User Story 1&2:**
```
T010 (IntentAnalyzer) ║ T011 (ActorFactory) ║ T012 (GenericActor)
```

**User Story 5:**
```
T018 (disable_user) ║ T019 (delete_user)
```

**Polish:**
```
T032 (sample rate) ║ T033 (timeout handling)
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2, 5)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 & 2 (Trace + 监控)
4. Complete Phase 4: User Story 5 (系统管理集成)
5. **STOP and VALIDATE**: Test tracing, monitoring, and admin integration
6. Deploy/demo MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1&2 → Test tracing in Langfuse → MVP!
3. Add US5 → Test admin integration → Deploy
4. Add US3 → Test evaluation → Deploy
5. Add US4 → Test playground → Deploy
6. Polish → Final release

---

## Notes

- [P] tasks = different files, no dependencies
- US1 and US2 are combined in Phase 3 because they share the same tracing infrastructure
- Langfuse entities (Trace, Span, Dataset) are managed by Langfuse service, not SunnyAgent database
- Only `langfuse_user_mapping` table is added to SunnyAgent database
- Manual validation tasks (T016) require Langfuse UI verification
