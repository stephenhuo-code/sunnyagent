# Tasks: Meta-Agent Plugin Optimization System

**Input**: Design documents from `/specs/013-meta-agent/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US0, US1, US2)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md, this is a single project structure:
- **Source code**: `meta_agent/` at repository root
- **Tests**: `tests/` at repository root

---

## Phase 1: Setup (Project Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create `meta_agent/` directory structure per plan.md
- [x] T002 Initialize Python project with `pyproject.toml` (uv managed)
- [x] T003 [P] Add dependencies: anthropic, langfuse, httpx, gitpython, pyyaml, pydantic
- [x] T004 [P] Configure pyright for type checking (`pyrightconfig.json`)
- [x] T005 [P] Create `meta_agent/__init__.py` with version info

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Data Models

- [x] T006 [P] Create `meta_agent/models/__init__.py` with exports
- [x] T007 [P] Implement TestCase, TestDataset models in `meta_agent/models/dataset.py`
- [x] T008 [P] Implement EvaluationResult, CaseResult, CaseScore in `meta_agent/models/evaluation.py`
- [x] T009 [P] Implement OptimizationConfig, Checkpoint in `meta_agent/models/optimization.py`
- [x] T010 [P] Implement Command, Skill structures in `meta_agent/models/plugin.py`

### Core Utilities

- [x] T011 [P] Implement score_calculator in `meta_agent/utils/score_calculator.py` (50% correctness, 16.7% each for others)
- [x] T012 [P] Implement git_utils in `meta_agent/utils/git_utils.py` (commit, revert, diff)

### Configuration

- [x] T013 Create config loader in `meta_agent/config.py` (YAML parsing, env vars, defaults)
- [x] T014 [P] Create example `meta_agent/config.yaml` with defaults

### Services Infrastructure

- [x] T015 [P] Create `meta_agent/services/__init__.py` with exports
- [x] T016 Implement LangfuseClient in `meta_agent/services/langfuse_client.py` per contracts/langfuse-client.md
- [x] T017 Implement SunnyAgentClient in `meta_agent/services/sunnyagent_client.py` per contracts/sunnyagent-client.md
- [x] T018 Implement FileService in `meta_agent/services/file_service.py` per contracts/file-service.md (packages/ restriction)

### Agents Infrastructure

- [x] T019 [P] Create `meta_agent/agents/__init__.py` with exports
- [x] T020 Create base Agent structure for Claude Agent Team integration

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 0 - 测试环境准备 (Priority: P1) 🎯 MVP

**Goal**: Prepare test environment: create test projects, upload files, prepare conversation context

**Independent Test**: Create a test project, upload sample files, verify file availability

### Tests for US0

- [x] T021 [P] [US0] Unit test for SunnyAgentClient project operations in `tests/unit/test_sunnyagent_client.py`
- [x] T022 [P] [US0] Unit test for file upload/download in `tests/unit/test_sunnyagent_client.py`
  - Note: SunnyAgentClient integration tests require running SunnyAgent server

### Implementation for US0

- [x] T023 [US0] Implement EnvironmentSetupAgent in `meta_agent/agents/environment_setup.py`
  - Create test project via SunnyAgentClient
  - Upload files from test-resources/files/
  - Validate context_files exist before execution
- [x] T024 [US0] Add project management methods to SunnyAgentClient (create_project, get_project, delete_project)
- [x] T025 [US0] Add file management methods to SunnyAgentClient (upload_file, get_project_files)
- [x] T026 [US0] Add conversation methods to SunnyAgentClient (create_conversation, get_conversation)
- [x] T027 [US0] Create `meta_agent/test-resources/` directory structure (datasets/, files/)
- [x] T028 [US0] Implement test environment cleanup logic (optional project deletion)

**Checkpoint**: Test environment can be created with projects and files

---

## Phase 4: User Story 1 - 测试数据集模板与创建 (Priority: P1) 🎯 MVP

**Goal**: Users can create test datasets using templates, validate and sync to Langfuse

**Independent Test**: Fill template with 5 cases including file dependencies, verify Langfuse Dataset creation

### Tests for US1

- [x] T029 [P] [US1] Unit test for dataset validation in `tests/unit/test_dataset_service.py`
- [x] T030 [P] [US1] Unit test for JSONL/CSV parsing in `tests/unit/test_dataset_service.py`
- [x] T031 [P] [US1] Integration test for Langfuse Dataset sync in `tests/integration/test_langfuse_client.py`

### Implementation for US1

- [x] T032 [US1] Create DatasetService in `meta_agent/services/dataset_service.py`
  - Validate dataset format (JSONL/CSV)
  - Check context_files existence
  - Report errors with line numbers
- [x] T033 [US1] Implement Langfuse Dataset creation in LangfuseClient (create_dataset, create_dataset_item)
- [x] T034 [US1] Implement dataset sync logic (local → Langfuse) with auto-versioning (v1, v2...)
- [x] T035 [US1] Implement incremental dataset updates (add/modify cases)
- [x] T036 [P] [US1] Create dataset template files:
  - `specs/013-meta-agent/templates/dataset-template.csv`
  - `specs/013-meta-agent/templates/dataset-template.jsonl`
- [x] T037 [US1] Add CLI command for dataset validation: `meta_agent validate --dataset PATH`
- [x] T038 [US1] Add CLI command for dataset sync: `meta_agent sync --dataset PATH`

**Checkpoint**: Datasets can be created, validated, and synced to Langfuse

---

## Phase 5: User Story 2 - 基于 Langfuse 的评估执行 (Priority: P1) 🎯 MVP

**Goal**: Execute tests via SunnyAgent API, read traces from Langfuse, calculate scores

**Independent Test**: Run evaluation on a Dataset with file dependencies, view results in Langfuse

### Tests for US2

- [x] T039 [P] [US2] Unit test for score calculation in `tests/unit/test_score_calculator.py`
- [x] T040 [P] [US2] Unit test for evaluation execution in `tests/unit/test_evaluation_service.py`
- [x] T041 [P] [US2] Integration test for SunnyAgent chat in `tests/integration/test_sunnyagent_client.py`

### Implementation for US2

- [x] T042 [US2] Implement EvaluationService in `meta_agent/services/evaluation_service.py` per contracts/evaluation-service.md
  - run_evaluation(): orchestrate full evaluation
  - run_single_case(): execute one test case
  - calculate_case_score(): score individual case
- [x] T043 [US2] Add chat methods to SunnyAgentClient (send_message, send_message_and_wait)
- [x] T044 [US2] Implement trace reading from Langfuse (get_traces, get_trace_detail)
- [x] T045 [US2] Implement score writing to Langfuse (add_score, add_scores_batch)
- [x] T046 [US2] Implement EvaluatorAgent in `meta_agent/agents/evaluator.py`
  - Execute test cases in prepared environment
  - Read traces from Langfuse
  - Calculate and report scores
- [x] T047 [US2] Add retry logic with exponential backoff for API calls (max 3 retries)
- [x] T048 [US2] Add CLI command for evaluation: `meta_agent evaluate --dataset PATH`

**Checkpoint**: Evaluations can be executed and results appear in Langfuse

---

## Phase 6: User Story 3 - 失败分析与改进建议 (Priority: P1)

**Goal**: Analyzer Agent reads evaluation results from Langfuse, categorizes failures, generates improvement suggestions

**Independent Test**: Run evaluation, verify Agent correctly classifies failures and gives reasonable suggestions

### Tests for US3

- [x] T049 [P] [US3] Unit test for failure categorization in `tests/unit/test_analyzer.py`
- [x] T050 [P] [US3] Unit test for suggestion generation in `tests/unit/test_analyzer.py`

### Implementation for US3

- [x] T051 [US3] Implement AnalyzerAgent in `meta_agent/agents/analyzer.py`
  - Read failed case details from Langfuse (including file context)
  - Categorize failures by type (skill_not_triggered, wrong_skill, output_incorrect, etc.)
  - Identify file-related failures
  - Generate prioritized improvement suggestions
- [x] T052 [US3] Define failure categories enum in `meta_agent/models/evaluation.py`
- [x] T053 [US3] Implement suggestion prioritization logic (impact × frequency)

**Checkpoint**: Failures are analyzed and actionable suggestions generated

---

## Phase 7: User Story 4 - Command/Skill 自动生成与修改 (Priority: P2)

**Goal**: Generator Agent creates/modifies Command and Skill files based on analysis

**Independent Test**: Given a failure case and suggestion, verify generated modification follows schema

### Tests for US4

- [x] T054 [P] [US4] Unit test for Command generation in `tests/unit/test_generator.py`
- [x] T055 [P] [US4] Unit test for Skill generation in `tests/unit/test_generator.py`
- [x] T056 [P] [US4] Unit test for FileService path validation in `tests/unit/test_file_service.py`

### Implementation for US4

- [x] T057 [US4] Implement GeneratorAgent in `meta_agent/agents/generator.py`
  - Generate new Command files (commands/*.md)
  - Modify existing Command files
  - Generate new Skill files (skills/*/SKILL.md)
  - Modify existing Skill files
- [x] T058 [US4] Implement Command/Skill schema validation in FileService
- [x] T059 [US4] Implement git commit automation after each modification
- [x] T060 [US4] Implement file backup before modification
- [x] T061 [US4] Add path validation to reject writes outside packages/

**Checkpoint**: Files can be generated/modified with git tracking

---

## Phase 8: User Story 5 - 迭代优化循环 (Priority: P2)

**Goal**: Orchestrator Agent coordinates complete optimization loop until convergence

**Independent Test**: Set low target score with small dataset, verify complete loop runs and terminates

### Tests for US5

- [x] T062 [P] [US5] Unit test for termination conditions in `tests/unit/test_orchestrator.py`
- [x] T063 [P] [US5] Unit test for checkpoint save/load in `tests/unit/test_orchestrator.py`
- [x] T064 [US5] Integration test for full optimization loop in `tests/integration/test_optimization_loop.py`

### Implementation for US5

- [x] T065 [US5] Implement OrchestratorAgent in `meta_agent/agents/orchestrator.py`
  - Coordinate: Environment → Evaluate → Analyze → Generate → Review → Re-evaluate
  - Manage iteration state
  - Apply termination conditions (target_score, max_iterations, patience)
- [x] T066 [US5] Implement checkpoint persistence (save state after each iteration)
- [x] T067 [US5] Implement checkpoint resume logic
- [x] T068 [US5] Implement iteration report generation (Langfuse links, score delta, modifications)
- [x] T069 [US5] Add CLI command for optimization: `meta_agent optimize [OPTIONS]`
- [x] T070 [US5] Add CLI command for resume: `meta_agent resume --checkpoint-id <uuid>`

**Checkpoint**: Full optimization loop can run and converge

---

## Phase 9: User Story 6 - 回归检测与自动回滚 (Priority: P2)

**Goal**: Detect regression when modifications cause score drops, auto-rollback problematic changes

**Independent Test**: Intentionally introduce regression-causing change, verify detection and rollback

### Tests for US6

- [x] T071 [P] [US6] Unit test for regression detection in `tests/unit/test_orchestrator.py`
- [x] T072 [P] [US6] Unit test for git rollback in `tests/unit/test_git_utils.py`

### Implementation for US6

- [x] T073 [US6] Implement regression detection in OrchestratorAgent
  - Compare scores before/after modification
  - Detect when score drops beyond regression_threshold
- [x] T074 [US6] Implement auto-rollback via git revert
- [x] T075 [US6] Add alternative strategy selection after rollback

**Checkpoint**: Regressions are detected and rolled back automatically

---

## Phase 10: User Story 7 - 最终报告生成 (Priority: P3)

**Goal**: Generate comprehensive final report after optimization completion

**Independent Test**: Complete one optimization, verify report contains all required information

### Tests for US7

- [x] T076 [P] [US7] Unit test for report generation in `tests/unit/test_report.py`

### Implementation for US7

- [x] T077 [US7] Implement report generator in `meta_agent/utils/report_generator.py`
  - Generate Markdown report with:
    - Initial/final scores
    - Total iterations
    - Langfuse Dashboard links
    - File change list with git commit hashes
    - Key findings and patterns
    - Unresolved issues and recommendations
- [x] T078 [US7] Save reports to `meta_agent/results/report-<timestamp>.md`

**Checkpoint**: Comprehensive reports generated for completed optimizations

---

## Phase 11: User Story Review - 内容质量审查 (Priority: P2)

**Goal**: Reviewer Agent validates generated content quality before application

### Implementation

- [x] T079 Implement ReviewerAgent in `meta_agent/agents/reviewer.py`
  - Format validation (Command/Skill schema compliance)
  - Content quality check
  - Consistency verification with existing plugin structure
- [x] T080 Integrate ReviewerAgent into optimization loop (Generator → Reviewer → Apply)

**Checkpoint**: Generated content is quality-checked before application

---

## Phase 12: CLI Entry Point & Polish

**Purpose**: Complete CLI interface and cross-cutting concerns

### CLI Implementation

- [x] T081 Implement CLI entry point in `meta_agent/main.py`
  - `optimize` command with options (--config, --target-plugin, --dataset, --dry-run)
  - `evaluate` command
  - `resume` command
  - `validate` command
  - `sync` command
  - `checkpoints list/show` commands
- [x] T082 [P] Add help text and usage examples for all commands
- [x] T083 [P] Add progress output for long-running operations

### Testing & Documentation

- [x] T084 [P] Add conftest.py with shared fixtures in `tests/conftest.py`
- [x] T085 [P] Verify quickstart.md workflow end-to-end
- [x] T086 [P] Add error handling for common failure scenarios
- [x] T087 [P] Add logging throughout the system

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US0 (Phase 3)**: Depends on Foundational (T016-T018 services)
- **US1 (Phase 4)**: Depends on US0 for test environment
- **US2 (Phase 5)**: Depends on US0, US1 for environment and datasets
- **US3 (Phase 6)**: Depends on US2 for evaluation results
- **US4 (Phase 7)**: Depends on US3 for analysis suggestions
- **US5 (Phase 8)**: Depends on US0-US4 (full loop integration)
- **US6 (Phase 9)**: Depends on US5 for optimization loop
- **US7 (Phase 10)**: Depends on US5 for completed optimizations
- **Review (Phase 11)**: Can parallel with US6-US7
- **CLI & Polish (Phase 12)**: Depends on all user stories

### Critical Path

```
Setup → Foundational → US0 → US1 → US2 → US3 → US4 → US5 → CLI
                                                    ↘
                                                      US6/US7/Review
```

### Parallel Opportunities

**Within Setup/Foundational:**
- T003, T004, T005 can run in parallel
- T006-T010 (all models) can run in parallel
- T011, T012 (utilities) can run in parallel
- T015, T016, T017, T018 (services) - T016/T017/T018 can run in parallel after T015

**Within User Stories:**
- Tests marked [P] within each story can run in parallel
- US6, US7, Phase 11 can run in parallel after US5 completion

**Team Strategy:**
- Team completes Setup + Foundational together
- Then proceed through US0-US5 sequentially (critical path)
- Parallelize US6, US7, and Review (Phase 11) once US5 is stable

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All file modifications MUST be within `packages/` directory
- Test with small datasets first before scaling up
