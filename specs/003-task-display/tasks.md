# Tasks: Task Display Mode Redesign

**Input**: Design documents from `/specs/003-task-display/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/` (Python 3.11+, FastAPI)
- **Frontend**: `frontend/src/` (TypeScript, React 19)

---

## Phase 1: Setup

**Purpose**: Project structure preparation and type definitions

- [X] T001 Copy SSE event contracts from specs/003-task-display/contracts/sse-events.ts to frontend/src/types/sse-events.ts
- [X] T002 [P] Extend frontend/src/types/index.ts with Todo, SpawnedTask, ThinkingStep interfaces from data-model.md
- [X] T003 [P] Extend SSEEvent union type in frontend/src/types/index.ts to include new events

---

## Phase 2: Foundational (Backend SSE Infrastructure)

**Purpose**: Backend SSE event emission - MUST complete before frontend user stories

**⚠️ CRITICAL**: Frontend display features depend on these backend events

- [X] T004 Add TaskTracker and EventCounter dataclasses to backend/stream_handler.py per data-model.md
- [X] T005 Extend stream_handler.py to process `updates` stream mode and detect `todos` state changes
- [X] T006 Add `todos_updated` event emission when todos state changes in backend/stream_handler.py
- [X] T007 Detect `task` tool calls and emit `task_spawned` event in backend/stream_handler.py
- [X] T008 Track task completion and emit `task_completed` event with duration_ms in backend/stream_handler.py
- [X] T009 Enhance `thinking` event emission to include `type` field in backend/stream_handler.py
- [X] T010 Add `task_id` field to `tool_call_start` and `tool_call_result` events in backend/stream_handler.py
- [X] T011 Add event ID to all SSE events for reconnection support in backend/stream_handler.py

**Checkpoint**: Backend now emits all new SSE events - frontend development can begin ✅

---

## Phase 3: User Story 1 - Quick Answer Display (Priority: P1) 🎯 MVP

**Goal**: Simple questions display only result area, no thinking bubble or task tree

**Independent Test**: Send "你好" message, verify only result area is visible, no extra UI elements

### Implementation for User Story 1

- [X] T012 [P] [US1] Extend useChat hook to detect scenario type (quick/agent/planning) based on events in frontend/src/hooks/useChat.ts
- [X] T013 [P] [US1] Add scenario state to Message type and compute from incoming events in frontend/src/hooks/useChat.ts
- [X] T014 [US1] Modify MessageBubble to conditionally render layers based on scenario in frontend/src/components/MessageBubble.tsx
- [X] T015 [US1] Implement result-only layout for quick answer scenario in frontend/src/components/MessageBubble.tsx

**Checkpoint**: Quick answer scenario displays cleanly without extra UI - MVP functional ✅

---

## Phase 4: User Story 2 - Specialized Agent Execution Display (Priority: P1)

**Goal**: Single agent tasks show task tree with one node (e.g., SQL Agent), expandable to see tool calls

**Independent Test**: Send "/sql 列出所有表", verify single task node appears with tool calls inside when expanded

### Implementation for User Story 2

- [X] T016 [P] [US2] Handle `task_spawned` event in useChat hook, create SpawnedTask entry in frontend/src/hooks/useChat.ts
- [X] T017 [P] [US2] Handle `task_completed` event in useChat hook, update SpawnedTask status in frontend/src/hooks/useChat.ts
- [X] T018 [P] [US2] Associate tool_call_start/result with parent task via task_id in frontend/src/hooks/useChat.ts
- [X] T019 [P] [US2] Create TaskNode component showing task name, status, expand/collapse in frontend/src/components/TaskList.tsx (combined)
- [X] T020 [P] [US2] Create ToolCallList component displaying tool calls within a task in frontend/src/components/TaskList.tsx (using ToolCallCard)
- [X] T021 [US2] Create TaskTree container component rendering SpawnedTask list in frontend/src/components/TaskList.tsx
- [X] T022 [US2] Integrate TaskTree into MessageBubble for agent scenario in frontend/src/components/MessageBubble.tsx
- [X] T023 [US2] Add status indicators (running animation, success checkmark, error icon) to TaskNode in frontend/src/components/TaskList.tsx

**Checkpoint**: Agent tasks show single expandable task node with tool calls - US2 functional ✅

---

## Phase 5: User Story 3 - Autonomous Planning Mode Display (Priority: P1)

**Goal**: Complex tasks show thinking bubble (planning), task tree (multiple nodes), and result area

**Independent Test**: Send complex task like "比较三家公司的市场策略", verify thinking bubble shows planning, multiple task nodes appear

### Implementation for User Story 3

- [X] T024 [P] [US3] Handle `todos_updated` event in useChat hook, store Todo list in Message in frontend/src/hooks/useChat.ts
- [X] T025 [P] [US3] Handle `thinking` event with type field, categorize as planning/replanning/routing in frontend/src/hooks/useChat.ts
- [X] T026 [P] [US3] Create ThinkingBubble component showing planning steps with icons in frontend/src/components/ThinkingBubble.tsx (existing)
- [ ] T027 [US3] Add replanning step display with distinct styling in ThinkingBubble in frontend/src/components/ThinkingBubble.tsx
- [X] T028 [US3] Extend TaskTree to render Todo list as task nodes (alternative to SpawnedTasks) in frontend/src/components/TaskList.tsx
- [X] T029 [US3] Map Todo status to visual states (pending=gray, in_progress=blue+animation, completed=green) in frontend/src/components/TaskList.tsx
- [X] T030 [US3] Integrate ThinkingBubble into MessageBubble for planning scenario in frontend/src/components/MessageBubble.tsx
- [X] T031 [US3] Add dynamic task node insertion when todos_updated adds new tasks in frontend/src/components/TaskList.tsx

**Checkpoint**: Planning mode shows full three-layer structure - US3 functional ✅

---

## Phase 6: User Story 4 - Task Node Expansion (Priority: P2)

**Goal**: Users can expand/collapse task nodes to see tool calling details

**Independent Test**: Click on any task node, verify it expands to show tool calls; click again to collapse

### Implementation for User Story 4

- [X] T032 [P] [US4] Add expand/collapse state management to TaskNode using useState in frontend/src/components/TaskList.tsx
- [X] T033 [P] [US4] Implement expand/collapse animation with CSS transitions in frontend/src/App.css
- [X] T034 [US4] Add tool call detail view showing args and output when expanded in frontend/src/components/TaskList.tsx (using ToolCallCard)
- [ ] T035 [US4] Implement output truncation (>100 chars) with "展开全部" button in frontend/src/components/ToolCallList.tsx
- [ ] T036 [US4] Add copy-to-clipboard functionality for tool args and output in frontend/src/components/ToolCallList.tsx

**Checkpoint**: Task nodes fully expandable/collapsible with detail views - US4 functional ✅

---

## Phase 7: User Story 5 - Thinking Bubble Display (Priority: P2)

**Goal**: Thinking bubble clearly shows planning phases with visual distinction

**Independent Test**: Trigger planning task, verify thinking bubble shows "正在分析任务..." with animation, then planning results

### Implementation for User Story 5

- [X] T037 [P] [US5] Add thinking animation indicator (spinner/pulse) to ThinkingBubble in frontend/src/components/ThinkingBubble.tsx (existing)
- [ ] T038 [P] [US5] Style planning vs replanning steps differently (icons, colors) in frontend/src/components/ThinkingBubble.tsx
- [ ] T039 [US5] Add timestamp display for each thinking step in frontend/src/components/ThinkingBubble.tsx
- [ ] T040 [US5] Implement auto-scroll to latest thinking step in frontend/src/components/ThinkingBubble.tsx

**Checkpoint**: Thinking bubble provides clear visual feedback during planning - US5 functional (basic)

---

## Phase 8: Edge Cases & Polish

**Purpose**: Handle edge cases and cross-cutting concerns

- [ ] T041 [P] Add SSE reconnection with Last-Event-ID support in frontend/src/api/client.ts
- [ ] T042 [P] Handle network interruption gracefully, show reconnecting state in frontend/src/hooks/useChat.ts
- [X] T043 [P] Add error state styling to TaskNode (red border, error icon) in frontend/src/components/TaskList.tsx
- [ ] T044 [P] Handle task cancellation, mark nodes as "已取消" in frontend/src/components/TaskNode.tsx
- [ ] T045 [P] Add output truncation for >2000 char tool outputs with expand button in frontend/src/components/ToolCallList.tsx
- [X] T046 Handle empty planning (no todos) by degrading to quick answer mode in frontend/src/hooks/useChat.ts
- [X] T047 Add React.memo to TaskList for performance optimization in frontend/src/components/TaskList.tsx
- [ ] T048 Run quickstart.md test scenarios to validate all three display modes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all frontend user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (Quick Answer): No dependencies on other stories
  - US2 (Agent Display): No dependencies on other stories, can parallel with US1
  - US3 (Planning Mode): No dependencies on other stories, can parallel with US1/US2
  - US4 (Expansion): Can parallel but benefits from US2/US3 components
  - US5 (Thinking Bubble): Can parallel but benefits from US3 ThinkingBubble base
- **Polish (Phase 8)**: Can start after any user story, full validation after all complete

### User Story Dependencies

```
Phase 1 (Setup)
     ↓
Phase 2 (Foundational - Backend SSE)
     ↓
     ├── Phase 3 (US1: Quick Answer) ──────────┐
     ├── Phase 4 (US2: Agent Display) ─────────┤
     ├── Phase 5 (US3: Planning Mode) ─────────┤──→ Phase 8 (Polish)
     ├── Phase 6 (US4: Expansion) ─────────────┤
     └── Phase 7 (US5: Thinking Bubble) ───────┘
```

### Within Each User Story

- Types/hooks before components
- Base components before integration
- Core functionality before polish

### Parallel Opportunities

**Phase 1 (Setup)**:
- T002 and T003 can run in parallel

**Phase 2 (Foundational)**:
- Sequential within phase (each builds on previous)

**Phase 3-7 (User Stories)**:
- All user stories can run in parallel after Phase 2
- Within each story, tasks marked [P] can run in parallel

---

## Parallel Example: User Story 2

```bash
# Launch all [P] tasks for US2 together:
Task: "T016 Handle task_spawned event..."
Task: "T017 Handle task_completed event..."
Task: "T018 Associate tool_call_start/result with parent task..."
Task: "T019 Create TaskNode component..."
Task: "T020 Create ToolCallList component..."

# Then sequential tasks:
Task: "T021 Create TaskTree container..."
Task: "T022 Integrate TaskTree into MessageBubble..."
Task: "T023 Add status indicators..."
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (types)
2. Complete Phase 2: Foundational (backend SSE)
3. Complete Phase 3: User Story 1 (quick answer)
4. **STOP and VALIDATE**: Test quick answer scenario
5. Deploy/demo if ready - users see improved simple responses

### Incremental Delivery

1. Setup + Foundational → Backend ready
2. Add US1 → Quick answers work → Demo
3. Add US2 → Agent tasks show single node → Demo
4. Add US3 → Planning mode works → Demo
5. Add US4/US5 → Full interactivity → Final release

### Parallel Team Strategy

With 2 developers after Phase 2:
- **Developer A**: US1 → US3 → US5 (display logic)
- **Developer B**: US2 → US4 → Polish (interaction logic)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable via quickstart.md scenarios
- Backend Phase 2 is blocking - no frontend work until SSE events emit correctly
- All new SSE fields are optional for backward compatibility
- Commit after each task or logical group
