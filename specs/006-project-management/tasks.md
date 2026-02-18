# Tasks: Project Management

**Input**: Design documents from `/specs/006-project-management/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are NOT explicitly requested in the feature specification - test tasks are excluded.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and project structure initialization

- [X] T001 Create database migration for projects tables in `infra/migrations/versions/004_create_projects_table.py`
- [X] T002 Run database migration to create projects, project_files tables and modify conversations table

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend models and database operations that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Create Pydantic models for projects in `backend/projects/models.py`
- [X] T004 [P] Create project database operations in `backend/projects/database.py`
- [X] T005 Create projects router with basic CRUD endpoints in `backend/projects/router.py`
- [X] T006 Register projects router in `backend/main.py`
- [X] T007 [P] Add project_id field to conversation models in `backend/conversations/models.py`
- [X] T008 Extend conversation database operations to support project filtering in `backend/conversations/database.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 项目基础管理 (Priority: P1) 🎯 MVP

**Goal**: Users can create, edit, and delete projects with unique names per user

**Independent Test**: Create a new project, rename it, then delete it - verify all operations work correctly

### Implementation for User Story 1

- [X] T009 [US1] Implement POST /api/projects endpoint (create project with unique name validation) in `backend/projects/router.py`
- [X] T010 [US1] Implement GET /api/projects endpoint (list user's projects) in `backend/projects/router.py`
- [X] T011 [US1] Implement GET /api/projects/{id} endpoint (get project detail) in `backend/projects/router.py`
- [X] T012 [US1] Implement PATCH /api/projects/{id} endpoint (rename project) in `backend/projects/router.py`
- [X] T013 [US1] Implement DELETE /api/projects/{id} endpoint (soft delete with cascade) in `backend/projects/router.py`
- [X] T014 [P] [US1] Create Projects API client in `frontend/src/api/projects.ts`
- [X] T015 [P] [US1] Create useProjects hook in `frontend/src/hooks/useProjects.ts`
- [X] T016 [P] [US1] Add Project TypeScript types in `frontend/src/types/index.ts`
- [X] T017 [US1] Create NewProjectModal component in `frontend/src/components/Projects/NewProjectModal.tsx`

**Checkpoint**: Users can create, rename, and delete projects via API and basic frontend support

---

## Phase 4: User Story 2 - 项目工作区界面 (Priority: P1)

**Goal**: Users can access a two-column workspace (Sources panel + Chat panel) when clicking a project

**Independent Test**: Click a project and verify the workspace displays with collapsible Sources panel and functional Chat panel

### Implementation for User Story 2

- [X] T018 [P] [US2] Create SourcesPanel component (file list with checkboxes) in `frontend/src/components/Projects/SourcesPanel.tsx`
- [X] T019 [P] [US2] Create ProjectWorkspace component (two-column layout) in `frontend/src/components/Projects/ProjectWorkspace.tsx`
- [X] T020 [US2] Integrate selected files state with useChat hook in `frontend/src/hooks/useChat.ts`
- [X] T021 [US2] Add project workspace route and navigation in `frontend/src/App.tsx`
- [X] T022 [US2] Add collapse/expand functionality to SourcesPanel with smooth animation in `frontend/src/components/Projects/SourcesPanel.tsx`
- [X] T023 [US2] Display selected file count in Chat input bar in `frontend/src/components/InputBar.tsx`

**Checkpoint**: Project workspace displays correctly with collapsible Sources panel and Chat integration

---

## Phase 5: User Story 3 - 项目导航集成 (Priority: P1)

**Goal**: Projects and History display side-by-side in sidebar; conversations can be added/removed from projects

**Independent Test**: Verify sidebar shows Projects and History sections; right-click conversation to add/remove from project

### Implementation for User Story 3

- [X] T024 [US3] Add project-conversation association endpoint POST /api/conversations/{id}/project in `backend/conversations/router.py`
- [X] T025 [US3] Add remove from project endpoint DELETE /api/conversations/{id}/project in `backend/conversations/router.py`
- [X] T026 [US3] Add GET /api/projects/{id}/conversations endpoint to list project conversations in `backend/projects/router.py`
- [X] T027 [P] [US3] Create ProjectList component with expandable tree in `frontend/src/components/Projects/ProjectList.tsx`
- [X] T028 [P] [US3] Create ProjectItem component (expandable with conversations) in `frontend/src/components/Projects/ProjectItem.tsx`
- [X] T029 [US3] Modify Sidebar to include Projects section alongside History in `frontend/src/components/Layout/Sidebar.tsx`
- [ ] T030 [US3] Add right-click context menu to ConversationItem for project operations in `frontend/src/components/Conversations/ConversationItem.tsx`
- [X] T031 [US3] Create project selection dropdown/modal for "Add to Project" action in `frontend/src/components/Projects/ProjectSelectMenu.tsx`
- [X] T032 [US3] Filter History list to exclude project-assigned conversations in `frontend/src/hooks/useConversations.ts`

**Checkpoint**: Navigation shows Projects and History; conversations can be managed between them

---

## Phase 6: User Story 4 - 文件源管理 (Priority: P2)

**Goal**: Users can upload, view, select, and delete files in project Sources panel with permanent storage

**Independent Test**: Upload a file, verify it appears in Sources, select it, then delete it; refresh to confirm persistence

### Implementation for User Story 4

- [X] T033 [US4] Create file storage utilities for permanent project file storage in `backend/projects/file_storage.py` (implemented inline in router.py)
- [X] T034 [US4] Implement POST /api/projects/{id}/files endpoint (upload with validation) in `backend/projects/router.py`
- [X] T035 [US4] Implement GET /api/projects/{id}/files endpoint (list project files) in `backend/projects/router.py`
- [X] T036 [US4] Implement DELETE /api/projects/{id}/files/{file_id} endpoint in `backend/projects/router.py`
- [X] T037 [US4] Add file type validation (PDF, DOCX, TXT, MD, CSV, JSON, code files) in `backend/projects/file_storage.py` (implemented inline in router.py)
- [X] T038 [US4] Add file count limit validation (max 50 per project) in `backend/projects/database.py`
- [X] T039 [P] [US4] Add project files API methods in `frontend/src/api/projects.ts`
- [X] T040 [US4] Implement file upload UI in SourcesPanel with progress indicator in `frontend/src/components/Projects/SourcesPanel.tsx`
- [X] T041 [US4] Add file deletion UI in SourcesPanel with confirmation in `frontend/src/components/Projects/SourcesPanel.tsx`
- [X] T042 [US4] Add "Select all sources" checkbox functionality in `frontend/src/components/Projects/SourcesPanel.tsx`
- [X] T043 [US4] Pass selected file_ids to chat API when sending messages in `frontend/src/hooks/useChat.ts`
- [X] T044 [US4] Implement project deletion cascade (delete stored files) in `backend/projects/database.py`

**Checkpoint**: Files can be uploaded, selected as context, and deleted; file persistence works across sessions

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, edge cases, and improvements

- [X] T045 [P] Add empty state UI for Projects section (no projects yet) in `frontend/src/components/Projects/ProjectList.tsx`
- [X] T046 [P] Add empty state UI for project conversations (no conversations in project) in `frontend/src/components/Projects/ProjectItem.tsx`
- [X] T047 [P] Add loading states for project operations in `frontend/src/hooks/useProjects.ts`
- [ ] T048 Add error handling and toast notifications for project operations in `frontend/src/components/Projects/`
- [X] T049 Add file name truncation with tooltip for long filenames in `frontend/src/components/Projects/SourcesPanel.tsx`
- [X] T050 Validate all API endpoints return proper error codes per contracts in `backend/projects/router.py`
- [ ] T051 Run quickstart.md scenarios for end-to-end validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (Phase 3): Can start after Foundational
  - US2 (Phase 4): Can start after Foundational (frontend components)
  - US3 (Phase 5): Backend depends on US1 API; frontend can start after Foundational
  - US4 (Phase 6): Backend depends on US1 API; frontend depends on US2 (SourcesPanel)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundation only - MVP starting point
- **User Story 2 (P1)**: Foundation only - parallel with US1 for frontend
- **User Story 3 (P1)**: Needs US1 APIs for project operations; frontend can start early
- **User Story 4 (P2)**: Needs US1 (project context) and US2 (SourcesPanel component)

### Within Each User Story

- Backend API endpoints before frontend API clients
- API clients before React hooks
- Hooks before components
- Core functionality before polish

### Parallel Opportunities

- T003, T004, T007 can run in parallel (different files, no dependencies)
- T014, T015, T16 can run in parallel (frontend setup)
- T018, T019 can run in parallel (independent components)
- T027, T028 can run in parallel (independent components)
- T045, T046, T047 can run in parallel (polish tasks)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all parallel foundational tasks together:
Task: "Create Pydantic models for projects in backend/projects/models.py"
Task: "Create project database operations in backend/projects/database.py"
Task: "Add project_id field to conversation models in backend/conversations/models.py"

# Then sequential tasks:
Task: "Create projects router in backend/projects/router.py"
Task: "Register projects router in backend/main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (database migration)
2. Complete Phase 2: Foundational (models, database ops)
3. Complete Phase 3: User Story 1 (project CRUD)
4. **STOP and VALIDATE**: Test project creation/edit/delete via API
5. Basic project management working - can demo

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test CRUD operations → Demo (MVP!)
3. Add User Story 2 → Test workspace layout → Demo
4. Add User Story 3 → Test navigation integration → Demo
5. Add User Story 4 → Test file management → Full feature complete

### Suggested Order for Single Developer

1. T001-T002 (Setup)
2. T003-T008 (Foundational)
3. T009-T017 (US1 - Backend then Frontend)
4. T018-T023 (US2 - Workspace)
5. T024-T032 (US3 - Navigation)
6. T033-T044 (US4 - Files)
7. T045-T051 (Polish)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total: 51 tasks across 7 phases
