# Tasks: Unified LLM Provider

**Input**: Design documents from `/specs/004-unified-llm-provider/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (Constitution requires test coverage for core business logic)

**Organization**: Single user story (P1) - one-shot implementation

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US1]**: User Story 1 - 一键切换 LLM 提供商
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Add dependencies and create module structure

- [x] T001 Add litellm and langchain-litellm dependencies to pyproject.toml
- [x] T002 Create backend/llm/ directory structure with __init__.py

---

## Phase 2: Foundational (LLM Module)

**Purpose**: Implement core LLM configuration module - MUST complete before agent modifications

**⚠️ CRITICAL**: No agent modifications can begin until this phase is complete

- [x] T003 [P] Implement LLMProvider enum and ProviderConfig types in backend/llm/config.py
- [x] T004 [P] Implement PROVIDER_PRESETS with model mappings in backend/llm/config.py
- [x] T005 Implement get_model() factory function in backend/llm/factory.py
- [x] T006 Implement validate_config() function in backend/llm/factory.py
- [x] T007 Export get_model and validate_config from backend/llm/__init__.py
- [x] T008 [P] Add unit tests for config validation in tests/unit/test_llm_config.py
- [x] T009 [P] Add unit tests for get_model() in tests/unit/test_llm_config.py

**Checkpoint**: LLM module ready - run `uv run pytest tests/unit/test_llm_config.py` to verify

---

## Phase 3: User Story 1 - 一键切换 LLM 提供商 (Priority: P1) 🎯 MVP

**Goal**: 通过设置 `LLM_PROVIDER` 环境变量切换所有 Agent 使用的 LLM 提供商

**Independent Test**:
1. Set `LLM_PROVIDER=openai` in .env
2. Restart backend
3. Check logs show "Using LLM provider: openai"
4. Send a chat message and verify response comes from OpenAI

### Implementation for User Story 1

- [x] T010 [P] [US1] Update backend/supervisor.py to use get_model("supervisor")
- [x] T011 [P] [US1] Update backend/agents/research.py to use get_model("research")
- [x] T012 [P] [US1] Update backend/agents/sql.py to use get_model("sql")
- [x] T013 [P] [US1] Update backend/agents/general.py to use get_model("general")
- [x] T014 [P] [US1] Update backend/agents/loader.py to use get_model(agent_name)
- [x] T015 [US1] Add config validation call in backend/main.py lifespan startup
- [x] T016 [US1] Add provider logging in backend/main.py startup

**Checkpoint**: All agents now use configurable LLM provider

---

## Phase 4: Polish & Documentation

**Purpose**: Update documentation and environment examples

- [x] T017 [P] Update .env.example with LLM_PROVIDER and DEEPSEEK_API_KEY
- [x] T018 [P] Update CLAUDE.md with LLM_PROVIDER configuration docs
- [x] T019 Run quickstart.md validation (manual test with each provider)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS all agent modifications
    ↓
Phase 3 (User Story 1) ← Can run after Phase 2
    ↓
Phase 4 (Polish)
```

### Task Dependencies

```
T001 → T002 → T003, T004 (parallel)
              ↓
           T005, T006 → T007 → T008, T009 (parallel tests)
                        ↓
        T010, T011, T012, T013, T014 (parallel agent updates)
                        ↓
                 T015 → T016
                        ↓
              T017, T018 (parallel docs)
                        ↓
                      T019
```

### Parallel Opportunities

**Phase 2** (after T002):
- T003 and T004 can run in parallel (different sections of config.py)
- T008 and T009 can run in parallel (different test functions)

**Phase 3** (after T007):
- T010, T011, T012, T013, T014 can ALL run in parallel (different files)

**Phase 4**:
- T017 and T018 can run in parallel (different files)

---

## Parallel Example: Agent Updates

```bash
# Launch all agent updates together (after Phase 2 complete):
Task: "Update backend/supervisor.py to use get_model('supervisor')"
Task: "Update backend/agents/research.py to use get_model('research')"
Task: "Update backend/agents/sql.py to use get_model('sql')"
Task: "Update backend/agents/general.py to use get_model('general')"
Task: "Update backend/agents/loader.py to use get_model(agent_name)"
```

---

## Implementation Strategy

### MVP Delivery (Recommended)

1. Complete Phase 1: Setup (~5 min)
2. Complete Phase 2: Foundational (~30 min)
3. Run tests: `uv run pytest tests/unit/test_llm_config.py`
4. Complete Phase 3: Agent updates (~20 min, parallel)
5. **VALIDATE**: Test with `LLM_PROVIDER=anthropic` (default behavior)
6. **VALIDATE**: Test with `LLM_PROVIDER=openai` (new capability)
7. Complete Phase 4: Polish (~10 min)

### Estimated Time

- Total tasks: 19
- Parallel opportunities: 11 tasks can be parallelized
- Sequential critical path: ~8 tasks
- Estimated time: 1-2 hours

---

## Notes

- All agent files (T010-T014) modify only the LLM initialization, not the agent logic
- The change in each agent file is minimal: replace `init_chat_model(...)` with `get_model("agent_name")`
- Tests in Phase 2 should mock environment variables to test all providers
- Validation requires having API keys for at least one provider
