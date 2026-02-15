# Implementation Plan: AIME Agent Core & Supervisor Optimization

**Branch**: `005-aime-supervisor` | **Date**: 2026-02-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-aime-supervisor/spec.md`

## Summary

基于 ByteDance AIME 论文重构 SunnyAgent 的 Supervisor 和 General Agent，实现动态规划和自适应执行。核心变更：
- 替换 Supervisor + General Agent 为 AIME Planner + Actor Factory + Dynamic Actor
- 新增 Intent Module 支持 4 种 action：direct_reply, delegate, plan, clarify
- 扩展 AgentEntry 支持 capabilities 和自定义 Agent 统一选择
- 保持现有 SSE 事件格式和前端兼容性

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript/React 19 (frontend)
**Primary Dependencies**: FastAPI, LangGraph, deepagents (>=0.2.6), langchain, litellm
**Storage**: PostgreSQL 15 (via asyncpg + LangGraph AsyncPostgresSaver)
**Testing**: pytest (backend), Playwright (e2e)
**Target Platform**: Linux server (backend), modern browsers (frontend)
**Project Type**: Web application (FastAPI backend + React frontend)
**Performance Goals**: 简单任务响应 < 2s, 意图识别延迟 < 300ms, Agent 选择延迟 < 500ms
**Constraints**: 保持现有 SSE 事件格式兼容，前端无需改动
**Scale/Scope**: 替换核心路由层，影响所有用户交互流程

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | AIME Planner 和各 Actor 独立运行，通过 SubtaskSpec 解耦 |
| II. 注册驱动发现 | ✅ PASS | 扩展 AgentEntry 添加 capabilities，Actor Factory 从 AGENT_REGISTRY 动态发现 |
| III. 流式优先 | ✅ PASS | 保持现有 SSE 事件格式，复用 stream_handler.py |
| IV. 包扩展性 | ✅ PASS | 自定义 Agent 通过 AGENTS.md frontmatter 声明 capabilities，自动加载 |
| V. 简洁性 | ✅ PASS | 仅替换必要组件（Supervisor + General），复用 Research/SQL Agent |
| VI. 测试优先 | ✅ PASS | 每个组件设计时明确测试策略，现有 E2E 测试作为兼容性门禁 |
| VII. 分层依赖 | ✅ PASS | API → Planner → Actor Factory → Actor → Service/Repository → DB |
| VIII. 接口优先 | ✅ PASS | SubtaskSpec、IntentResult 等数据契约在 models.py 中明确定义 |
| IX. 安全边界 | ✅ PASS | Generic Actor 继承现有沙箱执行机制，capabilities 限制工具访问 |

## Project Structure

### Documentation (this feature)

```text
specs/005-aime-supervisor/
├── plan.md              # This file
├── research.md          # Phase 0 output - 依赖研究、技术选型
├── data-model.md        # Phase 1 output - 核心数据结构
├── quickstart.md        # Phase 1 output - 快速开始指南
├── contracts/           # Phase 1 output - 接口契约
│   ├── intent.py        # IntentResult, Action, IntentAnalyzer 接口
│   ├── planner.py       # SubtaskSpec, PlannerBase 接口
│   ├── actor_factory.py # ActorFactory 接口
│   └── progress.py      # ProgressManager 接口
└── tasks.md             # Phase 2 output - 任务列表
```

### Source Code (repository root)

```text
backend/
├── aime/                        # 新增：AIME 模块
│   ├── __init__.py              # 导出 AIMEPlanner, ActorFactory
│   ├── planner.py               # AIME Dynamic Planner
│   ├── actor_factory.py         # Actor Factory
│   ├── progress_manager.py      # Progress Manager
│   ├── models.py                # SubtaskSpec, ProgressList, etc.
│   ├── intent/                  # 意图识别模块
│   │   ├── __init__.py          # 导出 IntentAnalyzer, IntentResult
│   │   ├── analyzer.py          # 核心分析器
│   │   ├── models.py            # IntentResult, Action, CAPABILITY_AGENT_MAP
│   │   └── classifiers/         # 分类器（可插拔）
│   │       ├── base.py          # ClassifierBase 抽象基类
│   │       ├── rule_based.py    # 规则匹配
│   │       ├── keyword_based.py # 关键词匹配
│   │       └── llm_based.py     # LLM 深度分析
│   └── actors/                  # Dynamic Actors
│       ├── __init__.py
│       └── generic.py           # Generic Actor
├── agents/
│   ├── research.py              # 修改：添加 capabilities 注册
│   ├── sql.py                   # 修改：添加 capabilities 注册
│   ├── general.py               # 废弃：标记为 deprecated
│   └── loader.py                # 修改：解析 AGENTS.md capabilities
├── skills/
│   ├── registry.py              # 修改：添加 WORKFLOW_SKILLS
│   └── loader.py                # 修改：解析 type/steps 字段
├── registry.py                  # 修改：AgentEntry 添加 capabilities, source
├── supervisor.py                # 修改：重写为调用 AIMEPlanner
├── stream_handler.py            # 保持不变
└── main.py                      # 修改：更新 import 路径

tests/
├── unit/
│   └── aime/
│       ├── test_intent_analyzer.py
│       ├── test_planner.py
│       ├── test_actor_factory.py
│       └── test_progress_manager.py
├── integration/
│   └── test_aime_flow.py
└── e2e/
    └── (existing tests - compatibility gate)
```

**Structure Decision**: 选择在 `backend/` 下新增 `aime/` 模块，保持与现有 `agents/` 分离，明确 AIME 架构的边界。意图识别封装为独立子模块 `aime/intent/`，支持分类器可插拔扩展。

## Complexity Tracking

> **No violations identified** - 设计遵循 Constitution 所有原则。

| Aspect | Current Design | Simplicity Check |
|--------|----------------|------------------|
| 模块数量 | 1 个新模块 (aime/) | ✅ 最小必要 |
| 分类器数量 | 3 个 (rule/keyword/llm) | ✅ 按需执行，非全部调用 |
| 新数据类型 | IntentResult, SubtaskSpec | ✅ 核心契约，必要抽象 |
| 现有代码改动 | 5 个文件 | ✅ 最小侵入，主要是添加字段 |

---

## Phase 0: Research (Pre-Implementation)

### 0.1 LangGraph StateGraph 集成模式

**目标**: 研究 AIME Planner 与 LangGraph StateGraph 的最佳集成方式。

**研究问题**:
- Q1: Planner 作为 StateGraph 节点还是独立组件？
- Q2: 子任务并行执行如何映射到 StateGraph 分支？
- Q3: 动态重规划如何实现状态回溯？

**参考资源**:
- LangGraph 官方文档: https://langchain-ai.github.io/langgraph/
- 现有 supervisor.py 实现
- 现有 agents/general.py 实现

### 0.2 deepagents 中间件栈

**目标**: 研究如何在 AIME Actor 中复用 deepagents 中间件。

**研究问题**:
- Q1: Generic Actor 是否使用 create_deep_agent()？
- Q2: Skill Instructions 注入点在中间件栈的哪一层？
- Q3: Progress 上报是否需要新的中间件？

### 0.3 现有 SSE 事件流分析

**目标**: 确保 AIME 架构与现有前端 SSE 处理完全兼容。

**研究问题**:
- Q1: todos_updated 事件的 payload 格式要求？
- Q2: task_spawned/task_completed 事件的触发时机？
- Q3: displayScenario 状态机的完整转换规则？

---

## Phase 1: Design Artifacts

### 1.1 Data Model (data-model.md)

生成核心数据结构文档：
- IntentResult: 意图分析结果
- SubtaskSpec: Planner 输出的子任务规格
- Actor: Actor Factory 输出的执行单元
- ProgressItem: Progress Manager 的状态项

### 1.2 Contracts (contracts/)

定义模块间接口契约：
- `contracts/intent.py`: IntentAnalyzer 接口和 ClassifierBase 抽象基类
- `contracts/planner.py`: PlannerBase 和 SubtaskSpec
- `contracts/actor_factory.py`: ActorFactory 接口
- `contracts/progress.py`: ProgressManager 接口

### 1.3 Quickstart (quickstart.md)

提供开发者快速开始指南：
- 如何添加新的 Classifier
- 如何扩展 Agent capabilities
- 如何创建 Workflow Skill

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM 调用延迟影响意图识别性能 | Medium | Medium | 规则+关键词分类器前置，LLM 仅在不确定时调用 |
| 现有 E2E 测试失败 | High | Low | SSE 事件格式保持不变，使用相同的 stream_handler |
| 自定义 Agent capabilities 声明不规范 | Low | Medium | 提供 AGENTS.md 模板和验证逻辑 |
| 复杂任务分解不准确 | Medium | Medium | 初版保守分解，后续迭代优化 |

---

## Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| 004-unified-llm-provider | External | 使用 litellm 作为 LLM 接口 |
| LangGraph | Package | StateGraph 编排 |
| deepagents | Package | create_deep_agent() 和中间件 |
| pytest | Dev | 单元测试 |
| Playwright | Dev | E2E 兼容性测试 |

---

## Next Steps

1. **Phase 0**: 完成 research.md，解答技术选型问题
2. **Phase 1**: 生成 data-model.md 和 contracts/
3. **Phase 2**: 运行 `/speckit.tasks` 生成 tasks.md
4. **Implementation**: 按 tasks.md 顺序实现
