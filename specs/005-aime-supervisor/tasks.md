# Tasks: AIME Agent Core & Supervisor Optimization

**Input**: Design documents from `/specs/005-aime-supervisor/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, architecture.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/` at repository root
- **Tests**: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup (Project Structure)

**Purpose**: Create AIME module structure and base files

- [x] T001 Create AIME module directory structure in backend/aime/
- [x] T002 [P] Create backend/aime/__init__.py with module exports
- [x] T003 [P] Create backend/aime/intent/__init__.py with intent module exports
- [x] T004 [P] Create backend/aime/intent/classifiers/__init__.py
- [x] T005 [P] Create backend/aime/actors/__init__.py

---

## Phase 2: Foundational (Core Data Models & Registry Extension)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Data Models

- [x] T006 [P] Implement IntentResult and Action types in backend/aime/intent/models.py (per data-model.md §1)
- [x] T007 [P] Implement CAPABILITY_AGENT_MAP in backend/aime/intent/models.py (per data-model.md §5)
- [x] T008 [P] Implement SubtaskSpec dataclass in backend/aime/models.py (per data-model.md §2.1)
- [x] T009 [P] Implement ProgressItem and TaskStatus in backend/aime/models.py (per data-model.md §2.2)
- [x] T010 [P] Implement ProgressList with state management methods in backend/aime/models.py (per data-model.md §2.3)
- [x] T011 [P] Implement Actor dataclass in backend/aime/models.py (per data-model.md §3.1)

### Registry Extension

- [x] T012 Extend AgentEntry with capabilities and source fields in backend/registry.py (per data-model.md §3.2)
- [x] T013 Update register_agent() function to accept capabilities and source parameters in backend/registry.py

### Skills Extension

- [x] T014 [P] Implement SkillStep and WorkflowSkillInfo dataclasses in backend/skills/registry.py (per data-model.md §4)
- [x] T015 [P] Add WORKFLOW_SKILLS registry dict in backend/skills/registry.py
- [x] T016 Update skill loader to parse type/steps from SKILL.md frontmatter in backend/skills/loader.py

### Preset Agent Capabilities

- [x] T017 [P] Add capabilities=["web_search", "news_search", "academic_search"] to research agent registration in backend/agents/research.py
- [x] T018 [P] Add capabilities=["database", "sql_query"] to sql agent registration in backend/agents/sql.py

### Package Agent Capabilities

- [x] T019 Update package loader to parse capabilities from AGENTS.md frontmatter in backend/agents/loader.py

**Checkpoint**: ✅ Foundation ready - IntentResult, SubtaskSpec, AgentEntry extended, capabilities declared

---

## Phase 3: User Story 1 - Simple Query Direct Response (Priority: P1) 🎯 MVP

**Goal**: 用户提出简单问题时，系统直接回复，不进行任务分解

**Independent Test**: 发送"你好"、"1+1等于几"等简单问题，验证直接回复无任务分解

### Intent Analyzer Infrastructure (US1 requires)

- [x] T020 [P] [US1] Implement ClassifierBase abstract class in backend/aime/intent/classifiers/base.py (per contracts/intent.py)
- [x] T021 [P] [US1] Implement RuleBasedClassifier for explicit routing detection in backend/aime/intent/classifiers/rule_based.py
- [x] T022 [P] [US1] Implement KeywordClassifier for quick pattern matching in backend/aime/intent/classifiers/keyword_based.py
- [x] T023 [US1] Implement IntentAnalyzer orchestrator in backend/aime/intent/analyzer.py (composes classifiers)

### Planner - Direct Reply Path

- [x] T024 [US1] Implement AIMEPlanner base structure in backend/aime/planner.py
- [x] T025 [US1] Implement direct_reply action handling in AIMEPlanner.process() in backend/aime/planner.py
- [x] T026 [US1] Integrate IntentAnalyzer into AIMEPlanner in backend/aime/planner.py

### Supervisor Rewrite

- [x] T027 [US1] Rewrite build_supervisor() to use AIMEPlanner in backend/supervisor.py
- [x] T028 [US1] Ensure direct_reply emits correct SSE events (text_delta → done) in backend/supervisor.py

**Checkpoint**: ✅ User Story 1 complete - simple queries get direct responses without task spawning

---

## Phase 4: User Story 2 - Explicit Agent Selection (Priority: P1)

**Goal**: 用户显式指定使用某个专业 Agent 时，系统优先使用用户指定的 Agent

**Independent Test**: 前端选择 Research Agent 或消息包含 `[ROUTE_TO: research]`，验证直接路由

### Actor Factory

- [x] T029 [P] [US2] Implement ActorFactory base structure in backend/aime/actor_factory.py (per contracts/actor_factory.py)
- [x] T030 [US2] Implement explicit_agent selection (priority 1) in ActorFactory.select_actor() in backend/aime/actor_factory.py
- [x] T031 [US2] Implement error handling for non-existent explicit_agent in backend/aime/actor_factory.py

### Planner - Delegate Path with Explicit Agent

- [x] T032 [US2] Implement delegate action handling with explicit_agent in AIMEPlanner in backend/aime/planner.py
- [x] T033 [US2] Update RuleBasedClassifier to detect [ROUTE_TO: xxx] pattern in backend/aime/intent/classifiers/rule_based.py
- [x] T034 [US2] Ensure delegate emits thinking + task_spawned events in backend/aime/planner.py

### Progress Manager - Basic

- [x] T035 [US2] Implement ProgressManager base structure in backend/aime/progress_manager.py (per contracts/progress.py)
- [x] T036 [US2] Implement task tracking (add, start, complete) in ProgressManager in backend/aime/progress_manager.py
- [x] T037 [US2] Implement to_todos() for SSE todos_updated events in ProgressManager in backend/aime/progress_manager.py

**Checkpoint**: ✅ User Story 2 complete - explicit [ROUTE_TO: xxx] routes directly to specified agent

---

## Phase 5: User Story 3 - Intelligent Agent Routing (Priority: P1)

**Goal**: 用户任务未显式指定 Agent 时，系统智能识别并路由到最合适的专业 Agent

**Independent Test**: 发送"搜索最新的AI新闻"，验证创建 Research 子任务并执行

### LLM Classifier

- [x] T038 [P] [US3] Implement LLMClassifier for semantic intent analysis in backend/aime/intent/classifiers/llm_based.py
- [x] T039 [US3] Integrate LLMClassifier into IntentAnalyzer classifier chain in backend/aime/intent/analyzer.py

### Actor Factory - Capability Matching

- [x] T040 [US3] Implement match_by_capabilities() method in ActorFactory in backend/aime/actor_factory.py
- [x] T041 [US3] Implement capability scoring (preset vs package competition) in ActorFactory in backend/aime/actor_factory.py
- [x] T042 [US3] Implement preset-first tiebreaker when scores equal in ActorFactory in backend/aime/actor_factory.py

### Planner - Delegate with Capability Matching

- [x] T043 [US3] Update delegate handling to use capability matching when no explicit_agent in backend/aime/planner.py
- [x] T044 [US3] Ensure capabilities from IntentResult flow to SubtaskSpec in backend/aime/planner.py

**Checkpoint**: ✅ User Story 3 complete - "搜索AI新闻" automatically routes to Research Agent

---

## Phase 6: User Story 4 - Complex Task Decomposition (Priority: P1)

**Goal**: 用户提出复杂任务时，Planner 动态分解为多个子任务并协调执行

**Independent Test**: 发送"分析最近三个月的质量数据，找出良率最低的产线，并生成改善报告"，验证任务被正确分解

### Generic Actor

- [x] T045 [P] [US4] Implement Generic Actor with sandbox, file_tools, activate_skill in backend/aime/actors/generic.py
- [x] T046 [US4] Implement create_generic_actor() fallback in ActorFactory in backend/aime/actor_factory.py

### Planner - Plan Action

- [x] T047 [US4] Implement plan action detection in IntentAnalyzer (complex task patterns) in backend/aime/intent/classifiers/llm_based.py
- [x] T048 [US4] Implement task decomposition logic in AIMEPlanner in backend/aime/planner.py
- [x] T049 [US4] Implement SubtaskSpec[] generation with depends_on relationships in backend/aime/planner.py
- [x] T050 [US4] Implement DAG validation (no circular dependencies) in AIMEPlanner in backend/aime/planner.py

### Progress Manager - Multi-task

- [x] T051 [US4] Implement get_ready_tasks() for dependency-aware dispatch in ProgressManager in backend/aime/progress_manager.py
- [x] T052 [US4] Implement parallel task limit (max 3) in ProgressManager in backend/aime/progress_manager.py
- [x] T053 [US4] Implement get_context_for_task() to pass results to dependent tasks in ProgressManager in backend/aime/progress_manager.py

### Planner - Multi-task Execution Loop

- [x] T054 [US4] Implement execution loop: dispatch ready tasks → collect results → repeat in backend/aime/planner.py
- [x] T055 [US4] Implement result aggregation and final response generation in backend/aime/planner.py
- [x] T056 [US4] Ensure plan action emits todos_updated + multiple task_spawned events in backend/aime/planner.py

**Checkpoint**: ✅ User Story 4 complete - complex tasks decompose into tracked subtasks with dependencies

---

## Phase 7: User Story 5 - Real-time Progress Tracking (Priority: P2)

**Goal**: 用户能够实时看到任务执行进度，包括各子任务的状态

**Independent Test**: 执行复杂任务时观察前端是否显示任务树和状态更新

### Progress Manager - SSE Events

- [x] T057 [US5] Implement ProgressEvent emission for task state changes in backend/aime/progress_manager.py
- [x] T058 [US5] Ensure todos_updated events include all subtask statuses in backend/aime/progress_manager.py
- [x] T059 [US5] Verify task_spawned/task_completed events match stream_handler.py format in backend/aime/progress_manager.py

### Planner - Progress Integration

- [x] T060 [US5] Integrate ProgressManager event emission into Planner execution loop in backend/aime/planner.py
- [x] T061 [US5] Ensure task_id consistency between SubtaskSpec and SSE events in backend/aime/planner.py

**Checkpoint**: ✅ User Story 5 complete - frontend displays real-time task tree with status updates

---

## Phase 8: User Story 6 - Dynamic Re-planning (Priority: P3)

**Goal**: 当任务执行失败或结果不符合预期时，系统能够动态调整计划

**Independent Test**: 模拟 Agent 执行失败，验证 Planner 尝试替代方案

### Progress Manager - Error Handling

- [x] T062 [US6] Implement should_retry() with max 3 retries in ProgressManager in backend/aime/progress_manager.py
- [x] T063 [US6] Implement mark_error() with retry_count increment in ProgressManager in backend/aime/progress_manager.py

### Planner - Re-planning

- [x] T064 [US6] Implement handle_task_result() for failure detection in AIMEPlanner in backend/aime/planner.py
- [x] T065 [US6] Implement re-planning logic: create alternative subtasks on failure in backend/aime/planner.py
- [x] T066 [US6] Implement graceful degradation: return error after 3 retries in backend/aime/planner.py

**Checkpoint**: ✅ User Story 6 complete - failed tasks trigger re-planning up to 3 retries

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Integration, cleanup, and final validation

### Integration

- [x] T067 Update main.py imports to use new AIME module in backend/main.py (stream_aime_response available)
- [x] T068 Mark general.py as deprecated with migration note in backend/agents/general.py
- [x] T069 Verify stream_handler.py compatibility with AIME events in backend/stream_handler.py

### Clarify Action

- [x] T070 Implement clarify action handling (confidence < 0.5) in AIMEPlanner in backend/aime/planner.py
- [x] T071 Ensure clarify returns clarify_questions in text_delta response in backend/aime/planner.py

### Skills Integration

- [x] T072 Update RuleBasedClassifier to detect [SKILL: name] pattern in backend/aime/intent/classifiers/rule_based.py
- [x] T073 Implement skill_name/skill_step_id handling in ActorFactory in backend/aime/actor_factory.py
- [x] T074 Implement Workflow Skill expansion in Planner (steps → SubtaskSpec[]) in backend/aime/planner.py

### Module Exports

- [x] T075 Update backend/aime/__init__.py with all public exports
- [x] T076 Update backend/aime/intent/__init__.py with IntentAnalyzer, IntentResult exports

### Validation

- [x] T077 Run existing E2E tests to verify SSE compatibility
- [x] T078 Verify simple-chat, sql-agent, research-agent scenarios work correctly (unit tests added)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - MVP
- **User Story 2 (Phase 4)**: Depends on Foundational, benefits from US1 completion
- **User Story 3 (Phase 5)**: Depends on Foundational + US2 (Actor Factory)
- **User Story 4 (Phase 6)**: Depends on Foundational + US2 + US3 (Actor Factory + capability matching)
- **User Story 5 (Phase 7)**: Depends on US4 (Progress Manager)
- **User Story 6 (Phase 8)**: Depends on US4 + US5 (execution loop)
- **Polish (Phase 9)**: Depends on all user stories

### User Story Dependencies

```
US1 (direct_reply) ←── Foundation
        │
        ▼
US2 (explicit agent) ←── US1 + ActorFactory
        │
        ▼
US3 (intelligent routing) ←── US2 + capability matching
        │
        ▼
US4 (task decomposition) ←── US3 + Generic Actor + Progress Manager
        │
        ▼
US5 (progress tracking) ←── US4 + SSE events
        │
        ▼
US6 (re-planning) ←── US5 + error handling
```

### Within Each User Story

- Models before services
- Infrastructure before business logic
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T006, T007, T008, T009, T010, T011 can run in parallel (different files)
- T014, T015 can run in parallel
- T017, T018 can run in parallel

**Phase 3 (US1)**:
- T020, T021, T022 can run in parallel (different classifiers)

**Phase 4 (US2)**:
- T029 can start while T030, T031 wait

**Phase 6 (US4)**:
- T045 (Generic Actor) can run parallel to T047-T050 (Planner decomposition)

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all data model tasks together:
Task: "Implement IntentResult and Action types in backend/aime/intent/models.py"
Task: "Implement CAPABILITY_AGENT_MAP in backend/aime/intent/models.py"
Task: "Implement SubtaskSpec dataclass in backend/aime/models.py"
Task: "Implement ProgressItem and TaskStatus in backend/aime/models.py"
Task: "Implement ProgressList in backend/aime/models.py"
Task: "Implement Actor dataclass in backend/aime/models.py"

# After models complete, launch agent capability tasks:
Task: "Add capabilities to research agent in backend/agents/research.py"
Task: "Add capabilities to sql agent in backend/agents/sql.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T019)
3. Complete Phase 3: User Story 1 (T020-T028)
4. **STOP and VALIDATE**: Test simple queries like "你好", "1+1=?"
5. Deploy/demo if ready - basic AIME working

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test direct_reply → MVP!
3. Add User Story 2 → Test [ROUTE_TO: xxx] → Explicit routing
4. Add User Story 3 → Test "搜索AI新闻" → Intelligent routing
5. Add User Story 4 → Test complex tasks → Task decomposition
6. Add User Story 5 → Verify frontend progress display
7. Add User Story 6 → Test failure recovery
8. Polish → Full integration

### Critical Path

```
Setup → Foundational → US1 → US2 → US3 → US4 → US5 → US6 → Polish
         (blocking)    (MVP)
```

---

## Summary

| Phase | Tasks | Parallel Opportunities |
|-------|-------|------------------------|
| Setup | 5 | 4 parallel |
| Foundational | 14 | 10 parallel |
| US1 (P1) | 9 | 3 parallel |
| US2 (P1) | 9 | 1 parallel |
| US3 (P1) | 7 | 1 parallel |
| US4 (P1) | 12 | 1 parallel |
| US5 (P2) | 5 | 0 parallel |
| US6 (P3) | 5 | 0 parallel |
| Polish | 12 | 0 parallel |
| **Total** | **78** | **20 parallel** |

### Independent Test Criteria

| Story | Test Criteria |
|-------|--------------|
| US1 | 发送"你好" → 直接回复，无 task_spawned 事件 |
| US2 | 发送 `[ROUTE_TO: research] test` → task_spawned 到 research |
| US3 | 发送"搜索AI新闻" → 自动路由到 research agent |
| US4 | 发送复杂任务 → todos_updated 显示多个子任务 |
| US5 | 任务执行中 → 前端实时更新状态 |
| US6 | 模拟失败 → 重试最多3次后返回错误 |

### Suggested MVP Scope

**Phase 1 + Phase 2 + Phase 3 (User Story 1)** = 28 tasks

This delivers:
- AIME module structure
- IntentAnalyzer with Rule + Keyword classifiers
- AIMEPlanner with direct_reply handling
- Supervisor rewritten to use AIME
- Simple queries work without task spawning
