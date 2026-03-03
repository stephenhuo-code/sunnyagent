# Tasks: 插件管理系统 (Plugin Management)

**Input**: Design documents from `/specs/012-plugin-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/plugins-api.yaml

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US8)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/` (Python 3.11+, FastAPI)
- **Frontend**: `frontend/src/` (TypeScript, React 19)
- **Migrations**: `infra/migrations/versions/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create `backend/plugins/` module directory with `__init__.py`
- [x] T002 [P] Create Pydantic models in `backend/plugins/models.py` (PluginInfo, PluginSource, PluginType, etc.)
- [x] T003 [P] Create TypeScript types in `frontend/src/types/plugins.ts`
- [x] T004 [P] Create API client in `frontend/src/api/plugins.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create Alembic migration for 3 new tables in `infra/migrations/versions/006_create_plugin_tables.py`
- [x] T006 Apply migration and verify tables created: `cd infra && uv run alembic upgrade head`
- [x] T007 [P] Implement database CRUD in `backend/plugins/database.py` (user_plugin_states, uploaded_plugins, plugin_ratings)
- [x] T008 [P] Extend `backend/skills/registry.py` with `source` field in SkillEntry dataclass
- [x] T009 [P] Extend `backend/skills/loader.py` to accept `source` parameter in `load_skills_from_directory()`
- [x] T010 Modify `backend/agents/loader.py` to register Package skills to SKILL_REGISTRY with `source=package:{agent_name}`, pass `skills=None` to `create_deep_agent()`
- [x] T011 Create unified plugin loader in `backend/plugins/loader.py` with `load_agent_from_directory()` function
- [x] T012 Create plugin service in `backend/plugins/service.py` (get_all_plugins, get_plugin, merge preset/package/uploaded/shared sources)
- [x] T013 Register plugins router in `backend/main.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 浏览已安装插件 (Priority: P1) 🎯 MVP

**Goal**: 用户可以查看系统中所有可用的插件列表、状态和详细信息

**Independent Test**: 用户登录后进入插件管理页面，看到所有插件的列表、状态和描述信息

### Implementation for User Story 1

- [x] T014 [US1] Implement `GET /api/plugins` endpoint in `backend/core/plugins.py` (listPlugins)
- [x] T015 [US1] Implement `GET /api/plugins/{plugin_name}` endpoint in `backend/core/plugins.py` (getPlugin)
- [x] T016 [P] [US1] Create `frontend/src/components/Plugins/PluginSidebar.tsx` (插件列表组件)
- [x] T017 [P] [US1] Create `frontend/src/components/Plugins/PluginDetail.tsx` (插件详情面板)
- [x] T018 [US1] Create `frontend/src/pages/PluginsPage.tsx` (插件管理页面，整合 Sidebar + Detail)
- [x] T019 [US1] Add plugins route to `frontend/src/App.tsx` and navigation in `frontend/src/components/Layout/`
- [x] T020 [US1] Create CSS styles in `frontend/src/components/Plugins/Plugins.css`

**Checkpoint**: User Story 1 complete - 用户可以浏览已安装插件

---

## Phase 4: User Story 2 - 浏览插件市场 (Priority: P1) 🎯 MVP

**Goal**: 用户可以浏览所有可用插件，按分类筛选，搜索特定插件

**Independent Test**: 点击 "+" 按钮后可浏览所有可用插件，按标签页筛选，搜索功能正常

### Implementation for User Story 2

- [x] T021 [US2] Implement `GET /api/plugins/marketplace` endpoint in `backend/core/plugins.py` (browseMarketplace)
- [x] T022 [P] [US2] Create `frontend/src/components/Plugins/BrowsePluginsModal.tsx` (浏览插件市场弹窗)
- [x] T023 [US2] Add search and filter logic to marketplace API (search by name/description, filter by source)
- [x] T024 [US2] Integrate BrowsePluginsModal with PluginsPage (点击 "+" 按钮打开)

**Checkpoint**: User Story 2 complete - 用户可以浏览插件市场

---

## Phase 5: User Story 3 - 启用/禁用插件 (Priority: P2)

**Goal**: 用户可以控制哪些插件和 skill 对自己可用

**Independent Test**: 禁用某个插件后，该插件的 Commands 和 Skills 不再出现在自动完成列表中

### Implementation for User Story 3

- [x] T025 [US3] Implement `PATCH /api/plugins/{plugin_name}` endpoint in `backend/core/plugins.py` (updatePluginState)
- [x] T026 [US3] Add enable/disable toggle to `frontend/src/components/Plugins/PluginDetail.tsx`
- [x] T027 [US3] Implement user plugin state filtering in `backend/plugins/service.py` (get_enabled_plugins_for_user)
- [x] T028 [US3] Modify `backend/aime/planner.py` to filter agents/skills by user's enabled plugins
- [x] T029 [US3] Modify `backend/core/skills.py` GET /api/skills to respect user's enabled plugins

**Checkpoint**: User Story 3 complete - 用户可以启用/禁用插件

---

## Phase 6: User Story 5 - /命令调用 Skill (Priority: P1) 🎯 MVP

**Goal**: 用户在对话窗口中可通过 /命令直接调用特定的 skill

**Independent Test**: 用户在对话框输入 /skill-name，系统自动注入对应 skill 的指令并执行

### Implementation for User Story 5

- [x] T030 [US5] Modify `frontend/src/components/InputBar.tsx` to show autocomplete on `/` input
- [x] T031 [US5] Create `frontend/src/hooks/useSkillAutocomplete.ts` (fetch enabled skills, filter by input)
- [x] T032 [US5] Modify `frontend/src/api/client.ts` to include `skill` field in ChatRequest
- [x] T033 [US5] Verify `backend/core/chat.py` correctly handles `request.skill` (existing logic)
- [x] T034 [US5] Ensure disabled skills are excluded from autocomplete list

**Checkpoint**: User Story 5 complete - 用户可以通过 /命令调用 Skill

---

## Phase 7: User Story 4 - 上传插件包 (Priority: P3)

**Goal**: 用户可以通过上传 ZIP 文件安装自己的插件

**Independent Test**: 上传有效的插件包后，该插件出现在用户的插件列表中并可立即使用

### Implementation for User Story 4

- [x] T035 [US4] Create plugin validator in `backend/plugins/validator.py` (validate ZIP structure, AGENTS.md/SKILL.md presence)
- [x] T036 [US4] Implement `POST /api/plugins/upload` endpoint in `backend/core/plugins.py` (uploadPlugin)
- [x] T037 [US4] Implement ZIP extraction and storage in `backend/plugins/loader.py` (save to uploaded/{user_id}/{plugin_name}/)
- [x] T038 [US4] Implement dynamic plugin registration (load_agent_from_directory for uploaded plugins)
- [x] T039 [P] [US4] Create `frontend/src/components/Plugins/UploadPluginModal.tsx` (上传弹窗，拖放区域)
- [x] T040 [US4] Integrate UploadPluginModal with PluginsPage ("+" → "Upload plugin")
- [x] T041 [US4] Implement `DELETE /api/plugins/{plugin_name}` endpoint in `backend/core/plugins.py` (deletePlugin)

**Checkpoint**: User Story 4 complete - 用户可以上传和删除插件

---

## Phase 8: User Story 6 - Workflow Skill 任务规划 (Priority: P2)

**Goal**: Workflow 类型的 skill 自动进行多步骤任务规划和执行

**Independent Test**: 调用 workflow skill 后，系统按预定义步骤规划任务，依次执行并汇总结果

### Implementation for User Story 6

- [x] T042 [US6] Verify `backend/skills/registry.py` supports workflow type and steps
- [x] T043 [US6] Verify `backend/aime/planner.py` `_expand_workflow_skill()` works correctly
- [x] T044 [US6] Add workflow skill indicator in `frontend/src/components/Plugins/PluginDetail.tsx` (显示 steps)
- [x] T045 [US6] Modify `/命令` autocomplete to show skill type indicator (atomic vs workflow)

**Checkpoint**: User Story 6 complete - Workflow Skills 正常执行

---

## Phase 9: User Story 7 - 插件评分 (Priority: P3)

**Goal**: 用户可以对 Package 和 Shared 插件评分

**Independent Test**: 用户对某个插件评分后，该评分显示在插件详情页，其他用户可以看到平均评分

### Implementation for User Story 7

- [x] T046 [US7] Implement `PUT /api/plugins/{plugin_name}/rating` endpoint in `backend/core/plugins.py` (ratePlugin)
- [x] T047 [US7] Implement `GET /api/plugins/{plugin_name}/rating` endpoint in `backend/core/plugins.py` (getPluginRating)
- [x] T048 [US7] Add rating component to `frontend/src/components/Plugins/PluginDetail.tsx` (星级评分 UI)
- [x] T049 [US7] Add average rating display to `frontend/src/components/Plugins/BrowsePluginsModal.tsx`
- [x] T050 [US7] Add rating aggregation query in `backend/plugins/database.py` (calculate average and count)

**Checkpoint**: User Story 7 complete - 用户可以评分插件

---

## Phase 10: User Story 8 - 分享插件 (Priority: P3)

**Goal**: 用户可以将自己上传的插件分享到插件市场

**Independent Test**: 分享插件后，该插件出现在插件市场 "Shared" 分类，其他用户可以看到并启用

### Implementation for User Story 8

- [x] T051 [US8] Implement `POST /api/plugins/{plugin_name}/share` endpoint in `backend/core/plugins.py` (sharePlugin)
- [x] T052 [US8] Implement `DELETE /api/plugins/{plugin_name}/share` endpoint in `backend/core/plugins.py` (unsharePlugin)
- [x] T053 [P] [US8] Create `frontend/src/components/Plugins/SharePluginModal.tsx` (分享确认对话框)
- [x] T054 [US8] Add share/unshare button to PluginDetail.tsx (仅 uploaded 插件显示)
- [x] T055 [US8] Handle delisted state in plugin service (is_delisted = true 时保留已启用用户的访问)
- [x] T056 [US8] Add "Shared" tab to BrowsePluginsModal marketplace tabs

**Checkpoint**: User Story 8 complete - 用户可以分享和取消分享插件

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T057 [P] Add loading states and error handling to all frontend components
- [x] T058 [P] Add validation error messages for upload failures
- [x] T059 Run `uv run pyright` and fix type errors
- [x] T060 Run `cd frontend && npx tsc` and fix TypeScript errors
- [x] T061 Run quickstart.md validation scenarios
- [x] T062 Verify all API endpoints match contracts/plugins-api.yaml

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational completion
- **Polish (Phase 11)**: Depends on desired user stories being complete

### User Story Dependencies

| Story | Priority | Dependencies | Can Start After |
|-------|----------|--------------|-----------------|
| US1 浏览已安装插件 | P1 | None | Foundational |
| US2 浏览插件市场 | P1 | US1 (共享 PluginsPage) | US1 |
| US3 启用/禁用插件 | P2 | US1 (需要详情面板) | US1 |
| US5 /命令调用 | P1 | US3 (需要过滤逻辑) | US3 |
| US4 上传插件包 | P3 | US2 (需要 BrowseModal) | US2 |
| US6 Workflow Skill | P2 | US5 (需要 /命令基础) | US5 |
| US7 插件评分 | P3 | US2 (需要市场展示) | US2 |
| US8 分享插件 | P3 | US4 (需要上传功能) | US4 |

### MVP Scope (P1 Stories)

**Minimum Viable Product 包含**:
1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: US1 - 浏览已安装插件
4. Phase 4: US2 - 浏览插件市场
5. Phase 5: US3 - 启用/禁用插件
6. Phase 6: US5 - /命令调用 Skill

**MVP 完成后可独立交付和验证**

---

## Parallel Execution Examples

### Phase 1 (Setup)

```bash
# 可并行执行：
T002 Create Pydantic models in backend/plugins/models.py
T003 Create TypeScript types in frontend/src/types/plugins.ts
T004 Create API client in frontend/src/api/plugins.ts
```

### Phase 2 (Foundational)

```bash
# 可并行执行（在 T006 完成后）：
T007 Implement database CRUD in backend/plugins/database.py
T008 Extend backend/skills/registry.py with source field
T009 Extend backend/skills/loader.py to accept source parameter
```

### Phase 3 (US1)

```bash
# 可并行执行：
T016 Create PluginSidebar.tsx
T017 Create PluginDetail.tsx
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 - 浏览已安装插件
4. Complete Phase 4: US2 - 浏览插件市场
5. Complete Phase 5: US3 - 启用/禁用插件
6. Complete Phase 6: US5 - /命令调用 Skill
7. **STOP and VALIDATE**: 运行 quickstart.md 场景 1-5

### Incremental Delivery

| 交付里程碑 | 包含 Stories | 新增能力 |
|-----------|--------------|----------|
| MVP | US1, US2, US3, US5 | 浏览、启用/禁用、/命令 |
| v1.1 | + US4 | 上传插件 |
| v1.2 | + US6, US7 | Workflow、评分 |
| v1.3 | + US8 | 分享插件 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- 每个 User Story 应可独立完成和测试
- 完成每个 task 或逻辑组后提交
- 在任何 checkpoint 停止以独立验证 story
- 避免：模糊任务、同文件冲突、破坏独立性的跨 story 依赖
