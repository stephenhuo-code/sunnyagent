# Tasks: Context Manager

**Input**: Design documents from `specs/005-aime-supervisor/components/context-manager/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/context_manager.py

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)

---

## Phase 1: Setup

**Purpose**: Database migration and basic data model

- [x] T001 Create Alembic migration for task_contexts table in `infra/migrations/versions/003_create_task_contexts_table.py`
- [x] T002 [P] Create ContextEntry dataclass in `backend/aime/context_manager.py`
- [x] T003 [P] Add expected_input and expected_output fields to SubtaskSpec in `backend/aime/models.py`
- [x] T004 Apply migration and verify table creation with `cd infra && uv run alembic upgrade head`

**Checkpoint**: Database ready, basic data models defined

---

## Phase 2: Foundational (Core ContextManager)

**Purpose**: Core class structure that ALL user stories depend on

**⚠️ CRITICAL**: User story implementation cannot begin until this phase is complete

- [x] T005 Create ContextManager class skeleton with LRU cache in `backend/aime/context_manager.py`
- [x] T006 Implement `_estimate_tokens()` helper method (len // 3)
- [x] T007 Implement `_save_to_db()` with ON CONFLICT DO UPDATE
- [x] T008 Implement `_load_from_db()` for cache miss recovery
- [x] T009 Implement `_touch_in_db()` for sliding expiration update
- [x] T010 Add configuration constants (CONTEXT_EXPIRATION_DAYS, CONTEXT_CACHE_SIZE, SHORT_CONTEXT_THRESHOLD)

**Checkpoint**: ContextManager core ready for user story features

---

## Phase 3: User Story 1 - 基础上下文传递 (Priority: P1) 🎯 MVP

**Goal**: 后续任务能够自动获取前置任务的输出结果

**Independent Test**: `store()` 存储后 `get()` 能检索到内容，`prepare_for_task()` 返回格式化上下文

### Implementation

- [x] T011 [US1] Implement `store()` method - basic version without LLM classification in `backend/aime/context_manager.py`
- [x] T012 [US1] Implement `get()` method with thread_id validation and sliding expiration
- [x] T013 [US1] Implement `prepare_for_task()` method - single dependency, full content
- [x] T014 [US1] Integrate ContextManager into AIMEPlanner.__init__() in `backend/aime/planner.py`
- [x] T015 [US1] Add store() call after task execution in `_handle_plan()` method
- [x] T016 [US1] Add prepare_for_task() call before dependent task execution

**Checkpoint**: Multi-task scenarios now pass context between tasks. No more "please upload data" errors.

---

## Phase 4: User Story 2 - 长上下文智能处理 (Priority: P2)

**Goal**: 长上下文自动摘要，保留关键数据

**Independent Test**: >2000 tokens 内容存储后，get() 返回的 entry 包含 summary 和 key_data

### Implementation

- [x] T017 [US2] Implement `_generate_summary()` LLM helper with fallback in `backend/aime/context_manager.py`
- [x] T018 [US2] Implement `_extract_key_data()` LLM helper with fallback
- [x] T019 [US2] Update `store()` to call summarization when token_count > threshold
- [x] T020 [US2] Update `prepare_for_task()` to use summary + key_data for long contexts

**Checkpoint**: Long outputs are summarized, downstream tasks receive concise context

---

## Phase 5: User Story 3 - 多依赖上下文合并 (Priority: P3)

**Goal**: 任务依赖多个前置任务时，合理分配 token 预算

**Independent Test**: depends_on=[A, B] 时，prepare_for_task() 返回两个任务的合并输出

### Implementation

- [x] T021 [US3] Update `prepare_for_task()` to handle multiple depends_on
- [x] T022 [US3] Implement per-dependency token budget allocation (max_tokens / len(depends_on))
- [x] T023 [US3] Format merged context with markdown sections and type labels

**Checkpoint**: Complex multi-dependency tasks receive complete merged context

---

## Phase 6: User Story 4 - 任务 I/O 声明与验证 (Priority: P2)

**Goal**: 自动分类输出类型，验证 I/O 匹配

**Independent Test**: store() 后 entry.output_types 包含分类结果，expected_input 不匹配时记录警告

### Implementation

- [x] T024 [US4] Define OUTPUT_TYPES constant list in `backend/aime/context_manager.py`
- [x] T025 [US4] Implement `_classify_output_types()` LLM helper with fallback to ["raw_data"]
- [x] T026 [US4] Update `store()` to call classification and validate against expected_output
- [x] T027 [US4] Update `prepare_for_task()` to filter by expected_input match
- [x] T028 [US4] Add I/O mismatch warning logging
- [x] T029 [US4] Update task decomposition prompt in `_decompose_task()` to include I/O declarations

**Checkpoint**: Tasks have typed I/O, mismatches are logged for debugging

---

## Phase 7: User Story 5 - 会话恢复与持久化 (Priority: P2)

**Goal**: 用户关闭浏览器后可恢复上下文

**Independent Test**: 重启后端后，get() 仍能从 PostgreSQL 恢复之前存储的上下文

### Implementation

- [x] T030 [US5] Verify `_save_to_db()` persistence on store()
- [x] T031 [US5] Verify `_load_from_db()` recovery on cache miss
- [x] T032 [US5] Add graceful degradation for PostgreSQL connection failures
- [x] T033 [US5] Add error logging for DB failures without blocking task execution

**Checkpoint**: Session recovery works across browser closes and backend restarts

---

## Phase 8: User Story 6 - 上下文清理与滑动过期 (Priority: P2)

**Goal**: 滑动过期 + 定期清理 + 会话删除同步清理

**Independent Test**: 访问后 expires_at 延长，cleanup_expired() 删除过期记录

### Implementation

- [x] T034 [US6] Implement `cleanup_thread()` method (cache + DB)
- [x] T035 [US6] Implement `cleanup_expired()` method (cache + DB)
- [x] T036 [US6] Add background cleanup task in FastAPI lifespan in `backend/main.py`
- [x] T037 [US6] Call cleanup_thread() when conversation is deleted in `backend/conversations/router.py`

**Checkpoint**: Storage is automatically managed, no manual cleanup needed

---

## Phase 9: Polish & Integration

**Purpose**: Final integration and validation

- [x] T038 [P] Add unit tests for ContextManager in `tests/unit/test_context_manager.py`
- [x] T039 [P] Add integration tests in `tests/unit/test_context_manager_integration.py`
- [ ] T040 Run end-to-end test: "搜索特斯拉财报，然后分析营收趋势"
- [ ] T041 Verify no "请上传数据" errors in multi-task scenarios
- [x] T042 Run type checking with `uv run pyright backend/aime/context_manager.py`

**Checkpoint**: Feature complete and validated

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → User Stories (Phase 3-8) → Phase 9 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (P1) | Phase 2 | - |
| US2 (P2) | US1 | US4, US5, US6 |
| US3 (P3) | US1 | US4, US5, US6 |
| US4 (P2) | US1 | US2, US3, US5, US6 |
| US5 (P2) | Phase 2 | US2, US3, US4, US6 |
| US6 (P2) | Phase 2 | US2, US3, US4, US5 |

### Within User Stories

- T011 → T012 → T013 (US1 core flow)
- T014 → T015 → T016 (US1 Planner integration)

---

## Parallel Opportunities

```bash
# Phase 1: Setup (parallel)
Task T002: Create ContextEntry dataclass
Task T003: Add I/O fields to SubtaskSpec

# Phase 2 后，User Stories 可并行:
# 开发者 A: US1 (必须先完成)
# 开发者 B: US5 + US6 (存储相关)
# 开发者 C: US2 + US3 (上下文处理)
# 开发者 D: US4 (I/O 分类)

# Phase 9: Tests (parallel)
Task T038: Unit tests
Task T039: Integration tests
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T010)
3. Complete Phase 3: US1 (T011-T016)
4. **STOP and VALIDATE**: 验证多任务场景上下文传递
5. Deploy if ready

### Incremental Delivery

1. Setup + Foundational → Core ready
2. US1 → **MVP**: 基础上下文传递可用
3. US2 + US4 → 智能摘要 + I/O 分类
4. US5 + US6 → 持久化 + 清理
5. US3 → 多依赖支持
6. Polish → 测试 + 验证

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Setup | T001-T004 | DB migration, data models |
| Foundational | T005-T010 | Core ContextManager structure |
| US1 (P1) 🎯 | T011-T016 | 基础上下文传递 (MVP) |
| US2 (P2) | T017-T020 | 长上下文智能处理 |
| US3 (P3) | T021-T023 | 多依赖上下文合并 |
| US4 (P2) | T024-T029 | I/O 声明与验证 |
| US5 (P2) | T030-T033 | 会话恢复与持久化 |
| US6 (P2) | T034-T037 | 清理与滑动过期 |
| Polish | T038-T042 | 测试与验证 |

**Total**: 42 tasks
**MVP Scope**: T001-T016 (16 tasks)
