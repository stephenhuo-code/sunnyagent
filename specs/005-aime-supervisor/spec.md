# Feature Specification: AIME Agent Core & Supervisor Optimization

**Feature Branch**: `005-aime-supervisor`
**Created**: 2026-02-14
**Status**: Draft
**Reference**: [AIME: Towards Fully-Autonomous Multi-Agent Framework](./AIME.pdf) (ByteDance, arXiv:2507.11988)

## Overview

基于 AIME 论文的架构设计，重构 SunnyAgent 的 Supervisor 和 General Agent，实现动态规划和自适应执行。

### AIME 核心概念映射

| AIME 组件 | 论文定义 | SunnyAgent 实现 |
|-----------|---------|-----------------|
| **Dynamic Planner** | 中央编排器，持续根据实时反馈优化策略 | 替换 Supervisor + General Agent |
| **Actor Factory** | 按需实例化专业化 Actor | 新增模块，管理 Agent 选择和实例化 |
| **Dynamic Actor** | 执行具体子任务的自主 Agent | 复用现有 Research/SQL 等专业 Agent |
| **Progress Management** | 集中式状态管理，全局任务视图 | 使用现有 `todos_updated` SSE 事件 |

### 核心职责划分 (基于 AIME 论文)

```
┌─────────────────────────────────────────────────────────────────┐
│                         AIME 职责划分                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Planner (决定 "做什么" - WHAT)                                 │
│  ├─ 意图识别 (IntentAnalyzer)                                  │
│  ├─ 任务拆解 (Task Decomposition) ← 核心职责                    │
│  │   └─ 分解为子任务 DAG                                       │
│  │   └─ 确定依赖关系                                           │
│  │   └─ 生成 SubtaskSpec[]                                     │
│  ├─ 动态重规划 (Re-planning)                                   │
│  └─ 结果汇总                                                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Actor Factory (决定 "谁来做" - WHO)                            │
│  ├─ Agent 选择 (优先级: explicit > suggested > capability)     │
│  ├─ 能力校验 (验证 Agent 能力是否匹配)                          │
│  └─ Actor 配置 (tools, prompt, persona)  ← 论文强调的           │
│      └─ Toolkit Selection                                      │
│      └─ Prompt Generation (ρ, T, κ, ε, Γ)                      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dynamic Actor (决定 "怎么做" - HOW)                            │
│  ├─ ReAct 执行循环 (Reasoning → Action → Observation)          │
│  ├─ 工具调用                                                   │
│  └─ 进度上报 (Update_Progress tool)                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 核心数据流

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Planner                                                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. IntentAnalyzer.analyze()                               │  │
│  │    └─ 输出: IntentResult (action, capabilities, ...)      │  │
│  │                                                           │  │
│  │ 2. 根据 action 决策:                                       │  │
│  │    ├─ direct_reply → 直接回复 (不创建子任务)               │  │
│  │    ├─ delegate     → 创建单个 SubtaskSpec                 │  │
│  │    ├─ plan         → Task Decomposer 分解为 SubtaskSpec[] │  │
│  │    └─ clarify      → 返回追问，等待用户回答                │  │
│  │                                                           │  │
│  │ 3. 输出: SubtaskSpec (description, capabilities,          │  │
│  │          explicit_agent, depends_on)                      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼ SubtaskSpec (每个子任务)
┌─────────────────────────────────────────────────────────────────┐
│  Actor Factory                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Agent 选择 (优先级):                                    │  │
│  │    ├─ explicit_agent (用户指定) → 直接使用                 │  │
│  │    └─ capability matching (能力匹配) → 自动选择            │  │
│  │                                                           │  │
│  │ 2. Actor 配置:                                            │  │
│  │    └─ 组装 tools, prompt, persona                         │  │
│  │                                                           │  │
│  │ 3. 输出: Actor (name, graph, tools)                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼ Actor
┌─────────────────────────────────────────────────────────────────┐
│  Dynamic Actor                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ReAct Loop:                                               │  │
│  │    ┌──────────┐    ┌──────────┐    ┌──────────────┐       │  │
│  │    │ Reasoning│───→│  Action  │───→│ Observation  │──┐    │  │
│  │    └──────────┘    └──────────┘    └──────────────┘  │    │  │
│  │         ↑                                            │    │  │
│  │         └────────────────────────────────────────────┘    │  │
│  │                                                           │  │
│  │ 完成条件满足后:                                            │  │
│  │    └─ 返回执行结果给 Planner                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼ 执行结果
┌─────────────────────────────────────────────────────────────────┐
│  Planner (继续迭代)                                             │
│  ├─ 更新 Progress List                                         │
│  ├─ 检查是否需要重规划                                          │
│  ├─ 分派下一个子任务 (如果有)                                   │
│  └─ 汇总所有结果生成最终回复                                    │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
            Final Response to User
```

**关键点**:
- **Planner** 负责任务拆解，输出 SubtaskSpec[]
- **Actor Factory** 只接收已拆解的 SubtaskSpec，选择和配置 Actor
- **Dynamic Actor** 执行具体任务，返回结果给 Planner
- **Planner** 持续迭代直到所有子任务完成

---

### 职责划分总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AIME 架构                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │          AIME Planner (替换 Supervisor + General 编排)              │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐      ┌──────────────────────────────────────┐ │   │
│  │  │ IntentAnalyzer  │      │      Task Decomposer                 │ │   │
│  │  │ (意图识别模块)   │─────→│  (任务拆解 - Planner 核心职责)        │ │   │
│  │  │                 │      │  - 分解为子任务 DAG                   │ │   │
│  │  │ 输出:           │      │  - 确定依赖关系                       │ │   │
│  │  │ IntentResult    │      │  - 为每个子任务生成 SubtaskSpec       │ │   │
│  │  └─────────────────┘      └──────────────────────────────────────┘ │   │
│  │         ↓                              ↓                            │   │
│  │  IntentResult                   SubtaskSpec[]                       │   │
│  │  (action, confidence,           (description, capabilities,        │   │
│  │   capabilities, domain)          explicit_agent, depends_on)        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │       Actor Factory (只做 Actor 选择和实例化, 不做任务拆解)          │   │
│  │                                                                     │   │
│  │  输入: SubtaskSpec (来自 Planner)                                   │   │
│  │                                                                     │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │ Priority Select  │  │ Capability Match │  │ Actor Instantiate│   │   │
│  │  │ 1.explicit_agent │→│  验证能力匹配     │→│  配置 tools/prompt│   │   │
│  │  │ 2.capability     │  │                  │  │                  │   │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │   │
│  │                                                                     │   │
│  │  输出: Actor (name, graph, tools, persona)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Dynamic Actors                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │   │
│  │  │Research Actor│  │  SQL Actor   │  │    Generic Actor           │ │   │
│  │  │(复用现有)     │  │ (复用现有)   │  │ (替换 General 的执行能力)   │ │   │
│  │  │              │  │              │  │ 仅通用工具:                 │ │   │
│  │  │ - web_search │  │ - sql_query  │  │ - sandbox (代码执行)        │ │   │
│  │  │ - tavily     │  │ - db_connect │  │ - file_tools (文件处理)     │ │   │
│  │  │              │  │              │  │ - activate_skill           │ │   │
│  │  └──────────────┘  └──────────────┘  └────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Progress Manager (使用现有 SSE)                   │   │
│  │                     todos_updated / tool_call / stream              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 能力替换映射

| 原有能力 | 原组件 | 新组件 | 说明 |
|----------|--------|--------|------|
| 意图识别 | Supervisor | **Planner** → IntentAnalyzer | 输出 action + capabilities |
| 简单路由 | Supervisor | **Planner** | action=direct_reply 时直接回复 |
| 任务拆解 | General | **Planner** → Task Decomposer | action=plan 时分解为子任务 DAG |
| 子任务定义 | General (task tool) | **Planner** → SubtaskSpec | 结构化任务描述 |
| Agent 选择 | Supervisor/General | **Actor Factory** | 优先级选择 + 能力匹配 |
| Actor 配置 | (无) | **Actor Factory** | 配置 tools/prompt/persona |
| 工具执行 | General | **Generic Actor** | 包含所有通用工具 |
| Skill 激活 | General | **Generic Actor** | 通过 activate_skill |

**关键区分**:
- **Planner**: 决定 "做什么" (What) - 任务拆解、依赖关系、子任务描述
- **Actor Factory**: 决定 "谁来做" (Who) - Agent 选择、能力匹配、Actor 配置
- **Dynamic Actor**: 负责 "怎么做" (How) - 具体执行、工具调用、进度上报

### 架构兼容性原则

1. **替换**: Supervisor (`supervisor.py`) + General Agent (`general.py`)
2. **保留**: Registry、Research Agent、SQL Agent、Stream Handler、SSE 事件格式
3. **兼容现有使用模式**:
   - 简单问答 → 直接回复 (action=direct_reply)
   - 专业任务 → 委派专业 Agent (action=delegate)
   - 复杂任务 → 动态规划 + 子任务分解 (action=plan)
   - 意图不清 → 追问澄清 (action=clarify)
4. **专业 Agent 执行作为任务**: 每次调用专业 Agent 都是 Progress List 中的一个 subtask

---

## Clarifications

### Session 2026-02-15

- Q: Re-planning 失败时的最大重试次数是多少？ → A: 3 次（平衡重试与超时）
- Q: 当达到并行子任务上限（3个）时，新任务如何处理？ → A: 等待（阻塞直到有空位，按 DAG 顺序执行）
- Q: IntentAnalyzer 触发 `clarify` action 的置信度阈值是多少？ → A: < 0.5（中等阈值，不确定时追问）
- Q: Generic Actor 的工具集是否应该包含所有已注册工具？ → A: 仅通用工具（sandbox, file_tools, activate_skill），专业工具不包含
- Q: Actor Factory 如何选择自定义 Agent 和预设 Agent？ → A: 扩展 AgentEntry 增加 capabilities 字段，统一能力匹配；优先级：显式指定 > 能力匹配分数（预设和自定义平等竞争）

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simple Query Direct Response (Priority: P1)

用户提出简单问题时，系统直接回复，不进行任务分解。

**Why this priority**: 保持现有用户体验，简单问题不应引入额外延迟。

**Independent Test**: 发送"你好"、"1+1等于几"等简单问题，验证直接回复无任务分解。

**Acceptance Scenarios**:

1. **Given** 用户发送简单问候"你好", **When** Planner 分析意图, **Then** 直接生成回复，无 subtask 创建
2. **Given** 用户问简单知识问题, **When** Planner 判断无需工具, **Then** 直接回答，响应时间 < 2秒

---

### User Story 2 - Explicit Agent Selection (Priority: P1)

用户显式指定使用某个专业 Agent 时，系统优先使用用户指定的 Agent。

**Why this priority**: 尊重用户意图，用户明确知道需要哪个 Agent 时应直接使用。

**Independent Test**: 前端选择 Research Agent 或消息包含 `[ROUTE_TO: research]`，验证直接路由。

**Acceptance Scenarios**:

1. **Given** 用户在前端选择 "Research Agent", **When** 发送任务, **Then** 直接创建子任务路由到 Research Agent
2. **Given** 消息包含 `[ROUTE_TO: sql]`, **When** Planner 处理, **Then** 跳过意图识别，直接路由到 SQL Agent
3. **Given** 用户指定的 Agent 不存在, **When** Actor Factory 处理, **Then** 返回错误提示可用 Agent 列表

---

### User Story 3 - Intelligent Agent Routing (Priority: P1)

用户任务未显式指定 Agent 时，系统智能识别并路由到最合适的专业 Agent。

**Why this priority**: 兼容现有专业 Agent 使用模式，专业 Agent 调用体现为可追踪的任务。

**Independent Test**: 发送"搜索最新的AI新闻"，验证创建 Research 子任务并执行。

**Acceptance Scenarios**:

1. **Given** 用户请求搜索信息, **When** Planner 识别为 Research 任务, **Then** 创建子任务"执行搜索"，调用 Research Agent
2. **Given** 用户请求 SQL 查询, **When** Planner 识别为 SQL 任务, **Then** 创建子任务"执行查询"，调用 SQL Agent
3. **Given** 专业 Agent 执行中, **When** 前端订阅 SSE, **Then** 收到 `todos_updated` 事件显示子任务进度
4. **Given** Planner 建议 Agent 与能力不匹配, **When** Actor Factory 选择, **Then** 可以覆盖 Planner 建议

---

### User Story 4 - Complex Task Decomposition (Priority: P1)

用户提出复杂任务时，Planner 动态分解为多个子任务并协调执行。

**Why this priority**: AIME 的核心价值，实现自主规划能力。

**Independent Test**: 发送"分析最近三个月的质量数据，找出良率最低的产线，并生成改善报告"，验证任务被正确分解。

**Acceptance Scenarios**:

1. **Given** 用户发送复杂分析请求, **When** Planner 分析, **Then** 生成包含多个子任务的执行计划
2. **Given** 执行计划包含依赖关系, **When** 执行子任务, **Then** 按依赖顺序执行（如先查询再分析）
3. **Given** 子任务执行完成, **When** Planner 收到结果, **Then** 可动态调整后续计划（如发现异常数据需要额外查询）

---

### User Story 5 - Real-time Progress Tracking (Priority: P2)

用户能够实时看到任务执行进度，包括各子任务的状态。

**Why this priority**: 提升用户体验，复用现有 SSE 机制。

**Independent Test**: 执行复杂任务时观察前端是否显示任务树和状态更新。

**Acceptance Scenarios**:

1. **Given** 复杂任务正在执行, **When** 子任务状态变化, **Then** 前端收到 `todos_updated` 事件
2. **Given** 子任务完成, **When** Progress Manager 更新状态, **Then** 任务列表显示 ✅ 完成状态
3. **Given** 所有子任务完成, **When** Planner 汇总结果, **Then** 生成最终回复

---

### User Story 6 - Dynamic Re-planning (Priority: P3)

当任务执行失败或结果不符合预期时，系统能够动态调整计划。

**Why this priority**: AIME 强调的动态适应能力，但初版可简化实现。

**Independent Test**: 模拟 Agent 执行失败，验证 Planner 尝试替代方案。

**Acceptance Scenarios**:

1. **Given** 子任务执行失败, **When** Planner 收到失败反馈, **Then** 尝试调整策略或创建替代任务
2. **Given** 重试 3 次失败, **When** 达到重试上限, **Then** 返回友好错误信息给用户

---

### Edge Cases

- 用户中途取消任务：Progress Manager 标记任务为取消状态，停止后续子任务
- 循环依赖检测：Planner 生成计划时验证无循环依赖
- Agent 执行超时：Dynamic Actor 设置超时机制（默认 60 秒）
- 并发任务限制：同一会话最多 3 个并行子任务，超限时阻塞等待空位，按 DAG 依赖顺序执行
- Re-planning 重试上限：单个子任务最多重试 3 次，超过后返回错误并停止该分支

---

## Architecture Design

### Current vs New Architecture

**现有架构** (替换前):
```
User Request → Supervisor (路由)
                   ├─ Direct Response
                   ├─ → Research Agent
                   ├─ → SQL Agent
                   └─ → General Agent (编排) → [Research, SQL, ...]
```

**AIME 架构** (替换后):
```
User Request → AIME Planner (意图识别 + 动态规划)
                   │
                   ├─ [简单] Direct Response
                   │
                   ├─ [专业] → Actor Factory → Dynamic Actor (Research/SQL)
                   │                              ↓
                   │                         Progress Manager
                   │
                   └─ [复杂] → Task Decomposition
                                   ├─ Subtask 1 → Actor Factory → Actor
                                   ├─ Subtask 2 → Actor Factory → Actor
                                   └─ ...
                                         ↓
                                    Progress Manager
```

### Agent Selection Strategy (专业 Agent 选择策略)

**核心问题**: 专业 Agent 的选择应该在哪一步进行？

**方案评估**:

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **1. Planner 统一选择** | Planner 完成意图识别+Agent选择 | 单一决策点，简单 | Planner 职责过重，难扩展 |
| **2. Factory 统一选择** | Planner 只分类，Factory 选择 Agent | 职责分离清晰 | 两步决策可能延迟 |
| **3. 混合方案** ⭐ | Planner 提供建议，Factory 最终决策 | 灵活、可扩展 | 实现稍复杂 |

**选择: 混合方案 (Planner Hint + Factory Decision)**

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    AIME Planner                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │            Intent Analysis                       │   │
│  │  - Action: direct_reply / delegate / plan / clarify │   │
│  │  - Capabilities: ["web_search", "database", ...]    │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Actor Factory                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Agent Selection (优先级顺序)             │   │
│  │  1. 用户显式指定 (explicit_agent) → 必须使用    │   │
│  │  2. 能力匹配 (capabilities) → 自动选择          │   │
│  │  3. 默认通用 Actor                              │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**选择优先级详解**:

| 优先级 | 来源 | 触发条件 | 示例 |
|--------|------|----------|------|
| **1. 显式指定** | 用户 | 前端选择 Agent 或 `[ROUTE_TO: xxx]` | 用户明确选择 Research Agent |
| **2. 能力匹配** | Factory | 基于 capabilities 匹配 Agent | `["web_search"]` → research |
| **3. 默认通用** | Factory | 无法匹配任何专业 Agent | 使用 Generic Actor |

**设计优势**:

1. **职责清晰**: Planner 只分析能力需求，不做 Agent 选择
2. **用户优先**: 用户显式指定时必须使用
3. **兜底机制**: 无法匹配时使用通用 Actor
4. **易于扩展**: 新增 Agent 只需注册能力映射

### Agent Registry Extension (支持自定义 Agent)

**问题**: 系统有两种 Agent 来源，Actor Factory 需要统一处理：
- **预设 Agent**（`backend/agents/`）：research, sql, generic
- **自定义 Agent**（`packages/`）：从 AGENTS.md 自动加载

**解决方案**: 扩展 `AgentEntry` 增加 `capabilities` 字段，所有 Agent 平等竞争。

#### AgentEntry 扩展

```python
# backend/registry.py

@dataclass
class AgentEntry:
    """A registered agent with its metadata."""
    name: str
    description: str
    graph: CompiledStateGraph
    tools: list = field(default_factory=list)
    icon: str = "bot"
    show_in_selector: bool = True
    # === 新增字段 ===
    capabilities: list[str] = field(default_factory=list)  # Agent 声明的能力
    source: Literal["preset", "package"] = "preset"        # 来源标识
```

#### 能力声明方式

**预设 Agent** (硬编码):
```python
# backend/agents/research.py
register_agent(
    name="research",
    description="Web research specialist",
    graph=agent,
    capabilities=["web_search", "news_search", "academic_search"],
    source="preset",
)
```

**自定义 Agent** (AGENTS.md frontmatter):
```yaml
# packages/data-analyst/AGENTS.md
---
name: data-analyst
description: Analyze data and generate insights
capabilities:
  - data_analysis
  - visualization
  - statistics
---
# Data Analyst Agent
...instructions...
```

#### Actor Factory 统一选择逻辑

```python
# backend/aime/actor_factory.py

class ActorFactory:
    def select_actor(self, spec: SubtaskSpec) -> Actor:
        # 优先级 1: 用户显式指定
        if spec.explicit_agent:
            return self._get_agent_or_error(spec.explicit_agent)

        # 优先级 2: 能力匹配（预设和自定义平等竞争）
        if spec.capabilities:
            matched = self._match_by_capabilities(spec.capabilities)
            if matched:
                return matched

        # 优先级 3: 默认 Generic Actor
        return self._create_generic_actor(spec)

    def _match_by_capabilities(self, required: list[str]) -> Actor | None:
        """基于能力匹配最合适的 Agent（预设和自定义平等竞争）"""
        candidates: list[tuple[AgentEntry, int]] = []

        for entry in AGENT_REGISTRY.values():
            if not entry.capabilities:
                continue
            # 计算匹配分数：匹配的能力数量
            score = len(set(required) & set(entry.capabilities))
            if score > 0:
                candidates.append((entry, score))

        if not candidates:
            return None

        # 按分数降序排序，分数相同时预设优先
        candidates.sort(key=lambda x: (x[1], x[0].source == "preset"), reverse=True)
        best_entry = candidates[0][0]
        return Actor(name=best_entry.name, graph=best_entry.graph, tools=best_entry.tools)
```

#### 选择优先级详解

| 优先级 | 条件 | 行为 |
|--------|------|------|
| **1. 显式指定** | `explicit_agent` 有值 | 直接使用，不存在则报错 |
| **2. 能力匹配** | `capabilities` 有值 | 遍历所有 Agent（含自定义），按匹配分数排序 |
| **2a. 分数相同** | 多个 Agent 分数相等 | 预设 Agent 优先（source="preset"） |
| **3. 兜底** | 无匹配 | 使用 Generic Actor |

#### Package Loader 更新

```python
# backend/agents/loader.py

def _register_package(pkg_dir: Path) -> None:
    """Create a deep agent from a package directory and register it."""
    agents_md = pkg_dir / "AGENTS.md"
    metadata = _parse_frontmatter(agents_md)  # 解析 YAML frontmatter

    register_agent(
        name=metadata.get("name", pkg_dir.name),
        description=metadata.get("description", ""),
        graph=agent,
        capabilities=metadata.get("capabilities", []),  # 新增
        source="package",  # 标识为自定义
        show_in_selector=False,
    )
```

### Skills Integration (Skills 与 Planner 集成)

**核心问题**: Skills 可以定义执行步骤，但 Skills 在 Agent 内执行；任务拆解在 Planner 内。执行步骤应在哪定义？

**解决方案**: 区分 **Atomic Skills** 和 **Workflow Skills**

#### Skills 分类

| 类型 | 定义 | 处理方式 | 示例 |
|------|------|----------|------|
| **Atomic Skill** | 单 Agent 内完成，无跨 Agent 调用 | Planner 创建单个 subtask，Agent 内部执行 | PDF 处理、代码格式化 |
| **Workflow Skill** | 包含多步骤，可能需要多 Agent 协作 | Planner 展开为多个 subtask | 研究报告生成、数据分析流程 |

#### Skills 加载机制（设计约束）

**原则**：Planner 和 Agent 使用同一套加载机制，Workflow 扩展信息按需注册。

**Registry 设计**：

```python
# 现有（保持不变）- 所有 Skills
SKILL_REGISTRY: dict[str, SkillEntry] = {}

# 新增 - 仅 Workflow Skills 的步骤信息
WORKFLOW_SKILLS: dict[str, WorkflowSkillInfo] = {}

@dataclass
class WorkflowSkillInfo:
    """Workflow Skill 的步骤定义（仅 Planner 使用）"""
    name: str
    steps: list[SkillStep]

@dataclass
class SkillStep:
    """Workflow Skill 的单个步骤"""
    id: str
    description: str
    required_capability: str | None = None
```

**加载逻辑**：

```python
# loader.py - 统一加载，分别注册
def load_skills_from_directory(skills_dir: Path) -> int:
    for skill_dir in skills_dir.iterdir():
        name, description, skill_type, steps = parse_skill_metadata(skill_md)

        # 所有 Skills 注册到 SKILL_REGISTRY（现有逻辑不变）
        entry = SkillEntry(name=name, description=description, path=skill_dir)
        register_skill(entry)

        # 仅 Workflow Skills 额外注册步骤信息
        if skill_type == "workflow" and steps:
            workflow_info = WorkflowSkillInfo(name=name, steps=steps)
            register_workflow_skill(workflow_info)
```

**使用方式对比**：

| 组件 | 使用的 Registry | 用途 |
|------|----------------|------|
| **Agent** | `SKILL_REGISTRY` | `activate_skill()` 获取 Instructions |
| **Planner** | `SKILL_REGISTRY` | Prompt 注入摘要 (`get_skill_summaries()`) |
| **Planner** | `WORKFLOW_SKILLS` | 判断是否展开为多个子任务 |
| **Actor Factory** | `SKILL_REGISTRY` | 加载 Instructions 注入 Actor |

**Planner 判断逻辑**：

```python
def _create_subtasks_for_skill(self, skill_name: str, user_request: str) -> list[SubtaskSpec]:
    workflow_info = WORKFLOW_SKILLS.get(skill_name)

    if workflow_info:
        # Workflow Skill: 展开为多个子任务
        return [
            SubtaskSpec(
                skill_name=skill_name,
                skill_step_id=step.id,
                description=step.description,
                capabilities=[step.required_capability] if step.required_capability else [],
            )
            for step in workflow_info.steps
        ]
    else:
        # Atomic Skill: 单个子任务
        return [SubtaskSpec(skill_name=skill_name, description=user_request)]
```

**设计优势**：
1. **最小改动**：现有 `SkillEntry` 和 Agent 代码不变
2. **按需扩展**：只有 Workflow Skills 才存储 steps 信息
3. **统一加载**：`loader.py` 一次加载，分别注册到两个 Registry
4. **职责清晰**：Agent 只需 Instructions，Planner 额外需要 steps

#### Skills 格式扩展（兼容 Anthropic 格式）

**现有 Anthropic Skills 格式**:
```yaml
---
name: skill-name
description: When to use this skill
---
# Instructions content (Markdown)
```

**扩展格式（向后兼容）**:

**Atomic Skill（默认，无需修改现有 Skills）**:
```yaml
---
name: pdf
description: Use this skill for PDF processing
# type: atomic  # 可选，默认值
---
# PDF Processing Instructions
...
```

**Workflow Skill（扩展）**:
```yaml
---
name: research-report
description: Create comprehensive research reports
type: workflow
steps:
  - id: search
    description: Search for relevant information
    required_capability: web_search
  - id: analyze
    description: Analyze and synthesize findings
    required_capability: analysis
  - id: generate
    description: Generate final report
    required_capability: generation
---
# Research Report Guidelines
## For each step, follow these instructions...
```

#### Skills 处理流程

```
User: "使用 research-report skill 生成AI趋势报告"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Planner                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  1. 识别 Skill 请求: "research-report"                                │  │
│  │                                                                       │  │
│  │  2. 加载 Skill 元信息:                                                │  │
│  │     ├─ type: workflow                                                 │  │
│  │     └─ steps: [search, analyze, generate]                             │  │
│  │                                                                       │  │
│  │  3. 展开为 SubtaskSpec[]:                                             │  │
│  │     ┌─────────────────────────────────────────────────────────────┐   │  │
│  │     │ SubtaskSpec[0]:                                             │   │  │
│  │     │   skill_name: "research-report"                             │   │  │
│  │     │   skill_step_id: "search"                                   │   │  │
│  │     │   description: "搜索AI趋势相关信息"                          │   │  │
│  │     │   capabilities: ["web_search"]                              │   │  │
│  │     └─────────────────────────────────────────────────────────────┘   │  │
│  │     ┌─────────────────────────────────────────────────────────────┐   │  │
│  │     │ SubtaskSpec[1]:                                             │   │  │
│  │     │   skill_name: "research-report"                             │   │  │
│  │     │   skill_step_id: "analyze"                                  │   │  │
│  │     │   description: "分析搜索结果，提炼关键趋势"                    │   │  │
│  │     │   capabilities: ["code_execution"]                          │   │  │
│  │     │   depends_on: ["0"]                                         │   │  │
│  │     └─────────────────────────────────────────────────────────────┘   │  │
│  │     ┌─────────────────────────────────────────────────────────────┐   │  │
│  │     │ SubtaskSpec[2]:                                             │   │  │
│  │     │   skill_name: "research-report"                             │   │  │
│  │     │   skill_step_id: "generate"                                 │   │  │
│  │     │   description: "生成最终研究报告"                            │   │  │
│  │     │   capabilities: ["document_generation"]                     │   │  │
│  │     │   depends_on: ["1"]                                         │   │  │
│  │     └─────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼ (每个 SubtaskSpec)
┌─────────────────────────────────────────────────────────────────────────────┐
│  Actor Factory                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  判断: if subtask.skill_name:  # Skill 任务                           │  │
│  │    1. 加载 Skill Instructions (SKILL.md 内容)                         │  │
│  │    2. 根据 capabilities 匹配 Agent                                    │  │
│  │    3. 将 Skill 指令注入 Actor prompt                                  │  │
│  │                                                                       │  │
│  │  示例 (step: search):                                                 │  │
│  │    selected_agent: "research"                                         │  │
│  │    injected_prompt: Skill Instructions + step context                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Dynamic Actor (Research Agent with Skill Instructions)                     │
│  执行搜索任务，返回结果给 Planner                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### SubtaskSpec 扩展

```python
@dataclass
class SubtaskSpec:
    """Planner 传递给 Factory 的子任务信息"""
    id: str
    description: str

    # Skill 相关（有值则为 Skill 任务，None 则为普通任务）
    skill_name: str | None = None
    skill_step_id: str | None = None  # Workflow Skill 的步骤 ID

    # Agent 选择
    explicit_agent: str | None = None  # 用户显式指定，有值则 Factory 必须使用
    capabilities: list[str] = field(default_factory=list)  # 所需能力，Factory 用于匹配

    # 依赖
    depends_on: list[str] = field(default_factory=list)
    context: dict | None = None
```

**判断逻辑**：
```python
if subtask.skill_name:
    # Skill 任务：加载 Skill Instructions，注入 Actor prompt
else:
    # 普通任务：直接执行
```

#### 兼容性分析

| 特性 | Anthropic 格式 | 扩展格式 | 兼容性 |
|------|---------------|----------|--------|
| YAML frontmatter | ✅ `name`, `description` | ✅ 保留 | 100% |
| Markdown 指令 | ✅ `# Instructions` | ✅ 保留 | 100% |
| `type` 字段 (SKILL.md) | ❌ 无 | ✅ 新增，默认 `atomic` | 向后兼容 |
| `steps` 字段 (SKILL.md) | ❌ 无 | ✅ 新增，仅 workflow | 向后兼容 |

**兼容性保证**:
- 现有 Atomic Skills 无需任何修改
- SKILL.md 中 `type` 缺失时默认为 `atomic`，按现有逻辑处理
- Workflow Skills 是可选扩展，不影响现有功能
- SubtaskSpec 通过 `skill_name` 是否有值区分任务类型，无需额外字段

### Component Design

#### 0. Intent Analyzer Module (意图识别模块) ⭐ 独立封装

**设计目标**: 将意图识别封装为独立模块，支持可插拔的分类器和领域识别器。

**模块结构**:
```
backend/aime/intent/
├── __init__.py          # 导出 IntentAnalyzer, IntentResult
├── analyzer.py          # 核心分析器（组合多个分类器）
├── models.py            # IntentResult 数据类、Action 类型
├── classifiers/         # 分类器（可插拔）
│   ├── base.py          # ClassifierBase 抽象基类
│   ├── rule_based.py    # 规则匹配（显式路由检测）
│   ├── keyword_based.py # 关键词匹配（快速分类）
│   └── llm_based.py     # LLM 深度分析（复杂意图）
└── domain/              # 领域识别器（可选扩展）
    ├── base.py          # DomainRecognizer 基类
    ├── manufacturing.py # 制造业术语 (CPK, FMEA, SPC...)
    └── quality.py       # 质量管理术语 (8D, PDCA, 客诉...)
```

**IntentResult 设计（简化版）**:

```
IntentResult (意图分析结果)
│
├── action                        # 核心决策 - Planner 下一步行为
│   ├── direct_reply              # 直接回复 (简单问候、知识问答)
│   ├── delegate                  # 委派给专业 Agent (单任务路由)
│   ├── plan                      # 自主规划 (复杂任务分解)
│   └── clarify                   # 澄清追问 (意图不清晰)
│
├── confidence                    # 置信度 (0.0-1.0)
│
├── capabilities                  # 所需能力 (Factory 用于匹配 Agent)
│   └── ["web_search", "database", "code_execution", ...]
│
├── domain                        # 领域 (预留扩展)
│   └── "general" | "manufacturing" | "quality" | "hr" | "it"
│
└── clarify_questions             # 追问问题 (clarify 时使用)
    └── ["需要分析什么数据？", "输出什么格式？"]
```

**核心接口**:
```python
# backend/aime/intent/config.py

from typing import Literal
from dataclasses import dataclass, field

# Action 类型 - 直接决定 Planner 行为
Action = Literal["direct_reply", "delegate", "plan", "clarify"]

# 能力到 Agent 的映射
# 注意：这只是 IntentAnalyzer 的快速参考，实际匹配由 Actor Factory 从 AGENT_REGISTRY 动态计算
# Actor Factory 会遍历所有注册的 Agent（包括自定义），基于 capabilities 字段进行匹配
CAPABILITY_AGENT_MAP = {
    "web_search": "research",
    "database": "sql",
    "code_execution": "generic",
    "file_processing": "generic",
    "document_generation": "generic",
    "knowledge_base": "knowledge",  # 未来扩展
}


# backend/aime/intent/analyzer.py

@dataclass
class IntentResult:
    """意图分析结果"""

    # ===== 核心决策 =====
    action: Action                               # Planner 下一步行为
    confidence: float = 0.0                      # 置信度

    # ===== 路由信息 (delegate/plan 时使用) =====
    capabilities: list[str] = field(default_factory=list)  # 所需能力，Factory 用于匹配
    domain: str = "general"                      # 领域 (预留扩展)

    # ===== 澄清信息 (clarify 时使用) =====
    clarify_questions: list[str] | None = None   # 追问问题列表
```

**Action 与场景映射**:

| Action | 场景 | 说明 | 示例 |
|--------|------|------|------|
| `direct_reply` | 直接回复 | 简单问题，无需工具 | "你好"、"1+1=?" |
| `delegate` | 委派 Agent | 单任务，路由到专业 Agent | "搜索 AI 新闻" → research |
| `plan` | 自主规划 | 复杂任务，分解为多步骤 | "分析数据并生成报告" |
| `clarify` | 澄清追问 | 意图不清晰，需要更多信息 | "帮我分析一下" |

**数据流 (Intent → Planner → Factory)**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  User Message: "分析最近三个月的质量数据，找出良率最低的产线，并生成报告"      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  IntentAnalyzer.analyze()                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  IntentResult:                                                        │  │
│  │    action: "plan"                                                     │  │
│  │    confidence: 0.92                                                   │  │
│  │    capabilities: ["database", "code_execution", "document_generation"]│  │
│  │    domain: "quality"                                                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Planner.process()                                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Decision: action == "plan" → 任务分解                                 │  │
│  │                                                                       │  │
│  │  Generated Subtasks:                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ SubtaskSpec[0]:                                                 │  │  │
│  │  │   description: "查询最近三个月的质量数据"                         │  │  │
│  │  │   capabilities: ["database"]                                    │  │  │
│  │  │   depends_on: []                                                │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ SubtaskSpec[1]:                                                 │  │  │
│  │  │   description: "分析数据，找出良率最低的产线"                      │  │  │
│  │  │   capabilities: ["code_execution"]                              │  │  │
│  │  │   depends_on: [0]                                               │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ SubtaskSpec[2]:                                                 │  │  │
│  │  │   description: "生成质量改善报告"                                 │  │  │
│  │  │   capabilities: ["document_generation"]                         │  │  │
│  │  │   depends_on: [1]                                               │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ (每个 SubtaskSpec)
┌─────────────────────────────────────────────────────────────────────────────┐
│  ActorFactory.select_actor(subtask_spec)                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Selection Priority:                                                  │  │
│  │  1. explicit_agent: None ❌                                           │  │
│  │  2. capability matching: ["database"] → "sql" ✓                      │  │
│  │                                                                       │  │
│  │  Result: Actor(name="sql", graph=SQL_AGENT_GRAPH, tools=[...])       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

class IntentAnalyzer:
    """
    意图分析器 - 组合多个分类器，按优先级执行

    分类器执行顺序:
    1. RuleBasedClassifier: 检测显式路由 [ROUTE_TO: xxx]
    2. KeywordClassifier: 快速关键词匹配
    3. LLMClassifier: 深度语义分析 (仅当前两步不确定时)
    """

    def __init__(
        self,
        classifiers: list[ClassifierBase] | None = None,
        domain_recognizers: list[DomainRecognizer] | None = None,
    ):
        self.classifiers = classifiers or [
            RuleBasedClassifier(),
            KeywordClassifier(),
            LLMClassifier(),
        ]
        self.domain_recognizers = domain_recognizers or []

    async def analyze(
        self,
        message: str,
        context: dict | None = None,
    ) -> IntentResult:
        """
        分析用户意图

        Args:
            message: 用户消息
            context: 上下文（历史消息、用户画像等）

        Returns:
            IntentResult: 意图分析结果
        """
        # 1. 领域识别（丰富上下文）
        domain = self._recognize_domain(message)

        # 2. 按优先级执行分类器
        for classifier in self.classifiers:
            result = await classifier.classify(message, context, domain)
            if result.confidence >= classifier.confidence_threshold:
                return result

        # 3. 置信度 < 0.5 时触发追问，否则默认 plan
        if result.confidence < 0.5:
            return IntentResult(action="clarify", confidence=result.confidence, domain=domain or "general")
        return IntentResult(action="plan", confidence=0.5, domain=domain or "general")

    def _recognize_domain(self, message: str) -> str | None:
        """识别消息所属领域"""
        for recognizer in self.domain_recognizers:
            if domain := recognizer.recognize(message):
                return domain
        return None
```

**分类器基类**:
```python
# backend/aime/intent/classifiers/base.py

from abc import ABC, abstractmethod

class ClassifierBase(ABC):
    """分类器基类 - 可插拔设计"""

    confidence_threshold: float = 0.7  # 置信度阈值

    @abstractmethod
    async def classify(
        self,
        message: str,
        context: dict | None,
        domain: str | None,
    ) -> IntentResult:
        """执行分类"""
        pass
```

**规则分类器示例**:
```python
# backend/aime/intent/classifiers/rule_based.py

class RuleBasedClassifier(ClassifierBase):
    """规则匹配分类器 - 处理显式路由"""

    confidence_threshold: float = 1.0  # 规则匹配 100% 置信

    async def classify(self, message: str, context: dict | None, domain: str | None) -> IntentResult:
        # 检测显式路由: [ROUTE_TO: agent_name]
        # 注意：显式路由通过 explicit_agent 传递，不在 IntentResult 中
        match = re.search(r'\[ROUTE_TO:\s*(\w+)\]', message)
        if match:
            # 返回 delegate，explicit_agent 由 Planner 单独处理
            return IntentResult(
                action="delegate",
                confidence=1.0,
            )

        # 检测 Skill 请求: [SKILL: skill_name]
        if message.startswith("[SKILL:"):
            return IntentResult(
                action="delegate",
                confidence=1.0,
            )

        # 未匹配规则，返回低置信度（让下一个分类器处理）
        return IntentResult(action="direct_reply", confidence=0.0)
```

**扩展性设计**:

| 扩展场景 | 实现方式 |
|----------|----------|
| 新增分类器 | 实现 `ClassifierBase`，添加到 `classifiers` 列表 |
| 新增领域 | 在 domain 字段使用新的领域标识 |
| 新增能力 | 在 capabilities 列表添加新能力字符串 |
| 切换到 ML 模型 | 实现 `MLClassifier`，替换 `LLMClassifier` |
| 用户画像集成 | 在 `context` 中传入用户偏好，分类器读取 |

---

#### 1. AIME Planner (替换 Supervisor + General Agent)

**职责**:
- 意图识别：判断简单/专业/复杂任务
- 任务分解：复杂任务拆解为子任务 DAG
- 动态调整：根据执行反馈修改计划
- 结果汇总：整合子任务结果生成最终回复

**核心公式** (来自论文):
```
(L_{t+1}, g_{t+1}) = LLM_planner(P_planner, (G, L_t, H_t))

其中:
- L_t: 当前任务列表 (Progress List)
- g_t: 下一步具体操作 (dispatch subtask / respond directly)
- H_t: 历史执行结果
```

**实现要点**:
```python
# backend/aime/planner.py

@dataclass
class AIMEPlanner:
    """
    AIME Dynamic Planner - 替换 Supervisor + General Agent

    决策逻辑:
    1. direct_reply: 简单任务 → 直接回复
    2. delegate: 专业任务 → 创建单个子任务，Factory 匹配 Agent
    3. plan: 复杂任务 → 分解为子任务 DAG
    4. clarify: 意图不清 → 追问澄清
    """

    def __init__(self, intent_analyzer: IntentAnalyzer | None = None):
        # 使用独立的意图分析模块
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.actor_factory = ActorFactory()
        self.progress_manager = ProgressManager()

    async def process(
        self,
        message: str,
        context: dict,
        explicit_agent: str | None = None  # 用户显式指定
    ) -> AsyncIterator[Event]:

        # Step 1: 检查用户显式指定
        if explicit_agent:
            # 跳过意图识别，直接创建子任务
            subtask = SubtaskSpec(
                description=message,
                explicit_agent=explicit_agent,
            )
            yield TodosUpdated([subtask])
            async for event in self._execute_subtask(subtask):
                yield event
            return

        # Step 2: Intent Analysis
        intent = await self._analyze_intent(message, context)

        match intent.action:
            case "direct_reply":
                # 直接回复，无子任务
                async for token in self._generate_direct_response(message):
                    yield StreamToken(token)

            case "delegate":
                # 委派给专业 Agent，创建单个子任务
                subtask = SubtaskSpec(
                    description=message,
                    capabilities=intent.capabilities,  # Factory 用于匹配 Agent
                )
                yield TodosUpdated([subtask])
                async for event in self._execute_subtask(subtask):
                    yield event

            case "plan":
                # 自主规划，分解为多个子任务
                plan = await self._decompose_task(message, context, intent)
                yield TodosUpdated(plan.tasks)
                async for event in self._execute_plan(plan):
                    yield event

            case "clarify":
                # 意图不清晰，返回追问
                yield ClarifyRequest(questions=intent.clarify_questions)

    async def _analyze_intent(self, message: str, context: dict) -> IntentResult:
        """
        意图分析 - 委托给独立的 IntentAnalyzer 模块

        IntentAnalyzer 会按优先级执行分类器:
        1. RuleBasedClassifier: 检测显式路由
        2. KeywordClassifier: 快速关键词匹配
        3. LLMClassifier: 深度语义分析
        """
        return await self.intent_analyzer.analyze(message, context)
```

#### 2. Actor Factory (新增模块)

**职责**:
- 根据选择优先级确定最合适的 Actor
- 复用注册的专业 Agent (Research, SQL, etc.)
- 支持动态创建 Actor (未来扩展)

**实现要点**:
```python
# backend/aime/actor_factory.py

@dataclass
class SubtaskSpec:
    """子任务规格 - Planner 传递给 Factory 的信息"""
    description: str
    explicit_agent: str | None = None    # 用户显式指定，有值则必须使用
    capabilities: list[str] = field(default_factory=list)  # 所需能力

class ActorFactory:
    """
    Actor Factory - 按需选择/创建 Actor

    选择优先级:
    1. 用户显式指定 (explicit_agent) → 必须使用
    2. 能力匹配 (capabilities) → 自动选择
    3. 默认通用 Actor
    """

    def select_actor(self, spec: SubtaskSpec) -> Actor:
        """根据优先级选择 Actor"""

        # 优先级 1: 用户显式指定
        if spec.explicit_agent:
            agent = self._get_registered_agent(spec.explicit_agent)
            if agent:
                return agent
            raise AgentNotFoundError(
                f"Agent '{spec.explicit_agent}' not found. "
                f"Available: {list(AGENT_REGISTRY.keys())}"
            )

        # 优先级 2: 基于 capabilities 匹配
        if spec.capabilities:
            matched_agent = self._match_by_capabilities(spec.capabilities)
            if matched_agent:
                return matched_agent

        # 优先级 3: 默认通用 Actor
        return self._create_generic_actor(spec)

    def _match_by_capabilities(self, capabilities: list[str]) -> Actor | None:
        """基于 capabilities 匹配最合适的 Agent"""
        for cap in capabilities:
            agent_name = CAPABILITY_AGENT_MAP.get(cap)
            if agent_name:
                agent = self._get_registered_agent(agent_name)
                if agent:
                    return agent
        return None
```

#### 3. Progress Manager (使用现有 SSE)

**职责**:
- 维护全局任务列表 (Progress List)
- 跟踪子任务状态
- 通过现有 `todos_updated` SSE 事件推送更新

**数据结构** (兼容现有 SSE):
```python
# 复用现有 todos_updated 事件格式
@dataclass
class ProgressList:
    """全局任务列表 - AIME 的 Single Source of Truth"""

    tasks: list[TaskItem]

    @dataclass
    class TaskItem:
        id: str
        description: str
        status: Literal["pending", "running", "completed", "failed"]
        agent: str | None  # 执行该任务的 Agent
        result: str | None
        subtasks: list["TaskItem"] | None  # 支持层级
```

**SSE 事件格式** (保持不变):
```json
{
  "event": "todos_updated",
  "data": {
    "todos": [
      {"id": "1", "task": "搜索最新AI新闻", "status": "running", "agent": "research"},
      {"id": "2", "task": "分析搜索结果", "status": "pending", "agent": null}
    ]
  }
}
```

---

## Response Modes & SSE Events Mapping (四种答复模式与 SSE 映射)

### 概述

AIME 架构定义了四种答复模式 (`action`)，每种模式产生不同的 SSE 事件序列，前端根据事件动态切换 `displayScenario` 并渲染对应的 UI 组件。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Response Mode → SSE → UI 映射                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────────────┐   │
│  │ Action Type │ ──→ │   SSE Events    │ ──→ │    Display Scenario     │   │
│  │ (Backend)   │     │   (Stream)      │     │    → UI Components      │   │
│  └─────────────┘     └─────────────────┘     └─────────────────────────┘   │
│                                                                             │
│  direct_reply ──→ text_delta ──────────→ "quick" → MessageContent          │
│                                                                             │
│  delegate ────→ thinking(routing)                                          │
│               → task_spawned ──────────→ "agent" → ThinkingBubble          │
│               → tool_call_*                      → TaskList (SpawnedTask)  │
│               → task_completed                   → MessageContent          │
│               → text_delta                                                 │
│                                                                             │
│  plan ────────→ thinking(planning)                                         │
│               → todos_updated ─────────→ "planning" → ThinkingBubble       │
│               → task_spawned                        → TaskList (Todos +    │
│               → tool_call_*                              SpawnedTasks)     │
│               → task_completed                      → MessageContent       │
│               → todos_updated                                              │
│               → text_delta                                                 │
│                                                                             │
│  clarify ─────→ text_delta ────────────→ "quick" → MessageContent          │
│                                                   (clarifying questions)   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mode 1: direct_reply (直接回复)

**触发条件**: 简单问答、无需工具调用

**Backend 流程**:
```
User: "你好"
    │
    ▼
Planner.analyze() → IntentResult(action="direct_reply")
    │
    ▼
Planner._generate_direct_response() → 直接生成文本
    │
    ▼
Stream: text_delta → done
```

**SSE 事件序列**:
```
event: text_delta    data: {"text": "你好！"}
event: text_delta    data: {"text": "有什么可以帮助你的吗？"}
event: done          data: {}
```

**Display Scenario**: `quick` (默认，无 thinking/task 事件)

**UI 组件渲染**:
```
┌─────────────────────────────────────────┐
│ MessageBubble                           │
│ ┌─────────────────────────────────────┐ │
│ │ Layer 3: MessageContent             │ │
│ │ "你好！有什么可以帮助你的吗？"        │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

### Mode 2: delegate (委派单任务)

**触发条件**: 单专业任务，路由到专业 Agent

**Backend 流程**:
```
User: "搜索最新的AI新闻"
    │
    ▼
Planner.analyze() → IntentResult(action="delegate", capabilities=["web_search"])
    │
    ▼
Planner._create_subtask() → SubtaskSpec(capabilities=["web_search"])
    │
    ▼
ActorFactory.select_actor() → Research Agent
    │
    ▼
Stream: thinking(routing) → task_spawned → tool_call_* → task_completed → text_delta → done
```

**SSE 事件序列**:
```
event: thinking      data: {"content": "Routing to research: 搜索AI新闻", "type": "routing"}
event: task_spawned  data: {"task_id": "tc-123", "subagent_type": "research", "description": "搜索最新AI新闻"}
event: tool_call_start   data: {"id": "tool-1", "name": "tavily_search", "args": {"query": "AI news 2026"}, "task_id": "tc-123"}
event: tool_call_result  data: {"id": "tool-1", "status": "success", "output": "...", "task_id": "tc-123"}
event: task_completed    data: {"task_id": "tc-123", "status": "success", "duration_ms": 2500}
event: text_delta    data: {"text": "根据搜索结果，最新的AI新闻包括..."}
event: done          data: {}
```

**Display Scenario**: `agent` (收到 thinking 或 task_spawned 时升级)

**UI 组件渲染**:
```
┌───────────────────────────────────────────────────────────────┐
│ MessageBubble                                                 │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Layer 1: ThinkingBubble                                   │ │
│ │ 🧠 思考中... 3秒                                          │ │
│ │ └─ "Routing to research: 搜索AI新闻"                      │ │
│ └───────────────────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Layer 2: TaskList (SpawnedTasks)                          │ │
│ │ ┌─────────────────────────────────────────────────────┐   │ │
│ │ │ ▸ ⏳ research: 搜索最新AI新闻               2.5s    │   │ │
│ │ │   ├─ ✓ tavily_search: "AI news 2026"               │   │ │
│ │ └─────────────────────────────────────────────────────┘   │ │
│ └───────────────────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Layer 3: MessageContent                                   │ │
│ │ 根据搜索结果，最新的AI新闻包括...                          │ │
│ └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

---

### Mode 3: plan (自主规划)

**触发条件**: 复杂多步骤任务，需要任务分解

**Backend 流程**:
```
User: "分析最近三个月的质量数据，找出良率最低的产线，并生成报告"
    │
    ▼
Planner.analyze() → IntentResult(action="plan", capabilities=["database", "code_execution", "document_generation"])
    │
    ▼
Planner._decompose_task() → ExecutionPlan(subtasks=[...])
    │
    ▼
ProgressManager.update() → todos_updated (initial plan)
    │
    ▼
For each subtask:
  ├─ ActorFactory.select_actor()
  ├─ task_spawned
  ├─ Execute → tool_call_*
  ├─ task_completed
  └─ todos_updated (status update)
    │
    ▼
Planner._synthesize_results() → text_delta → done
```

**SSE 事件序列**:
```
event: thinking      data: {"content": "分析任务复杂度，规划执行步骤...", "type": "planning"}
event: todos_updated data: {"todos": [
  {"content": "查询最近三个月的质量数据", "status": "pending"},
  {"content": "分析数据，找出良率最低的产线", "status": "pending"},
  {"content": "生成质量改善报告", "status": "pending"}
]}
event: todos_updated data: {"todos": [
  {"content": "查询最近三个月的质量数据", "status": "in_progress"},
  ...
]}
event: task_spawned  data: {"task_id": "tc-1", "subagent_type": "sql", "description": "查询质量数据"}
event: tool_call_start   data: {"id": "tool-1", "name": "sql_query", "args": {...}, "task_id": "tc-1"}
event: tool_call_result  data: {"id": "tool-1", "status": "success", "output": "...", "task_id": "tc-1"}
event: task_completed    data: {"task_id": "tc-1", "status": "success", "duration_ms": 1500}
event: todos_updated data: {"todos": [
  {"content": "查询最近三个月的质量数据", "status": "completed"},
  {"content": "分析数据，找出良率最低的产线", "status": "in_progress"},
  ...
]}
... (subsequent subtasks)
event: text_delta    data: {"text": "## 质量分析报告\n\n根据分析..."}
event: done          data: {}
```

**Display Scenario**: `planning` (收到 todos_updated 时升级)

**UI 组件渲染**:
```
┌───────────────────────────────────────────────────────────────────┐
│ MessageBubble                                                     │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ Layer 1: ThinkingBubble                                       │ │
│ │ 🧠 思考中... 15秒                                             │ │
│ │ └─ "分析任务复杂度，规划执行步骤..."                            │ │
│ └───────────────────────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ Layer 2: TaskList                                             │ │
│ │ ┌─────────────────────────────────────────────────────────┐   │ │
│ │ │ Todos (Progress List):                                  │   │ │
│ │ │  ✅ 查询最近三个月的质量数据                             │   │ │
│ │ │  ⏳ 分析数据，找出良率最低的产线                         │   │ │
│ │ │  ○  生成质量改善报告                                    │   │ │
│ │ └─────────────────────────────────────────────────────────┘   │ │
│ │ ┌─────────────────────────────────────────────────────────┐   │ │
│ │ │ SpawnedTasks:                                           │   │ │
│ │ │ ▸ ✅ sql: 查询质量数据                          1.5s    │   │ │
│ │ │   └─ ✓ sql_query: SELECT * FROM quality_data...        │   │ │
│ │ │ ▸ ⏳ generic: 分析数据                                  │   │ │
│ │ │   └─ ⟳ execute_python: analyzing...                    │   │ │
│ │ └─────────────────────────────────────────────────────────┘   │ │
│ └───────────────────────────────────────────────────────────────┘ │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ Layer 3: MessageContent                                       │ │
│ │ ## 质量分析报告                                               │ │
│ │ 根据分析，产线C的良率最低...                                   │ │
│ └───────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

---

### Mode 4: clarify (澄清追问)

**触发条件**: 意图不清晰，需要更多信息

**Backend 流程**:
```
User: "帮我分析一下"
    │
    ▼
Planner.analyze() → IntentResult(action="clarify", clarify_questions=["需要分析什么数据？", "输出什么格式？"])
    │
    ▼
Stream: text_delta (clarifying questions) → done
```

**SSE 事件序列**:
```
event: text_delta    data: {"text": "您的请求不够具体，请补充以下信息：\n\n"}
event: text_delta    data: {"text": "1. 需要分析什么数据？\n"}
event: text_delta    data: {"text": "2. 期望输出什么格式？\n"}
event: done          data: {}
```

**Display Scenario**: `quick`

**UI 组件渲染**:
```
┌─────────────────────────────────────────┐
│ MessageBubble                           │
│ ┌─────────────────────────────────────┐ │
│ │ Layer 3: MessageContent             │ │
│ │ 您的请求不够具体，请补充以下信息：     │ │
│ │                                     │ │
│ │ 1. 需要分析什么数据？                │ │
│ │ 2. 期望输出什么格式？                │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

### SSE 事件与 UI 组件映射表

| SSE 事件 | 数据字段 | 触发 Scenario 变化 | UI 组件更新 |
|----------|----------|-------------------|-------------|
| `text_delta` | `text` | - | MessageContent 追加文本 |
| `thinking` | `content`, `type?` | `quick` → `agent`; `type=planning` → `planning` | ThinkingBubble 添加步骤 |
| `todos_updated` | `todos[]` | → `planning` | TaskList 更新 Todos |
| `task_spawned` | `task_id`, `subagent_type`, `description` | `quick` → `agent` | TaskList 添加 SpawnedTask |
| `task_completed` | `task_id`, `status`, `duration_ms` | - | SpawnedTask 更新状态 |
| `tool_call_start` | `id`, `name`, `args`, `task_id?` | - | ToolCallCard 添加 (running) |
| `tool_call_result` | `id`, `status`, `output`, `task_id?` | - | ToolCallCard 更新状态 |
| `error` | `message` | - | MessageContent 追加错误 |
| `done` | - | - | ThinkingBubble 收起 |

### Display Scenario 状态转换

```
初始状态: "agent" (显示 ThinkingBubble)
         │
         ▼
    ┌────────────────────────────────────────┐
    │           接收 SSE 事件                 │
    │                                        │
    │  thinking(routing) ─────────→ "agent"  │
    │  thinking(planning) ────────→ "planning│
    │  todos_updated ─────────────→ "planning│
    │  task_spawned ──────────────→ "agent"  │
    │  (保持 planning 如果已是 planning)      │
    │                                        │
    │  done ──────────────────────→ 保持当前  │
    │  (不再降级到 quick，保留完整 UI)        │
    └────────────────────────────────────────┘
```

### 关键设计决策

1. **初始 Scenario = "agent"**: 为立即显示 ThinkingBubble，消息创建时默认使用 `agent` scenario
2. **只升级不降级**: `done` 事件不会将 scenario 降级回 `quick`，保留完整的任务树
3. **task_id 关联**: `tool_call_start/result` 携带 `task_id` 时，工具调用嵌套在对应 SpawnedTask 下
4. **Todos vs SpawnedTasks**: Todos 是计划列表（checkbox 样式），SpawnedTasks 是执行任务（可展开查看工具调用）

---

## Requirements *(mandatory)*

### Functional Requirements

**意图识别模块** (独立封装):
- **FR-001**: IntentAnalyzer MUST 作为独立模块，支持可插拔的分类器
- **FR-002**: IntentAnalyzer MUST 按优先级执行分类器: 规则 → 关键词 → LLM
- **FR-003**: IntentResult.action MUST 为四种之一: direct_reply / delegate / plan / clarify
- **FR-004**: action=clarify 时 MUST 返回 clarify_questions 列表

**任务分类与执行**:
- **FR-005**: AIME Planner MUST 使用 IntentAnalyzer 进行意图分析
- **FR-006**: 简单任务 MUST 直接回复，响应延迟 < 2秒
- **FR-007**: 专业任务 MUST 创建子任务并路由到对应 Agent
- **FR-008**: 复杂任务 MUST 分解为子任务 DAG

**Agent 选择优先级** (核心):
- **FR-009**: 用户显式指定 Agent 时 (`explicit_agent`) MUST 优先使用，跳过意图识别
- **FR-010**: IntentResult MUST 包含 `capabilities` 列表，用于 Factory 匹配 Agent
- **FR-011**: Actor Factory MUST 按优先级选择: 显式指定 > 能力匹配 > 默认通用
- **FR-012**: Actor Factory MUST 能校验建议是否合理，不合理时可覆盖
- **FR-013**: 用户指定的 Agent 不存在时 MUST 返回错误信息和可用 Agent 列表

**任务执行与进度管理**:
- **FR-014**: 每个专业 Agent 调用 MUST 作为 Progress List 中的子任务
- **FR-015**: Progress Manager MUST 通过 `todos_updated` SSE 事件推送状态更新
- **FR-016**: Planner MUST 能根据子任务结果动态调整后续计划

**Skills 集成**:
- **FR-017**: Planner 和 Agent MUST 使用同一套 Skills 加载机制 (`SKILL_REGISTRY`)
- **FR-018**: Workflow Skills MUST 额外注册到 `WORKFLOW_SKILLS`（仅存储 steps 信息）
- **FR-019**: Planner MUST 通过 `WORKFLOW_SKILLS.get(skill_name)` 判断是否需要展开
- **FR-020**: Atomic Skills MUST 作为单个子任务执行，由 Actor 内部处理
- **FR-021**: Workflow Skills MUST 被 Planner 展开为多个子任务 (SubtaskSpec[])
- **FR-022**: SubtaskSpec MUST 通过 `skill_name` 字段区分 Skill 任务（有值）和普通任务（None）
- **FR-023**: Actor Factory MUST 在 `skill_name` 有值时从 `SKILL_REGISTRY` 加载并注入 Instructions
- **FR-024**: Skills 格式扩展 MUST 向后兼容现有 Anthropic Skills（`type` 缺失时默认 `atomic`）

**兼容性**:
- **FR-025**: Actor Factory MUST 复用 AGENT_REGISTRY 中已注册的 Agent
- **FR-026**: 系统 MUST 保持与现有前端 SSE 显示方式的兼容性
- **FR-027**: 系统 MUST 保持与现有 Registry 机制的兼容性
- **FR-028**: 现有 SkillEntry 结构 MUST 保持不变，Agent 使用方式不变

**Agent Registry 扩展** (支持自定义 Agent):
- **FR-039**: AgentEntry MUST 扩展 `capabilities` 字段，声明 Agent 具备的能力列表
- **FR-040**: AgentEntry MUST 扩展 `source` 字段，区分 `preset`（预设）和 `package`（自定义）
- **FR-041**: 自定义 Agent MUST 通过 AGENTS.md frontmatter 声明 capabilities
- **FR-042**: Actor Factory 能力匹配 MUST 同时考虑预设和自定义 Agent（平等竞争）
- **FR-043**: 能力匹配分数相同时，MUST 优先选择预设 Agent（source="preset"）
- **FR-044**: Package Loader MUST 解析 AGENTS.md frontmatter 并提取 capabilities 注册到 Registry

**SSE 事件与 UI 渲染** (Response Modes):
- **FR-029**: `direct_reply` 模式 MUST 只产生 `text_delta` + `done` 事件序列
- **FR-030**: `delegate` 模式 MUST 产生 `thinking(routing)` → `task_spawned` → `tool_call_*` → `task_completed` → `text_delta` 事件序列
- **FR-031**: `plan` 模式 MUST 产生 `thinking(planning)` → `todos_updated` → (subtask events) → `text_delta` 事件序列
- **FR-032**: `clarify` 模式 MUST 只产生 `text_delta` + `done` 事件序列（澄清问题）
- **FR-033**: `thinking` 事件 MUST 包含 `type` 字段 (`routing` | `planning` | `replanning`)
- **FR-034**: `todos_updated` 事件 MUST 触发前端 displayScenario 升级到 `planning`
- **FR-035**: `task_spawned` 事件 MUST 触发前端 displayScenario 升级到 `agent`（如未达到 `planning`）
- **FR-036**: `tool_call_start/result` 事件 MUST 携带 `task_id` 字段以关联到 SpawnedTask
- **FR-037**: 前端 MUST 根据 `task_id` 将工具调用嵌套渲染在对应 SpawnedTask 下
- **FR-038**: `done` 事件 MUST NOT 触发 displayScenario 降级（保留完整任务树）

### Non-Functional Requirements

- **NFR-001**: 任务规划延迟 < 3秒
- **NFR-002**: 支持至少 5 个并发会话
- **NFR-003**: 子任务超时默认 60 秒

### Key Entities

**意图分析相关**:
```python
# Action 类型
Action = Literal["direct_reply", "delegate", "plan", "clarify"]

@dataclass
class IntentResult:
    """意图分析结果"""
    # 核心决策
    action: Action                               # Planner 下一步行为
    confidence: float = 0.0                      # 置信度
    # 路由信息
    capabilities: list[str] = field(default_factory=list)  # 所需能力，Factory 用于匹配
    domain: str = "general"                      # 领域 (预留扩展)
    # 澄清信息
    clarify_questions: list[str] | None = None   # 追问问题列表
```

**子任务规格**:
```python
@dataclass
class SubtaskSpec:
    """Planner 传递给 Factory 的子任务信息"""
    id: str                          # 任务 ID
    description: str                 # 任务描述

    # Skill 相关（有值则为 Skill 任务，None 则为普通任务）
    skill_name: str | None = None    # Skill 名称
    skill_step_id: str | None = None # Workflow Skill 步骤 ID

    # Agent 选择
    explicit_agent: str | None = None  # 用户显式指定，有值则 Factory 必须使用
    capabilities: list[str] = field(default_factory=list)  # 所需能力，Factory 用于匹配

    # 依赖关系
    depends_on: list[str]            # 依赖的任务 ID
    context: dict | None             # 上下文 (前置任务结果)
```

**执行计划**:
```python
@dataclass
class ExecutionPlan:
    """Planner 生成的执行计划"""
    goal: str                        # 原始用户目标
    subtasks: list[SubtaskSpec]      # 子任务列表 (拓扑排序)
    dag: dict[str, list[str]]        # 依赖关系图 {task_id: [dependent_ids]}
```

**进度管理**:
```python
@dataclass
class TaskProgress:
    """单个任务的进度"""
    id: str
    description: str
    status: Literal["pending", "running", "completed", "failed"]
    agent: str | None                # 执行的 Agent
    result: str | None               # 执行结果
    error: str | None                # 错误信息

@dataclass
class ProgressList:
    """全局任务列表 - AIME 的 Single Source of Truth"""
    tasks: list[TaskProgress]
```

**Actor 定义**:
```python
@dataclass
class Actor:
    """执行子任务的 Agent 实例"""
    name: str                        # Actor 名称
    graph: CompiledStateGraph        # LangGraph 图
    tools: list                      # 工具列表
    persona: str | None              # 角色设定 (可选)
```

**Skills 相关（Workflow 扩展）**:
```python
@dataclass
class SkillStep:
    """Workflow Skill 的单个步骤"""
    id: str                          # 步骤 ID
    description: str                 # 步骤描述
    required_capability: str | None = None  # 所需能力

@dataclass
class WorkflowSkillInfo:
    """Workflow Skill 的步骤定义（仅 Planner 使用）"""
    name: str                        # Skill 名称
    steps: list[SkillStep]           # 步骤列表

# Registry
WORKFLOW_SKILLS: dict[str, WorkflowSkillInfo] = {}  # 仅存储 Workflow Skills
```

---

## Files to Create/Modify

### New Files

| 文件 | 说明 |
|------|------|
| `backend/aime/__init__.py` | AIME 模块入口 |
| `backend/aime/planner.py` | AIME Dynamic Planner |
| `backend/aime/actor_factory.py` | Actor Factory |
| `backend/aime/progress_manager.py` | Progress Manager |
| `backend/aime/models.py` | 数据模型 (Subtask, ProgressList, etc.) |
| **Intent Module** | |
| `backend/aime/intent/__init__.py` | 意图模块入口，导出 IntentAnalyzer, IntentResult |
| `backend/aime/intent/analyzer.py` | 核心分析器（组合多个分类器） |
| `backend/aime/intent/models.py` | IntentResult 数据类、Action 类型、CAPABILITY_AGENT_MAP |
| `backend/aime/intent/classifiers/base.py` | 分类器抽象基类 |
| `backend/aime/intent/classifiers/rule_based.py` | 规则匹配分类器 |
| `backend/aime/intent/classifiers/keyword_based.py` | 关键词匹配分类器 |
| `backend/aime/intent/classifiers/llm_based.py` | LLM 深度分析分类器 |
| `backend/aime/intent/domain/base.py` | 领域识别器基类 (可选) |
| `backend/aime/intent/domain/manufacturing.py` | 制造业术语识别 (可选) |
| `backend/aime/intent/domain/quality.py` | 质量管理术语识别 (可选) |
| **Actors** | |
| `backend/aime/actors/__init__.py` | Actors 模块入口 |
| `backend/aime/actors/generic.py` | Generic Actor (替换 General 的执行能力) |

### Modified Files

| 文件 | 修改内容 |
|------|----------|
| `backend/supervisor.py` | 重写为调用 AIME Planner |
| `backend/agents/general.py` | 删除或标记废弃 |
| `backend/main.py` | 更新 import 路径 |
| `backend/skills/registry.py` | 新增 `WORKFLOW_SKILLS`、`WorkflowSkillInfo`、`SkillStep`（SkillEntry 保持不变） |
| `backend/skills/loader.py` | 解析 SKILL.md 的 `type` 和 `steps` 字段，Workflow Skills 额外注册到 `WORKFLOW_SKILLS` |
| `backend/registry.py` | AgentEntry 新增 `capabilities` 和 `source` 字段 |
| `backend/agents/loader.py` | 解析 AGENTS.md frontmatter 提取 capabilities，注册时设置 `source="package"` |
| `backend/agents/research.py` | 注册时声明 `capabilities=["web_search", ...]` |
| `backend/agents/sql.py` | 注册时声明 `capabilities=["database", "sql_query"]` |

### Unchanged Files (保持兼容)

| 文件 | 说明 |
|------|------|
| `backend/stream_handler.py` | 保持不变，SSE 格式兼容 |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

**性能指标**:
- **SC-001**: 简单任务响应时间 < 2秒 (当前: ~1.5秒，无退化)
- **SC-002**: 意图识别延迟 < 300ms (规则+关键词分类器)
- **SC-003**: Agent 选择延迟 < 500ms (包括优先级判断)

**意图识别模块**:
- **SC-004**: RuleBasedClassifier 100% 识别显式路由 `[ROUTE_TO: xxx]`
- **SC-005**: action 分类准确率 > 85% (direct_reply/delegate/plan/clarify)
- **SC-006**: clarify 场景 MUST 返回有效的 clarify_questions
- **SC-007**: 分类器可插拔测试通过 (替换/新增分类器无需改 Planner)

**Agent 选择准确性**:
- **SC-008**: 用户显式指定 Agent 时 100% 直接路由 (无意图识别)
- **SC-009**: capabilities 到 Agent 匹配准确率 > 90%
- **SC-010**: 能力匹配准确率 > 85% (任务正确路由到合适 Agent)

**功能完整性**:
- **SC-011**: 专业任务在 Progress List 中显示为子任务 (可追踪性)
- **SC-012**: 复杂任务正确分解为 2+ 子任务

**Skills 集成**:
- **SC-013**: Atomic Skills 100% 作为单子任务执行
- **SC-014**: Workflow Skills 正确展开为多个子任务 (步骤数 = subtask 数)
- **SC-015**: Skill Instructions 正确注入 Actor prompt
- **SC-016**: 现有 Skills (无 `type` 字段) 100% 兼容，默认按 atomic 处理

**兼容性**:
- **SC-017**: 前端 SSE 显示无变化 (兼容性测试通过)
- **SC-018**: 现有 E2E 测试全部通过 (simple-chat, sql-agent, research-agent, planning-agent)

**SSE/UI 渲染**:
- **SC-019**: `direct_reply` 模式 100% 只显示 MessageContent（无 ThinkingBubble、无 TaskList）
- **SC-020**: `delegate` 模式 100% 显示 ThinkingBubble + TaskList(SpawnedTask) + MessageContent
- **SC-021**: `plan` 模式 100% 显示 ThinkingBubble + TaskList(Todos + SpawnedTasks) + MessageContent
- **SC-022**: 工具调用 100% 正确嵌套在对应 SpawnedTask 下（通过 task_id 关联）
- **SC-023**: displayScenario 状态转换符合设计：只升级不降级

**Agent Registry 扩展**:
- **SC-024**: 预设 Agent 100% 正确注册 capabilities（research: web_search, sql: database）
- **SC-025**: 自定义 Agent 从 AGENTS.md frontmatter 正确解析 capabilities
- **SC-026**: 能力匹配时预设和自定义 Agent 都被考虑（无遗漏）
- **SC-027**: 分数相同时预设 Agent 优先被选择

---

## Implementation Plan

### Phase 1: Intent Module & Core Components (4 days)

1. **Day 1**: 数据模型 + Intent Module 基础
   - 定义 IntentResult, SubtaskSpec, ProgressList 数据结构
   - 实现 IntentAnalyzer 框架和 ClassifierBase 接口
   - 实现 RuleBasedClassifier（处理显式路由）

2. **Day 2**: Intent Module 完善 + Progress Manager
   - 实现 KeywordClassifier（关键词匹配）
   - 实现 LLMClassifier（深度分析）
   - 实现 Progress Manager（复用现有 SSE 事件）

3. **Day 3**: Actor Factory
   - 实现 Agent 选择优先级逻辑
   - 实现能力匹配和校验
   - 测试与 Research/SQL Agent 的集成

4. **Day 4**: AIME Planner 基础版
   - 集成 IntentAnalyzer
   - 实现简单任务直接回复
   - 实现专业任务单子任务路由

### Phase 2: Task Decomposition & Skills (3 days)

5. **Day 5**: 任务分解逻辑
   - 实现复杂任务拆解
   - 实现子任务 DAG 生成

6. **Day 6**: Skills 集成
   - 扩展 SkillEntry 支持 `type` 和 `steps` 字段
   - 实现 Workflow Skill 展开逻辑 (Planner)
   - 实现 Skill Instructions 注入 (Actor Factory)

7. **Day 7**: 动态执行
   - 实现子任务顺序/并行执行
   - 实现结果汇总
   - 测试 Atomic/Workflow Skills

### Phase 3: Integration & Testing (2 days)

8. **Day 8**: 系统集成
   - 替换 supervisor.py
   - 废弃 general.py
   - 更新 main.py

9. **Day 9**: 测试 & 优化
   - 运行现有 E2E 测试
   - Skills 集成测试（Atomic + Workflow）
   - 性能测试
   - Bug 修复

### Phase 4: Domain Extension (可选, 2 days)

10. **Day 10-11**: 领域识别器
    - 实现 ManufacturingRecognizer（制造业术语）
    - 实现 QualityRecognizer（质量管理术语）
    - 集成到 IntentAnalyzer

---

## Appendix: AIME Paper Key Insights

### Three Challenges in Plan-and-Execute Framework

1. **Rigid Plan Execution**: 计划一旦生成就固定，无法适应执行反馈
2. **Static Agent Capabilities**: Agent 角色和工具固定，无法应对新需求
3. **Inefficient Communication**: Agent 间信息传递丢失上下文

### AIME's Solutions

1. **Dynamic Planner**: 持续监控执行进度，动态调整计划
2. **Actor Factory**: 按需创建专业化 Actor，配置合适的 persona/tools/knowledge
3. **Progress Management Module**: 集中式状态管理，确保全局一致性

### Key Formula

```
Planner Operation:
(L_{t+1}, g_{t+1}) = LLM_planner(P_planner, (G, L_t, H_t))

Actor Instantiation:
A_t = F_factory(g_t) where A_t = {LLM_t, T_t, P_t, M_t}

Prompt Composition:
P_t = Compose(ρ_t, desc(T_t), κ_t, ε, Γ)
  - ρ_t: Persona
  - T_t: Toolkit
  - κ_t: Knowledge
  - ε: Environment
  - Γ: Format
```

### Workflow Summary

```
Step 1: Task Decomposition (Planner receives user request)
Step 2: (Sub)Task Dispatch (Planner identifies next task)
Step 3: Actor Instantiation (Factory creates specialized actor)
Step 4: ReAct Execution (Actor executes with reasoning-action loop)
Step 5: Progress Update (Actor reports to Progress Manager)
Step 6: Evaluation and Iteration (Planner evaluates and dispatches next)
```
