# Tasks: 对话历史与用户管理

**Input**: Design documents from `/specs/002-conversation-user-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml

**Tests**: 手动测试（未请求自动化测试）

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and database setup

- [x] T001 Add new dependencies to pyproject.toml: asyncpg, passlib[bcrypt], python-jose[cryptography], alembic, langgraph-checkpoint-postgres
- [x] T002 [P] Create Alembic configuration file in backend/alembic.ini
- [x] T003 [P] Create Alembic env.py in backend/migrations/env.py with async PostgreSQL support
- [x] T004 [P] Create Alembic script template in backend/migrations/script.py.mako
- [x] T005 Create PostgreSQL connection pool module in backend/db.py with asyncpg

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create initial Alembic migration for users table in backend/migrations/versions/001_create_users_table.py
- [x] T007 Create Alembic migration for conversations table in backend/migrations/versions/002_create_conversations_table.py
- [x] T008 [P] Create User Pydantic models in backend/auth/models.py (UserCreate, UserInfo, LoginRequest, LoginResponse)
- [x] T009 [P] Create Conversation Pydantic models in backend/conversations/models.py (ConversationCreate, ConversationSummary, Conversation)
- [x] T010 [P] Create security module in backend/auth/security.py (password hashing with bcrypt, JWT encode/decode)
- [x] T011 Create auth database operations in backend/auth/database.py (get_user_by_username, get_user_by_id, create_user, update_user_status, delete_user, list_users, count_active_admins)
- [x] T012 Create conversations database operations in backend/conversations/database.py (create_conversation, get_conversation, list_user_conversations, update_conversation_title, delete_conversation)
- [x] T013 Create authentication dependencies in backend/auth/dependencies.py (get_current_user, require_admin)
- [x] T014 Create __init__.py files for new modules: backend/auth/__init__.py, backend/conversations/__init__.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 用户登录 (Priority: P1) 🎯 MVP

**Goal**: 用户可以通过用户名和密码登录系统，未登录用户无法访问任何功能

**Independent Test**: 使用正确/错误凭据登录，验证成功登录后跳转主界面，失败时显示错误提示

### Implementation for User Story 1

- [x] T015 [US1] Create auth router in backend/auth/router.py with POST /api/auth/login and GET /api/auth/me endpoints
- [x] T016 [US1] Register auth router in backend/main.py
- [x] T017 [P] [US1] Create auth API client in frontend/src/api/auth.ts (login, getCurrentUser functions)
- [x] T018 [P] [US1] Create AuthContext and useAuth hook in frontend/src/hooks/useAuth.ts (login state, user info, isAuthenticated)
- [x] T019 [US1] Create LoginPage component in frontend/src/components/Auth/LoginPage.tsx with form, error handling, loading state
- [x] T020 [US1] Update frontend/src/App.tsx to show LoginPage when not authenticated, redirect on successful login
- [x] T021 [US1] Add authentication check to existing /api/chat endpoint in backend/main.py (require login)

**Checkpoint**: User Story 1 complete - users can login and access the app

---

## Phase 4: User Story 2 - 左树右表布局与导航 (Priority: P1)

**Goal**: 登录后看到左树右表布局，左侧导航栏可收缩/展开

**Independent Test**: 登录后查看布局、点击收缩按钮、点击各导航项

### Implementation for User Story 2

- [x] T022 [P] [US2] Create SidebarHeader component in frontend/src/components/Layout/SidebarHeader.tsx (logo, collapse button)
- [x] T023 [P] [US2] Create Sidebar component in frontend/src/components/Layout/Sidebar.tsx (navigation items, collapsible state)
- [x] T024 [US2] Create MainLayout component in frontend/src/components/Layout/MainLayout.tsx (sidebar + main content area)
- [x] T025 [US2] Update frontend/src/App.tsx to use MainLayout after login, integrate existing ChatContainer as main content
- [x] T026 [US2] Add sidebar collapse/expand animation and localStorage persistence in Sidebar component
- [x] T027 [US2] Add "新建对话" button in Sidebar that creates new conversation

**Checkpoint**: User Story 2 complete - layout with collapsible sidebar works

---

## Phase 5: User Story 3 - 对话历史管理 (Priority: P1)

**Goal**: 用户可以在左侧看到对话列表，点击打开历史对话，可以删除对话

**Independent Test**: 创建对话、在列表中查看、点击打开、删除对话

### Implementation for User Story 3

- [x] T028 [US3] Create conversations router in backend/conversations/router.py with GET /api/conversations, POST /api/conversations, GET/PATCH/DELETE /api/conversations/{id}
- [x] T029 [US3] Register conversations router in backend/main.py
- [x] T030 [P] [US3] Create conversations API client in frontend/src/api/conversations.ts (list, create, get, update, delete)
- [x] T031 [P] [US3] Create useConversations hook in frontend/src/hooks/useConversations.ts (conversation list state, CRUD operations)
- [x] T032 [US3] Create ConversationItem component in frontend/src/components/Conversations/ConversationItem.tsx (title, time, delete button)
- [x] T033 [US3] Create ConversationList component in frontend/src/components/Conversations/ConversationList.tsx (list display, empty state guidance)
- [x] T034 [US3] Integrate ConversationList into Sidebar component
- [x] T035 [US3] Update ChatContainer to load conversation by ID when selected from list
- [x] T036 [US3] Modify /api/chat to create/update conversation record on first message
- [x] T037 [US3] Add delete confirmation dialog in ConversationItem

**Checkpoint**: User Story 3 complete - conversation history management works

---

## Phase 6: User Story 4 - 管理员用户管理 (Priority: P2)

**Goal**: 管理员可以查看用户列表、创建新用户、禁用/启用用户、删除用户

**Independent Test**: 管理员登录、进入用户管理、执行CRUD操作

### Implementation for User Story 4

- [x] T038 [US4] Create users router in backend/auth/router.py (or separate file) with GET /api/users, POST /api/users, DELETE /api/users/{id}, PATCH /api/users/{id}/status
- [x] T039 [US4] Add business rules validation: cannot delete self, cannot delete last admin, cannot disable last admin
- [x] T040 [P] [US4] Create users API client in frontend/src/api/users.ts (list, create, delete, updateStatus)
- [x] T041 [P] [US4] Create UserForm component in frontend/src/components/Admin/UserForm.tsx (username, password, role inputs)
- [x] T042 [US4] Create UserManagement component in frontend/src/components/Admin/UserManagement.tsx (user table, actions)
- [x] T043 [US4] Add "系统管理" navigation item in Sidebar (admin only)
- [x] T044 [US4] Update MainLayout to show UserManagement when admin clicks "系统管理"

**Checkpoint**: User Story 4 complete - admin can manage users

---

## Phase 7: User Story 5 - 普通用户权限限制 (Priority: P2)

**Goal**: 普通用户看不到系统管理入口，无法访问管理功能

**Independent Test**: 普通用户登录，验证看不到管理入口，直接访问管理API被拒绝

### Implementation for User Story 5

- [x] T045 [US5] Update Sidebar to conditionally show "系统管理" only for admin users
- [x] T046 [US5] Add 403 error handling in frontend for unauthorized API calls
- [x] T047 [US5] Verify require_admin dependency is applied to all user management endpoints in backend

**Checkpoint**: User Story 5 complete - permission separation works

---

## Phase 8: User Story 6 - 用户退出登录 (Priority: P2)

**Goal**: 用户可以退出登录，退出后返回登录页面

**Independent Test**: 点击退出按钮，验证会话结束并返回登录页

### Implementation for User Story 6

- [x] T048 [US6] Add POST /api/auth/logout endpoint in backend/auth/router.py (clear cookie)
- [x] T049 [US6] Add logout function to frontend/src/api/auth.ts
- [x] T050 [US6] Add logout method to useAuth hook
- [x] T051 [US6] Create user info and logout button section in Sidebar (登录管理区域)
- [x] T052 [US6] Update App.tsx to redirect to LoginPage on logout

**Checkpoint**: User Story 6 complete - logout works

---

## Phase 9: User Story 7 - 对话自动命名 (Priority: P3)

**Goal**: 系统根据第一条消息自动生成对话标题，用户可以手动修改

**Independent Test**: 开始对话后查看列表中的标题，双击编辑标题

### Implementation for User Story 7

- [x] T053 [US7] Update conversation creation logic in backend to auto-generate title from first message (first 50 chars)
- [x] T054 [US7] Add title edit mode to ConversationItem component (double-click to edit)
- [x] T055 [US7] Add PATCH /api/conversations/{id} call when title is edited
- [x] T056 [US7] Add title truncation with tooltip for long titles in ConversationItem

**Checkpoint**: User Story 7 complete - auto-naming and editing work

---

## Phase 10: User Story 8 - 数据迁移与持久化 (Priority: P3)

**Goal**: 将 SQLite 数据迁移到 PostgreSQL，确保数据持久化

**Independent Test**: 创建数据、重启服务、验证数据完整性

### Implementation for User Story 8

- [x] T057 [US8] Create migration script in scripts/migrate_sqlite_to_pg.py (migrate threads.db checkpoints and writes tables)
- [x] T058 [US8] Update backend/main.py to use PostgreSQLSaver from langgraph-checkpoint-postgres instead of AsyncSqliteSaver
- [x] T059 [US8] Add default admin creation logic on first startup in backend/main.py (check if users table is empty, create admin from env vars)
- [x] T060 [US8] Update backend lifespan to run Alembic migrations on startup (optional, or require manual migration)
- [x] T061 [US8] Test data persistence: create conversation, restart server, verify data intact

**Checkpoint**: User Story 8 complete - PostgreSQL migration and persistence work

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T062 [P] Add loading states to all API calls in frontend components
- [x] T063 [P] Add error boundary and error messages for API failures
- [x] T064 [P] Ensure consistent styling across all new components (match existing design system)
- [x] T065 Add session timeout handling: auto-redirect to login when 401 received
- [x] T066 [P] Add environment variable documentation to .env.example for DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET_KEY
- [x] T067 Update quickstart.md with final setup instructions
- [ ] T068 Manual end-to-end testing following all acceptance scenarios from spec.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - Core login functionality
- **US2 (Phase 4)**: Depends on US1 - Layout requires auth context
- **US3 (Phase 5)**: Depends on US2 - Conversation list goes in sidebar
- **US4 (Phase 6)**: Depends on US2 - Admin page uses layout
- **US5 (Phase 7)**: Depends on US4 - Permission checks require admin features
- **US6 (Phase 8)**: Depends on US2 - Logout goes in sidebar
- **US7 (Phase 9)**: Depends on US3 - Title editing for conversations
- **US8 (Phase 10)**: Can start after Foundational - Database migration is independent
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ──────────────────────────────┐
    ↓                                                 │
Phase 3 (US1: Login) ←─────────────────── Phase 10 (US8: Migration)
    ↓
Phase 4 (US2: Layout)
    ↓
┌───┴───┬───────────┐
↓       ↓           ↓
US3     US4         US6
(History) (Admin)   (Logout)
↓         ↓
US7       US5
(Naming)  (Permissions)
    ↓
Phase 11 (Polish)
```

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T008, T009, T010 can run in parallel (different files)

**Phase 3 (US1)**:
- T017, T018 can run in parallel (frontend files)

**Phase 4 (US2)**:
- T022, T023 can run in parallel (different components)

**Phase 5 (US3)**:
- T030, T031 can run in parallel (API client and hook)

**Phase 6 (US4)**:
- T040, T041 can run in parallel (API client and form)

**Cross-Phase**:
- US8 (Migration) can run in parallel with US1-US7 after Foundational is complete

---

## Parallel Example: Phase 2 (Foundational)

```bash
# These can run in parallel (different files):
- T008 [P] Create User Pydantic models in backend/auth/models.py
- T009 [P] Create Conversation Pydantic models in backend/conversations/models.py
- T010 [P] Create security module in backend/auth/security.py

# Then sequentially:
- T011 Create auth database operations (depends on T008)
- T012 Create conversations database operations (depends on T009)
- T013 Create authentication dependencies (depends on T010, T011)
```

---

## Implementation Strategy

### MVP First (User Stories 1-3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Login)
4. Complete Phase 4: User Story 2 (Layout)
5. Complete Phase 5: User Story 3 (Conversation History)
6. **STOP and VALIDATE**: Test core functionality
7. Deploy/demo if ready - users can login, see layout, manage conversations

### Incremental Delivery

1. MVP (US1-3) → Basic usable application
2. Add US4-6 → Admin features and logout
3. Add US7-8 → Polish features and migration
4. Final phase → Production ready

### Suggested Execution Order for Single Developer

1. T001-T014 (Setup + Foundational)
2. T015-T021 (US1: Login)
3. T022-T027 (US2: Layout)
4. T028-T037 (US3: Conversations)
5. T057-T061 (US8: Migration - can be done earlier if PostgreSQL ready)
6. T038-T044 (US4: Admin)
7. T045-T047 (US5: Permissions)
8. T048-T052 (US6: Logout)
9. T053-T056 (US7: Naming)
10. T062-T068 (Polish)

---

## Notes

- All [P] tasks = different files, no dependencies within same phase
- [US#] label maps task to specific user story for traceability
- Commit after each task or logical group
- Verify each user story works independently before moving to next
- PostgreSQL must be running before starting Phase 2
- Run `uv run alembic upgrade head` after creating migrations
