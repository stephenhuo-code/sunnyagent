# Feature Specification: Context Manager

**Parent Feature**: `005-aime-supervisor`
**Component**: `context-manager`
**Created**: 2026-02-16
**Status**: Draft
**Input**: AIME 任务上下文管理器，用于管理任务间的上下文传递

## Overview

ContextManager 是 AIME 架构的核心组件，负责解决多任务执行时任务间上下文传递的问题。

### 问题背景

当前 AIME 在执行多任务计划时，后续任务无法获取前置任务的输出：
- 任务 1（RESEARCH）收集数据后，任务 2（GENERAL）无法访问这些数据
- 导致任务 2 输出 "If you have the data file, please upload it"
- 任务间的依赖关系 (`depends_on`) 未被正确利用

### 解决方案

引入 ContextManager 统一管理任务上下文的存储、检索和智能准备。

### 存储架构

```
┌─────────────────────────────────────────────────────────┐
│                    ContextManager                        │
│                                                          │
│   ┌──────────────┐         ┌──────────────────────┐     │
│   │ LRU Cache    │ ──miss──> │ PostgreSQL          │     │
│   │ (热数据)      │ <──load── │ (task_contexts 表)  │     │
│   └──────────────┘         └──────────────────────┘     │
│                                      │                   │
│                                      ▼                   │
│                            ┌──────────────────────┐     │
│                            │ 定期清理任务          │     │
│                            │ (过期数据自动删除)    │     │
│                            └──────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

- **热数据**：内存 LRU Cache，快速访问当前会话的上下文
- **持久化**：PostgreSQL `task_contexts` 表，支持会话恢复
- **清理策略**：滑动过期（用户访问时延长过期时间）+ 主动删除

### 过期策略：滑动过期

采用滑动过期机制，用户每次访问上下文时自动延长过期时间：

```
用户访问上下文
    ↓
更新 last_accessed_at = NOW()
    ↓
更新 expires_at = NOW() + 7天
    ↓
上下文继续可用
```

**效果**：
- 活跃会话的上下文永不过期（只要用户持续访问）
- 7 天无访问的上下文自动清理

### 任务 I/O 声明与管理

为解决任务间输入/输出关系不明确的问题，采用**显式声明 + 自动推断**的混合方案：

**问题**：
- LLM 分解任务时可能遗漏 `depends_on` 设置
- 前端无法展示任务间的数据流向
- 无法验证任务输入是否满足

**解决方案**：

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Planner._decompose_task() - 显式声明                          │
│    └─> 生成 SubtaskSpec (含 expected_input/expected_output)      │
│                                                                 │
│ 2. ProgressManager.add_task(spec) - 依赖校验                     │
│    └─> 校验: expected_input 是否被前置任务的 output 覆盖         │
│                                                                 │
│ 3. ContextManager.store(task_id, result) - 自动分类              │
│    └─> 自动分类输出类型，与 expected_output 比对                 │
│                                                                 │
│ 4. ContextManager.prepare_for_task(depends_on) - 智能匹配        │
│    └─> 根据 expected_input 筛选相关上下文                        │
└─────────────────────────────────────────────────────────────────┘
```

**SubtaskSpec 扩展**：

```python
@dataclass
class SubtaskSpec:
    id: str
    description: str
    capabilities: list[str]
    depends_on: list[str]

    # I/O 声明（由 LLM 任务分解时生成）
    expected_input: list[str] | None = None   # 期望输入: ["financial_report", "revenue_data"]
    expected_output: list[str] | None = None  # 产出输出: ["analysis_report", "chart"]
```

**任务分解示例**：

```json
[
  {
    "description": "搜索特斯拉最新财报",
    "capabilities": ["web_search"],
    "depends_on": [],
    "expected_input": [],
    "expected_output": ["financial_report", "revenue_data"]
  },
  {
    "description": "分析营收趋势",
    "capabilities": ["general"],
    "depends_on": [0],
    "expected_input": ["financial_report", "revenue_data"],
    "expected_output": ["analysis_report"]
  }
]
```

**前端展示效果**：

```
Task 0: 搜索财报
  输出: [财报数据, 营收数字]
       │
       ▼ (数据流)
Task 1: 分析趋势
  输入: [财报数据, 营收数字]
  输出: [分析报告]
```

### 组件交互关系

ContextManager 与 Planner、ActorFactory 的协作关系：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            AIMEPlanner                                   │
│                                                                         │
│  ┌───────────────┐  ┌─────────────────┐  ┌────────────────────────────┐ │
│  │ IntentAnalyzer│  │ ActorFactory    │  │ ContextManager             │ │
│  │               │  │                 │  │                            │ │
│  │ 分析意图       │  │ 选择执行者       │  │ 存储/检索/智能准备上下文    │ │
│  └───────┬───────┘  └────────┬────────┘  └─────────────┬──────────────┘ │
│          │                   │                         │                │
│          ▼                   ▼                         ▼                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        执行流程                                    │  │
│  │                                                                   │  │
│  │  1. analyze(message) ──> IntentResult(action=plan)                │  │
│  │                                                                   │  │
│  │  2. _decompose_task() ──> [SubtaskSpec, SubtaskSpec, ...]        │  │
│  │                                                                   │  │
│  │  3. for spec in subtasks:                                        │  │
│  │       ├─> ActorFactory.select_actor(spec) ──> Actor              │  │
│  │       ├─> ContextManager.prepare_for_task(spec.depends_on)       │  │
│  │       ├─> _execute_actor(actor, message + context)               │  │
│  │       └─> ContextManager.store(spec.id, result)                  │  │
│  │                                                                   │  │
│  │  4. _generate_summary(results)                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

**执行时序（含 I/O 声明）**：

```
Task 0: 搜索特斯拉财报
    │  expected_input: []
    │  expected_output: ["financial_report", "revenue_data"]
    │
    ├─ ActorFactory.select_actor() ──> research_agent
    ├─ _execute_actor(research_agent, "搜索特斯拉财报")
    └─ ContextManager.store("task-0", result, expected_output)
           │
           └─> 自动分类: output_types = ["financial_report", "table", "revenue_data"]
                │
                ▼
Task 1: 分析营收趋势 (depends_on: task-0)
    │  expected_input: ["financial_report", "revenue_data"]
    │  expected_output: ["analysis_report"]
    │
    ├─ ActorFactory.select_actor() ──> general_agent
    ├─ ContextManager.prepare_for_task(["task-0"], expected_input)
    │       │
    │       └─> 匹配: task-0.output_types ⊇ expected_input ✓
    │       └─> 返回 task-0 的相关输出（按类型筛选）
    │
    ├─ _execute_actor(general_agent, "分析营收趋势" + context)
    └─ ContextManager.store("task-1", result, expected_output)
```

**职责划分**：

| 组件 | 职责 | I/O 相关职责 |
|------|------|-------------|
| **Planner** | 编排任务执行流程 | 生成带 I/O 声明的 SubtaskSpec |
| **ProgressManager** | 任务状态追踪 | 校验 expected_input 是否满足 |
| **ActorFactory** | 选择合适的 Agent | - |
| **ContextManager** | 存储/检索/智能准备上下文 | 自动分类 output_types，按 expected_input 筛选 |

**Planner 集成点**：

```python
# backend/aime/planner.py - _handle_plan() 方法

# 集成点 1: 执行任务前，准备上下文（根据 expected_input 筛选）
if spec.depends_on:
    context_str = await self.context_manager.prepare_for_task(
        task_description=spec.description,
        depends_on=spec.depends_on,
        expected_input=spec.expected_input,  # 用于智能筛选
    )

# 集成点 2: 任务完成后，存储结果（自动分类输出类型）
await self.context_manager.store(
    context_id=spec.id,
    thread_id=thread_id,
    content=result_text,
    expected_output=spec.expected_output,  # 用于验证和标记
)
```

## Clarifications

### Session 2026-02-16

- Q: 上下文访问安全控制 - 当用户 A 的任务上下文存储后，用户 B 能否通过 `get(context_id)` 访问？ → A: 严格隔离（thread_id 级别校验，自动验证请求来源）
- Q: 并发写入处理 - 当两个任务同时调用 `store(context_id, ...)` 时如何处理？ → A: 后者覆盖（Last-Write-Wins，使用 `ON CONFLICT DO UPDATE`）
- Q: PostgreSQL 连接失败时的行为？ → A: 优雅降级（记录错误日志，继续使用内存缓存，任务执行不中断）
- Q: LLM 摘要/分类失败时的行为？ → A: 降级为简单处理（摘要失败 → 截断前 500 字符；分类失败 → 使用 `["raw_data"]` 默认标签）

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 基础上下文传递 (Priority: P1)

用户发起一个需要多步骤完成的任务（如"搜索苹果财报，然后分析营收趋势"），系统分解为多个子任务后，后续任务能够自动获取前置任务的输出结果，无需用户手动提供。

**Why this priority**: 这是 ContextManager 的核心价值，解决了当前任务间"断链"的问题。

**Independent Test**: 发送多步骤任务请求，验证第二个任务是否能引用第一个任务的输出内容。

**Acceptance Scenarios**:

1. **Given** 用户发送 "搜索特斯拉最新财报，然后分析其营收趋势"，**When** 系统执行第二个任务（分析），**Then** 分析任务应包含第一个任务（搜索）收集到的财报数据，不再要求用户上传数据。

2. **Given** 任务 A 完成并产生输出，任务 B 的 `depends_on` 包含任务 A 的 ID，**When** 任务 B 开始执行，**Then** 任务 B 的输入消息中应包含任务 A 的输出内容。

3. **Given** 任务 A 尚未完成，任务 B 依赖任务 A，**When** 调度器检查任务 B，**Then** 任务 B 应保持 pending 状态，等待任务 A 完成。

---

### User Story 2 - 长上下文智能处理 (Priority: P2)

当前置任务的输出内容很长（超过 2000 tokens）时，系统自动生成摘要和提取关键数据，将精简后的上下文传递给后续任务，避免超出 LLM 上下文窗口限制。

**Why this priority**: 确保系统在处理大量数据时仍能正常工作，是健壮性的关键。

**Independent Test**: 发送会产生长输出的任务，验证后续任务收到的是摘要而非全文。

**Acceptance Scenarios**:

1. **Given** 任务 A 的输出超过 2000 tokens，**When** 任务 B 请求任务 A 的上下文，**Then** 任务 B 收到的应是摘要版本（包含关键信息和数据），而非原始全文。

2. **Given** 长上下文被摘要处理，**Then** 摘要应保留：关键数字/统计数据、重要日期、核心结论/发现。

3. **Given** 任务 A 的输出少于 2000 tokens，**When** 任务 B 请求上下文，**Then** 任务 B 收到完整的原始内容。

---

### User Story 3 - 多依赖上下文合并 (Priority: P3)

当一个任务依赖多个前置任务时，系统能够合并多个上下文，并合理分配每个上下文的 token 预算。

**Why this priority**: 支持更复杂的任务编排场景。

**Independent Test**: 创建依赖两个任务的第三个任务，验证它能获取两个前置任务的输出。

**Acceptance Scenarios**:

1. **Given** 任务 C 的 `depends_on` 为 `[A, B]`，**When** 任务 C 开始执行，**Then** 任务 C 的上下文应包含任务 A 和任务 B 的输出。

2. **Given** 任务 A 和任务 B 的输出都很长，**When** 合并上下文时，**Then** 系统应按比例分配 token 预算，确保总上下文不超过限制。

---

### User Story 4 - 任务 I/O 声明与验证 (Priority: P2)

任务分解时生成显式的输入/输出声明，系统自动验证依赖关系，确保后续任务能获取所需数据，并在前端展示任务间的数据流向。

**Why this priority**: 解决 LLM 任务分解时遗漏 `depends_on` 的问题，提升任务编排的可靠性和可观测性。

**Independent Test**: 发送多步骤任务，验证任务分解结果包含 I/O 声明，验证输出类型被正确分类。

**Acceptance Scenarios**:

1. **Given** 用户发送 "搜索特斯拉财报，然后分析营收趋势"，**When** 系统分解任务，**Then** 每个子任务应包含 `expected_input` 和 `expected_output` 声明。

2. **Given** 任务 A 声明 `expected_output: ["financial_report"]`，任务 B 声明 `expected_input: ["financial_report"]`，**When** 系统执行任务 B，**Then** 系统应自动建立依赖关系（即使 LLM 遗漏了 `depends_on`）。

3. **Given** 任务完成并存储结果，**When** ContextManager.store() 被调用，**Then** 系统应自动分析输出内容并打上 `output_types` 标签。

4. **Given** 任务 B 的 `expected_input` 包含 "chart_data"，但前置任务 A 的 `output_types` 不包含 "chart_data"，**When** 系统检测到不匹配，**Then** 应记录警告日志并尝试从上下文中推断相关数据。

5. **Given** 任务列表在前端展示，**When** 用户查看任务详情，**Then** 应能看到每个任务的输入/输出类型及数据流向。

---

### User Story 5 - 会话恢复与持久化 (Priority: P2)

用户关闭浏览器后，过一段时间重新打开同一会话，系统能够恢复之前的任务上下文，继续未完成的对话。

**Why this priority**: 提升用户体验，支持长时间跨度的复杂任务。

**Independent Test**: 关闭浏览器，等待一段时间后重新打开会话，验证能继续使用之前任务的上下文。

**Acceptance Scenarios**:

1. **Given** 用户在会话中完成了任务 A，然后关闭浏览器，**When** 用户 3 天后重新打开同一会话，**Then** 系统能够获取任务 A 的上下文。

2. **Given** 用户重新打开会话，**When** 发送依赖之前任务输出的新请求，**Then** 系统能正确准备上下文，无需用户重新提供数据。

3. **Given** 上下文已超过 7 天未被访问，**When** 用户尝试恢复会话，**Then** 系统返回上下文不可用，用户需重新执行任务。

4. **Given** 用户在第 6 天访问了上下文，**When** 再过 5 天后访问，**Then** 上下文仍然可用（滑动过期，从最后访问时间重新计算 7 天）。

---

### User Story 6 - 上下文清理与滑动过期 (Priority: P2)

系统采用滑动过期策略：用户每次访问上下文时延长过期时间；超过 7 天未访问的上下文自动清理；用户删除会话时，相关上下文同步删除。

**Why this priority**: 保证系统长期运行的稳定性和存储效率，同时确保活跃用户的上下文不会意外过期。

**Independent Test**: 验证访问时延长过期时间，验证过期上下文被自动清理，验证删除会话时上下文同步删除。

**Acceptance Scenarios**:

1. **Given** 上下文超过 7 天未被访问，**When** 清理任务运行，**Then** 该上下文应被自动删除。

2. **Given** 用户主动删除一个会话，**When** 删除操作完成，**Then** 该会话的所有上下文数据应同步删除。

3. **Given** 上下文即将过期（如还剩 1 天），**When** 用户访问该上下文，**Then** 过期时间应延长至访问时间 + 7 天。

4. **Given** 系统配置了自定义过期时间（如 14 天），**When** 用户访问上下文，**Then** 过期时间应延长至访问时间 + 14 天。

5. **Given** 用户持续每周访问会话，**When** 检查上下文状态，**Then** 上下文应永久可用（只要用户保持活跃）。

---

### Edge Cases

- 依赖的任务失败或没有输出时，如何处理？
  - 系统应记录警告日志，继续执行但上下文为空
- 循环依赖如何防止？
  - 任务分解阶段应验证依赖关系，拒绝循环依赖
- 上下文存储空间不足时如何处理？
  - LRU 策略淘汰最旧的上下文，保留活跃任务的数据
- 并发写入同一 context_id 时如何处理？
  - 采用 Last-Write-Wins 策略，使用 `ON CONFLICT DO UPDATE` 确保数据一致性
- PostgreSQL 连接失败时如何处理？
  - 优雅降级：记录错误日志，继续使用内存缓存，任务执行不中断；会话恢复功能暂时不可用
- LLM 摘要或分类调用失败时如何处理？
  - 降级为简单处理：摘要失败 → 截断前 500 字符；分类失败 → 使用 `["raw_data"]` 默认标签

## Requirements *(mandatory)*

### Functional Requirements

**核心接口**
- **FR-001**: 系统 MUST 提供 `store(context_id, thread_id, content)` 接口，用于存储任务输出
- **FR-002**: 系统 MUST 提供 `get(context_id)` 接口，用于检索指定任务的上下文
- **FR-003**: 系统 MUST 提供 `prepare_for_task(task_description, depends_on)` 接口，智能准备任务所需的上下文

**智能处理**
- **FR-004**: 系统 MUST 在上下文超过阈值（2000 tokens）时自动生成摘要
- **FR-005**: 系统 MUST 从长上下文中提取结构化关键数据（数字、日期、发现）
- **FR-006**: 系统 MUST 在 LLM 摘要失败时降级为截断前 500 字符；在分类失败时使用 `["raw_data"]` 默认标签

**I/O 声明与分类**
- **FR-007**: 系统 MUST 在 `store()` 时自动分析输出内容，生成 `output_types` 标签（如 financial_report, chart, code 等）
- **FR-008**: 系统 MUST 在 `prepare_for_task()` 时根据 `expected_input` 筛选相关上下文
- **FR-009**: 系统 SHOULD 在 `expected_input` 与前置任务 `output_types` 不匹配时记录警告日志
- **FR-010**: 系统 SHOULD 支持在任务分解时自动补全遗漏的 `depends_on`（基于 I/O 类型匹配）

**存储与缓存**
- **FR-011**: 系统 MUST 支持 LRU 缓存策略，限制内存中的上下文数量（默认 100 条）
- **FR-012**: 系统 MUST 将上下文持久化到 PostgreSQL `task_contexts` 表，支持会话恢复
- **FR-013**: 系统 MUST 在缓存未命中时从 PostgreSQL 加载上下文到内存
- **FR-014**: 系统 MUST 在 PostgreSQL 连接失败时优雅降级：记录错误日志，继续使用内存缓存，不阻塞任务执行

**清理与滑动过期**
- **FR-015**: 系统 MUST 提供 `cleanup_thread(thread_id)` 接口，清理指定会话的所有上下文
- **FR-016**: 系统 MUST 支持可配置的过期时间（默认 7 天），过期上下文自动标记为不可用
- **FR-017**: 系统 MUST 实现滑动过期：每次访问上下文时，更新 `last_accessed_at` 并延长 `expires_at`
- **FR-018**: 系统 MUST 提供定期清理任务，删除过期的上下文数据
- **FR-019**: 系统 MUST 在用户删除会话时，同步删除该会话的所有上下文

**安全隔离**
- **FR-020**: 系统 MUST 在 `get()` 和 `prepare_for_task()` 时验证请求的 thread_id 与上下文的 thread_id 一致
- **FR-021**: 系统 MUST 拒绝跨 thread_id 的上下文访问请求，并记录安全警告日志

**集成**
- **FR-022**: 系统 MUST 在 Planner 任务完成后自动调用 store 存储结果（含 expected_output）
- **FR-023**: 系统 MUST 在 Planner 执行任务前自动调用 prepare_for_task 获取依赖上下文（含 expected_input）

### Key Entities

- **ContextEntry**: 任务上下文条目
  - context_id: 任务 ID（唯一标识，主键）
  - thread_id: 会话 ID（外键，关联 conversations 表）
  - content: 原始输出内容（TEXT）
  - summary: 摘要（长上下文时生成，TEXT，可空）
  - key_data: 结构化关键数据（JSONB，可空）
  - output_types: 输出类型标签（TEXT[]，自动分类，如 ["financial_report", "table"]）
  - expected_output: 期望输出类型（TEXT[]，来自 SubtaskSpec，可空）
  - token_count: token 估算值（INTEGER）
  - created_at: 创建时间（TIMESTAMP）
  - last_accessed_at: 最后访问时间（TIMESTAMP，用于滑动过期）
  - expires_at: 过期时间（TIMESTAMP，last_accessed_at + 配置的过期时长）
  - metadata: 额外元数据（JSONB，如 actor 名称）

- **SubtaskSpec 扩展**（Planner 模型）:
  - expected_input: 期望输入类型（TEXT[]，如 ["financial_report", "revenue_data"]）
  - expected_output: 期望输出类型（TEXT[]，如 ["analysis_report", "chart"]）

- **ContextManager**: 上下文管理器
  - 内存缓存（LRU，热数据快速访问）
  - PostgreSQL 持久化（会话恢复、跨重启保留）
  - 摘要生成能力（LLM）
  - 关键数据提取能力（LLM）
  - 输出类型自动分类（LLM，生成 output_types）
  - I/O 匹配与筛选（按 expected_input 筛选相关上下文）
  - 滑动过期机制（访问时延长过期时间）
  - 清理调度器（定期删除过期数据）

- **数据库表设计** (`task_contexts`):
  ```sql
  CREATE TABLE task_contexts (
      context_id VARCHAR(64) PRIMARY KEY,
      thread_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      content TEXT NOT NULL,
      summary TEXT,
      key_data JSONB,
      output_types TEXT[] DEFAULT '{}',        -- 自动分类的输出类型
      expected_output TEXT[] DEFAULT '{}',     -- 期望的输出类型（来自 SubtaskSpec）
      token_count INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW(),
      last_accessed_at TIMESTAMP DEFAULT NOW(),
      expires_at TIMESTAMP NOT NULL,
      metadata JSONB DEFAULT '{}'
  );

  CREATE INDEX idx_task_contexts_thread_id ON task_contexts(thread_id);
  CREATE INDEX idx_task_contexts_expires_at ON task_contexts(expires_at);
  CREATE INDEX idx_task_contexts_output_types ON task_contexts USING GIN(output_types);
  ```

- **输出类型分类**（output_types 预定义值）:
  - `financial_report` - 财务报告、财报数据
  - `revenue_data` - 营收数据、销售数据
  - `table` - 表格数据
  - `chart` - 图表
  - `code` - 代码片段
  - `analysis_report` - 分析报告
  - `summary` - 摘要总结
  - `file` - 生成的文件
  - `raw_data` - 原始数据

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 多任务场景下，后续任务能够在 100ms 内获取前置任务的上下文（缓存命中）
- **SC-002**: 长上下文（>2000 tokens）的摘要能在 3 秒内生成
- **SC-003**: 100 个并发会话 × 5 个任务/会话的上下文数据，内存占用不超过 50MB
- **SC-004**: 缓存未命中时，从 PostgreSQL 恢复上下文的时间不超过 100ms
- **SC-005**: 用户发送多步骤任务后，不再出现"请上传数据"的错误提示
- **SC-006**: 用户关闭浏览器后 7 天内重新打开会话，能够恢复任务上下文
- **SC-007**: 超过 7 天未访问的上下文在清理任务运行后被删除
- **SC-008**: 删除会话时，相关上下文在 100ms 内同步删除
- **SC-009**: 访问上下文时，过期时间自动延长至当前时间 + 7 天
- **SC-010**: 任务分解结果 100% 包含 `expected_input` 和 `expected_output` 声明
- **SC-011**: 输出类型自动分类准确率 > 90%（与 expected_output 比对）
- **SC-012**: I/O 类型不匹配时，系统能记录警告并尝试推断相关数据

## Assumptions

- 任务上下文需要跨浏览器会话持久化（用户关闭浏览器后可恢复）
- 采用滑动过期策略，默认过期时间为 7 天（从最后访问时间计算）
- 单个任务的输出通常在 1KB ~ 100KB 之间
- LLM 摘要能力由现有的 `get_model("supervisor")` 提供
- PostgreSQL 数据库已就绪（现有 `conversations` 表可用于外键关联）
- 清理任务可通过 FastAPI 后台任务或独立定时任务实现

## Out of Scope

- 向量检索/语义搜索（后续版本）
- 上下文的加密存储
- 分布式环境下的上下文同步（单实例部署）
- 大文件（>100MB）的上下文存储（大文件应使用 file_service）

## Configuration

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CONTEXT_EXPIRATION_DAYS` | 7 | 上下文过期时间（天），采用滑动过期 |
| `CONTEXT_CACHE_SIZE` | 100 | 内存 LRU 缓存最大条数 |
| `CONTEXT_CLEANUP_INTERVAL` | 3600 | 清理任务运行间隔（秒） |

## Dependencies

- AIME Planner (`backend/aime/planner.py`) - 集成点，任务分解生成 I/O 声明
- SubtaskSpec 模型 (`backend/aime/models.py`) - 扩展 expected_input/expected_output 字段
- LLM 模型 (`backend/llm/`) - 摘要生成、输出类型分类
- Progress Manager (`backend/aime/progress_manager.py`) - 任务状态追踪、依赖校验
- PostgreSQL 数据库 (`backend/db.py`) - 持久化存储
- Conversations 表 (`backend/conversations/`) - 外键关联，级联删除
