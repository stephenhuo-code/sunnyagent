# Feature Specification: Meta-Agent Plugin Optimization System

**Feature Branch**: `013-meta-agent`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User description: "创建一个独立的 meta-agent 系统，使用 Langfuse 构建测试数据集，自动构建和优化 packages 中的 command workflow 和 skills，支持多轮训练直到达到优化目标"

## Clarifications

### Session 2026-03-04

- 初步设计已记录在 design-notes.md 草案中
- 核心目标：自动化 Plugin（Package）中 Commands 和 Skills 的生成和优化
- **Langfuse 作为核心平台**：测试数据集管理和评估都通过 Langfuse 完成
- **系统定位**：独立的子系统，与 SunnyAgent 主系统分离
- **架构模式**：基于 Claude Agent Team 的多 Agent 协作闭环
- **修改范围限制**：只允许修改 `packages/` 目录下的文件，禁止修改主系统代码
- **测试上下文**：每个测试用例需要在具体的项目和对话上下文中运行，支持关联文件
- Q: 谁可以运行优化？使用什么账号？ → A: 使用 SunnyAgent 系统的 admin 账号作为测试账号
- Q: 优化中断后如何恢复？ → A: 支持断点续跑，保存迭代状态，可从上次中断处继续
- Q: LLM 速率限制如何处理？ → A: 自动重试 + 指数退避（最多重试 3 次）
- Q: 数据集版本如何管理？ → A: 自动版本号，每次更新自动递增（如 v1, v2）
- Q: 是否支持并发优化多个 Plugin？ → A: 单任务模式，同一时间只允许一个优化任务运行
- Q: 评分维度如何加权计算总体分数？ → A: correctness 优先（50% correctness，其他各 16.7%）
- Q: 修改是自动应用还是需人工审核？ → A: 全自动应用，依赖 git 回滚作为安全网
- Q: Multi-Agent 协作如何实现？ → A: 直接使用 Claude Agent Team 架构（详见 design-notes.md）

## System Overview

### 系统定位

Meta-Agent 是一个**独立的插件优化系统**，作为 SunnyAgent 的配套工具运行：

- **独立部署**：有自己的目录结构、配置和运行环境
- **只读主系统**：通过 API 调用 SunnyAgent，但不修改其代码
- **可写范围**：仅限 `packages/` 目录下的 Plugin 定义文件
- **Langfuse 集成**：复用 SunnyAgent 已有的 Langfuse 实例，SunnyAgent 执行时自动产生 trace，Meta-Agent 负责创建 Dataset 和读取 trace 进行分析

### 核心工作流

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Meta-Agent 优化流程                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  0. 测试环境准备                                                          │
│     ┌──────────────┐      ┌──────────────┐      ┌──────────────┐        │
│     │ 创建测试项目  │  →   │ 上传测试文件  │  →   │ 准备对话     │        │
│     │ (Project)    │      │ (Sources)    │      │ 上下文       │        │
│     └──────────────┘      └──────────────┘      └──────────────┘        │
│                                                                          │
│  1. 数据集准备                                                            │
│     ┌──────────────┐      ┌──────────────┐      ┌──────────────┐        │
│     │ 用户填写模板  │  →   │ 验证 & 解析  │  →   │ 同步到       │        │
│     │ (CSV/JSONL)  │      │ + 文件关联   │      │ Langfuse     │        │
│     └──────────────┘      └──────────────┘      │ Dataset      │        │
│                                                  └──────────────┘        │
│                                                                          │
│  2. 迭代优化循环                                                          │
│     ┌──────────────┐      ┌──────────────┐      ┌──────────────┐        │
│     │ Langfuse     │  →   │ 分析失败     │  →   │ 生成/修改    │        │
│     │ Evaluation   │      │ 生成建议     │      │ Commands/    │        │
│     │ (带文件上下文)│      │              │      │ Skills       │        │
│     └──────────────┘      └──────────────┘      └──────────────┘        │
│            ↑                                            │                │
│            └────────────── 重新评估 ←───────────────────┘                │
│                                                                          │
│  3. 终止条件: 达标 / 最大迭代 / 无提升                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 测试执行上下文

每个测试用例在 SunnyAgent 中运行时需要完整的执行上下文：

```
┌─────────────────────────────────────────────────────────┐
│                    测试执行上下文                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐                                        │
│  │   Project   │  测试项目（可共享或每个 case 独立）      │
│  │  (项目上下文) │                                        │
│  └──────┬──────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │   Sources   │  测试所需的文件（CSV、Excel、文档等）    │
│  │  (项目文件)  │  - 上传到项目的 Sources                 │
│  │             │  - 测试时选中作为上下文                  │
│  └──────┬──────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │ Conversation│  对话上下文                             │
│  │  (对话)     │  - 可以是新对话                         │
│  │             │  - 或带历史的对话（测试多轮）            │
│  └──────┬──────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │   Message   │  测试输入 + 选中的文件                  │
│  │  (用户消息)  │  → 发送到 SunnyAgent                   │
│  └─────────────┘                                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 优化目标文件

系统可以生成和修改的文件类型：

| 文件类型 | 路径模式 | 说明 |
|---------|---------|------|
| Plugin README | `packages/<plugin>/README.md` | 插件说明和配置 |
| Plugin Config | `packages/<plugin>/.plugin/plugin.json` | 插件元数据 |
| Commands | `packages/<plugin>/commands/*.md` | 命令定义（用户可调用的 workflow） |
| Skills | `packages/<plugin>/skills/*/SKILL.md` | 技能定义（Agent 内部能力） |
| Skill References | `packages/<plugin>/skills/*/references/*.md` | 技能参考资料 |

### 禁止修改的文件

以下文件 Meta-Agent 系统**绝对不允许修改**：

```
backend/**              # 后端代码
frontend/**             # 前端代码
infra/**                # 基础设施
skills/**               # 顶层技能（非 Package）
docker-compose.yml      # 基础设施配置
*.py                    # 任何 Python 代码
```

## User Scenarios & Testing *(mandatory)*

### User Story 0 - 测试环境准备 (Priority: P1)

在运行测试前，系统需要准备测试环境：创建测试项目、上传测试所需的文件、准备对话上下文。

**Why this priority**: 没有正确的执行上下文，测试无法模拟真实场景，结果不可靠。

**Independent Test**: 可以通过创建一个测试项目、上传示例文件、验证文件可用性来测试。

**Acceptance Scenarios**:

1. **Given** 用户定义了测试数据集, **When** 数据集中包含 context_files, **Then** 系统自动检查文件是否存在于测试资源目录
2. **Given** 测试文件存在, **When** 系统准备测试环境, **Then** 自动创建测试项目并上传所需文件
3. **Given** 测试项目已创建, **When** 运行测试 case, **Then** 在该项目上下文中创建对话
4. **Given** case 指定了 context_files, **When** 发送消息, **Then** 选中的文件作为对话上下文
5. **Given** 测试完成, **When** 清理环境, **Then** 可选择保留或删除测试项目

---

### User Story 1 - 测试数据集模板与创建 (Priority: P1)

用户通过填写系统提供的数据集模板来创建测试用例，模板支持指定项目上下文和文件依赖。

**Why this priority**: 没有测试数据集就无法评估 Plugin 表现，模板降低了用户创建数据集的门槛。

**Independent Test**: 可以通过下载模板、填写 5 个 case（含文件依赖）、上传并验证 Langfuse 中成功创建 Dataset 来测试。

**Acceptance Scenarios**:

1. **Given** 用户需要创建测试数据集, **When** 用户请求数据集模板, **Then** 系统提供带示例的 CSV/JSONL 模板文件（含文件上下文字段）
2. **Given** 用户填写了模板文件, **When** 用户提交数据集, **Then** 系统验证格式并检查 context_files 是否存在
3. **Given** 数据集验证通过, **When** 系统处理数据集, **Then** 自动在 Langfuse 创建对应的 Dataset
4. **Given** case 包含 context_files, **When** 查看 Langfuse Dataset Item, **Then** 能看到关联的文件信息
5. **Given** 用户需要更新数据集, **When** 用户提交新版本, **Then** 系统更新 Langfuse Dataset（增量或全量）

---

### User Story 2 - 基于 Langfuse 的评估执行 (Priority: P1)

系统通过 SunnyAgent API 执行测试，SunnyAgent 自动将执行 trace 写入 Langfuse，Meta-Agent 从 Langfuse 读取 trace 进行评分和分析。

**Why this priority**: 评估是优化循环的核心环节，必须在真实上下文中运行才能反映实际表现。

**Independent Test**: 可以通过选择一个带文件依赖的 Dataset、运行评估、并在 Langfuse 中查看评估结果来测试。

**Acceptance Scenarios**:

1. **Given** Langfuse Dataset 已存在且环境已准备, **When** 用户启动评估, **Then** 系统在测试项目中对每个 case 调用 SunnyAgent API
2. **Given** case 有 context_files, **When** 执行该 case, **Then** 文件被选中作为对话上下文传递
3. **Given** SunnyAgent 执行完成, **When** 收集响应, **Then** SunnyAgent 自动产生 trace 到 Langfuse，Meta-Agent 读取 trace 并计算各维度 score
4. **Given** 评估完成, **When** 用户查看 Langfuse, **Then** 能看到每个 case 的 trace、文件上下文、score 和通过/失败状态
5. **Given** 评估完成, **When** 系统生成报告, **Then** 包含总体分数、通过率、失败分布

---

### User Story 3 - 失败分析与改进建议 (Priority: P1)

Analyzer Agent 从 Langfuse 读取评估结果，分析失败案例（含文件上下文），生成具体的改进建议。

**Why this priority**: 失败分析是连接评估和优化的桥梁，需要考虑文件上下文对结果的影响。

**Independent Test**: 可以通过运行一次评估后，验证 Agent 能正确分类失败并给出合理的改进建议。

**Acceptance Scenarios**:

1. **Given** Langfuse 中有评估结果, **When** Analyzer Agent 运行分析, **Then** 从 Langfuse 读取失败 case 详情（含文件上下文）
2. **Given** 失败 case 已收集, **When** Analyzer Agent 分类, **Then** 将失败按类型分组，并标注是否与文件相关
3. **Given** 失败分组完成, **When** Analyzer Agent 生成建议, **Then** 每种失败类型对应具体的文件修改策略
4. **Given** 多个失败类型, **When** Analyzer Agent 确定优先级, **Then** 按影响范围和修复难度排序

---

### User Story 4 - Command/Skill 自动生成与修改 (Priority: P2)

Generator Agent 根据失败分析结果，自动生成新的 Command/Skill 或修改现有定义文件。

**Why this priority**: 这是优化循环的执行环节，依赖于评估和分析的完成。

**Independent Test**: 可以通过给定一个具体的失败案例和改进建议，验证 Agent 生成的修改符合预期。

**Acceptance Scenarios**:

1. **Given** 分析建议修改某个 Command, **When** Generator Agent 执行修改, **Then** Command 文件按照规范格式更新
2. **Given** 分析建议创建新 Skill, **When** Generator Agent 执行创建, **Then** 新的 SKILL.md 文件生成在 packages 正确位置
3. **Given** 文件被修改, **When** 修改完成, **Then** 系统自动创建 git commit 记录变更
4. **Given** 修改前的版本, **When** 需要回滚, **Then** 系统能通过 git 恢复到之前版本
5. **Given** Generator Agent 尝试修改 packages 外的文件, **When** 执行写入, **Then** 系统拒绝并报错

---

### User Story 5 - 迭代优化循环 (Priority: P2)

Orchestrator Agent 协调完整的优化循环：环境准备 → Langfuse 评估 → 分析 → 修改 → 重新评估 → 判断收敛。

**Why this priority**: 自动化循环是提高效率的关键，但需要前置功能稳定后才能实现。

**Independent Test**: 可以通过设置一个较低的目标分数和小数据集，验证完整循环能正常运行并终止。

**Acceptance Scenarios**:

1. **Given** 配置了目标分数和最大迭代次数, **When** 用户启动优化, **Then** Agent Team 自动执行循环直到满足终止条件
2. **Given** Langfuse 评估分数达到目标, **When** 迭代完成, **Then** 系统输出成功报告并停止
3. **Given** 达到最大迭代次数但未达标, **When** 迭代终止, **Then** 系统输出当前最佳结果和剩余问题
4. **Given** 连续多轮无提升, **When** patience 耗尽, **Then** 系统提前终止并提示需要人工介入
5. **Given** 每轮迭代完成, **When** 系统输出报告, **Then** 包含 Langfuse 评估链接、分数变化、本轮操作

---

### User Story 6 - 回归检测与自动回滚 (Priority: P2)

系统能够检测修改导致的回归（之前通过的 case 现在失败），并自动回滚问题修改。

**Why this priority**: 回归检测是保证优化质量的安全网，防止优化带来负面效果。

**Independent Test**: 可以通过故意引入一个导致回归的修改，验证系统能检测并回滚。

**Acceptance Scenarios**:

1. **Given** 修改后重新评估, **When** Langfuse 分数下降超过阈值, **Then** 系统标记为回归
2. **Given** 检测到回归, **When** 系统执行回滚, **Then** 通过 git revert 恢复到上一版本
3. **Given** 回滚完成, **When** 继续优化, **Then** 系统尝试不同的修复策略

---

### User Story 7 - 最终报告生成 (Priority: P3)

优化完成后，系统生成详细的最终报告，包含 Langfuse 评估历史链接和优化摘要。

**Why this priority**: 报告是优化结果的交付物，帮助用户理解和验证优化效果。

**Independent Test**: 可以在完成一轮优化后，验证生成的报告包含所有必要信息。

**Acceptance Scenarios**:

1. **Given** 优化循环结束, **When** 系统生成报告, **Then** 报告包含起始分数、最终分数、总迭代次数、Langfuse Dashboard 链接
2. **Given** 有文件变更, **When** 查看变更清单, **Then** 每个变更包含文件路径、修改内容、git commit hash
3. **Given** 优化过程有发现, **When** 查看关键发现, **Then** 包含模式分析和洞察
4. **Given** 仍有未解决问题, **When** 查看建议, **Then** 包含具体的后续改进方向

---

### Edge Cases

- 测试数据集模板格式错误时，系统应给出明确的错误提示和示例
- context_files 中指定的文件不存在时，应报错并列出缺失文件
- 测试项目创建失败时，应提示检查 SunnyAgent 服务状态
- 文件上传失败时，应重试并记录失败原因
- Langfuse 连接失败时，系统应提示检查配置并重试
- Langfuse Dataset 创建失败时，应保留本地数据以便重试
- SunnyAgent 服务不可用时，评估应优雅降级并保存已完成的结果
- 单个 case 超时时，应在 Langfuse 记录为失败并继续处理其他 case
- LLM API 速率限制时，自动重试 + 指数退避（最多 3 次），仍失败则记录并继续下一个 case
- 所有 case 都通过时，系统应直接报告成功而不进入优化循环
- Plugin 文件被外部修改时，系统应检测冲突并提示用户
- 每次只修改一个文件以便归因，避免同时修改多个导致无法判断效果
- 尝试修改 packages 目录外的文件时，必须拒绝并记录违规尝试
- 目标 Plugin 不存在时，应提示用户先创建 Plugin 结构
- 测试项目中的文件与 case 期望不匹配时，应提示并尝试修复

## Requirements *(mandatory)*

### Functional Requirements

**系统架构**:
- **FR-001**: System MUST be deployed as an independent subsystem with its own directory structure
- **FR-002**: System MUST implement a multi-agent architecture based on Claude Agent Team pattern
- **FR-003**: System MUST only modify files within the `packages/` directory
- **FR-004**: System MUST reject any write operations outside of `packages/` directory with explicit error

**测试环境准备**:
- **FR-005**: System MUST support creating test projects in SunnyAgent for evaluation
- **FR-006**: System MUST support uploading test files to project Sources
- **FR-007**: System MUST support specifying files as conversation context when running test cases
- **FR-008**: System MUST maintain a test resources directory for storing test files locally
- **FR-009**: System MUST validate that all context_files exist before running evaluation

**测试数据集模板与管理**:
- **FR-010**: System MUST provide downloadable dataset templates in CSV and JSONL formats
- **FR-011**: System MUST include example test cases in templates with all supported fields including context_files
- **FR-012**: System MUST validate user-submitted datasets and report errors with line numbers
- **FR-013**: System MUST automatically create/update Langfuse Dataset from validated local datasets
- **FR-014**: System MUST support dataset fields: case_id, input, command (metadata), expected_skill, expected_output_contains, expected_behavior, tags, context_files, project_config, conversation_history
- **FR-015**: System MUST support incremental dataset updates (add/modify cases without full replacement)
- **FR-016**: System MUST auto-increment dataset version on each update (e.g., v1, v2) and associate evaluation results with specific versions

**Langfuse 评估集成**:
- **FR-017**: System MUST reuse SunnyAgent's existing Langfuse instance (same LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
- **FR-018**: System MUST call SunnyAgent API to execute test cases; SunnyAgent automatically produces traces to Langfuse
- **FR-019**: System MUST read traces from Langfuse and calculate scores for multiple dimensions: correctness, skill_trigger, response_quality, file_context_usage
- **FR-020**: System MUST categorize failures into types: skill_not_triggered, wrong_skill_triggered, output_incorrect, output_incomplete, execution_error, timeout, file_context_error
- **FR-021**: System MUST provide Langfuse dashboard links in all reports

**评估维度说明**:
- `correctness`: 输出是否包含 expected_output_contains 中的关键词
- `skill_trigger`: Command 执行时是否正确触发了 expected_skill
- `response_quality`: LLM 根据 expected_behavior 评估整体回复质量
- `file_context_usage`: 是否正确使用了 context_files 中的文件内容

**总体分数计算**（correctness 优先）:
```
overall_score = 0.50 × correctness
              + 0.167 × skill_trigger
              + 0.167 × response_quality
              + 0.167 × file_context_usage
```

**分析功能**:
- **FR-022**: System MUST read evaluation results from Langfuse for analysis including file context
- **FR-023**: System MUST group failed cases by failure category
- **FR-024**: System MUST generate improvement suggestions for each failure category
- **FR-025**: System MUST prioritize fixes based on failure impact and frequency

**文件生成与修改**:
- **FR-026**: System MUST generate/modify Command files (`commands/*.md`) following the Command schema
- **FR-027**: System MUST generate/modify Skill files (`skills/*/SKILL.md`) following the Skill schema
- **FR-028**: System MUST generate/modify Plugin config (`plugin.json`) when needed
- **FR-029**: System MUST create git commits for each file modification
- **FR-030**: System MUST backup file versions before modification
- **FR-030a**: System MUST apply modifications automatically without human review gate (git history serves as safety net for rollback)

**优化循环**:
- **FR-031**: System MUST provide intelligent default values for all completion criteria (target_score=0.8, max_iterations=5, regression_threshold=0.05, patience=2, min_improvement=0.02)
- **FR-031a**: System MUST allow users to override any default completion criteria parameter
- **FR-032**: System MUST detect regression by comparing Langfuse evaluation scores
- **FR-033**: System MUST auto-rollback when score drops beyond threshold
- **FR-034**: System MUST terminate early when no improvement for consecutive iterations (patience)
- **FR-035**: System MUST output iteration summary with Langfuse links after each cycle
- **FR-036**: System MUST persist optimization state after each iteration for checkpoint resumption
- **FR-037**: System MUST support resuming interrupted optimization from last saved checkpoint

**报告与输出**:
- **FR-038**: System MUST generate final optimization report in Markdown format
- **FR-039**: System MUST include Langfuse dashboard/evaluation links in reports
- **FR-040**: System MUST provide clear interface for starting and resuming optimization tasks

### Dataset Template Schema

测试数据集模板包含以下字段：

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| `case_id` | string | 是 | 唯一标识，建议格式: `plugin_001` |
| `input` | string | 是 | 用户输入消息（可包含 `/command` 显式调用） |
| `command` | string | 否 | 测试的 Command 名称（元数据，用于分组统计） |
| `expected_skill` | string | 否 | 期望触发的 Skill 名称 |
| `expected_output_contains` | string[] | 否 | 输出应包含的关键词列表（JSON 数组） |
| `expected_behavior` | string | 是 | 期望行为的自然语言描述（用于 LLM 评估） |
| `tags` | string[] | 否 | 标签，用于过滤和分组（JSON 数组） |
| `context_files` | string[] | 否 | 测试时需要选中的文件（相对于测试资源目录） |
| `project_config` | object | 否 | 项目配置（见下方说明） |
| `conversation_history` | object[] | 否 | 多轮对话的历史消息（用于测试多轮场景） |

**关于 Command 调用**:

- Command 是用户**显式调用**的，通过 `/command-name` 格式包含在 `input` 中
- `command` 字段仅用于元数据标记（便于按 Command 分组分析结果）
- 示例：`input: "/complaint-analysis 分析这批投诉"` 表示用户显式调用 `complaint-analysis` 命令

**project_config 字段**:

| 子字段 | 类型 | 说明 |
|-------|------|------|
| `name` | string | 测试项目名称（默认: `meta-agent-test`） |
| `reuse` | boolean | 是否复用已存在的同名项目（默认: true） |
| `cleanup` | boolean | 测试后是否清理项目（默认: false） |

**conversation_history 字段**（用于多轮对话测试）:

| 子字段 | 类型 | 说明 |
|-------|------|------|
| `role` | string | `user` 或 `assistant` |
| `content` | string | 消息内容 |

**模板示例（JSONL）**:
```jsonl
{"case_id": "qc_001", "input": "/quality-data 分析这批产品的质量数据", "command": "quality-data", "expected_skill": "data-profiler", "expected_output_contains": ["CPK", "合格率"], "expected_behavior": "应该分析数据并返回 CPK、合格率等统计指标", "tags": ["quality", "data"], "context_files": ["test-data/quality-sample.csv"]}
{"case_id": "qc_002", "input": "这个数据有什么问题", "expected_skill": "quality-analysis", "expected_output_contains": ["异常", "建议"], "expected_behavior": "应该分析数据中的异常并给出改进建议", "tags": ["analysis"], "context_files": ["test-data/defect-report.xlsx"], "conversation_history": [{"role": "user", "content": "/quality-data 帮我检查产品质量"}, {"role": "assistant", "content": "数据已加载，请问您想了解什么？"}]}
{"case_id": "qc_003", "input": "/8d-report 写一份8D报告", "command": "8d-report", "expected_output_contains": ["问题描述", "根本原因"], "expected_behavior": "应该生成完整的8D报告模板", "tags": ["report"], "project_config": {"name": "qc-report-test", "reuse": false, "cleanup": true}}
{"case_id": "qc_004", "input": "/complaint-analysis 分析这批客户投诉数据", "command": "complaint-analysis", "expected_skill": "quality-analysis", "expected_output_contains": ["投诉原因", "帕累托"], "expected_behavior": "应该分析投诉数据并给出根因分析", "tags": ["complaint"], "context_files": ["test-data/complaints.csv"]}
```

### Test Resources Directory

测试资源目录结构：

```
meta-agent/
├── test-resources/           # 测试资源根目录
│   ├── datasets/            # 测试数据集文件
│   │   ├── qc-plugin.jsonl
│   │   └── data-plugin.jsonl
│   └── files/               # 测试所需的上下文文件
│       ├── test-data/
│       │   ├── quality-sample.csv
│       │   ├── defect-report.xlsx
│       │   └── production-log.txt
│       └── documents/
│           ├── sop-template.docx
│           └── spec-sample.pdf
```

### Agent Team Architecture

Meta-Agent 系统由以下 Agent 组成：

| Agent | 职责 | 能力 |
|-------|------|------|
| **Orchestrator** | 协调整体优化流程，管理迭代循环，判断终止条件 | 流程控制、状态管理、决策 |
| **Environment Setup** | 准备测试环境：创建项目、上传文件 | SunnyAgent API（项目、文件） |
| **Evaluator** | 调用 SunnyAgent API 执行测试，从 Langfuse 读取 trace 并计算评分 | SunnyAgent API、Langfuse 读取 API |
| **Analyzer** | 从 Langfuse 读取失败案例的 trace，分类统计，生成改进建议 | Langfuse 查询、模式识别、策略推荐 |
| **Generator** | 生成/修改 Command 和 Skill 文件 | 文件读写（仅 packages/）、格式验证 |
| **Reviewer** | 检查生成内容的质量和规范性 | 格式检查、一致性验证 |

### Key Entities

- **TestProject**: 测试项目，在 SunnyAgent 中创建，用于运行测试
- **TestFile**: 测试文件，上传到测试项目作为 Sources
- **DatasetTemplate**: 数据集模板文件，包含字段定义和示例
- **TestDataset**: 用户填写的测试数据集，验证后同步到 Langfuse，含自动版本号（v1, v2...）
- **TestCase**: 单个测试用例，包含 input、context_files、expected_* 等
- **LangfuseDataset**: Langfuse 中的 Dataset 对象，用于评估
- **LangfuseEvaluation**: Langfuse 中的评估运行，包含所有 trace 和 score
- **EvaluationResult**: 评估结果摘要，从 Langfuse 聚合而来
- **FailedCase**: 失败详情，包含 case_id、failure_category、file_context、langfuse_trace_url
- **FileVersion**: 文件版本记录，用于回滚和历史追踪
- **OptimizationConfig**: 优化配置（见下方详细说明）
- **OptimizationCheckpoint**: 优化检查点，包含 current_iteration、best_score、last_evaluation_id、modified_files、state（用于断点续跑）
- **IterationReport**: 单轮迭代报告，包含 langfuse_evaluation_url、score_delta、modifications

### OptimizationConfig 详细说明（完成准则配置）

系统采用**智能默认 + 用户可覆盖**模式，降低入门门槛的同时保留灵活性。

| 参数 | 类型 | 默认值 | 说明 | 用户可覆盖 |
|------|------|--------|------|-----------|
| `target_plugin` | string | - | 目标 Plugin 名称 | ✅ 必填 |
| `target_score` | float | 0.8 | 目标分数（0-1），达到后停止优化 | ✅ |
| `max_iterations` | int | 5 | 最大迭代次数，防止无限优化 | ✅ |
| `regression_threshold` | float | 0.05 | 回归阈值，分数下降超过此值触发回滚 | ✅ |
| `patience` | int | 2 | 耐心值，连续无提升的轮数后提前终止 | ✅ |
| `min_improvement` | float | 0.02 | 最小有效提升，低于此值视为无提升 | ✅ |

**终止条件**（满足任一即停止）：

1. **达标**: `current_score >= target_score`
2. **超限**: `current_iteration >= max_iterations`
3. **耐心耗尽**: 连续 `patience` 轮提升 < `min_improvement`

**配置示例**:

```yaml
# 默认配置（适合大多数场景）
optimization:
  target_plugin: "manufacturing-qc"
  # 以下使用智能默认值，无需指定

# 高要求场景（严格优化）
optimization:
  target_plugin: "manufacturing-qc"
  target_score: 0.9         # 更高目标
  max_iterations: 10        # 更多迭代机会
  regression_threshold: 0.02 # 更严格的回归检测

# 快速验证场景
optimization:
  target_plugin: "manufacturing-qc"
  target_score: 0.7         # 较低目标
  max_iterations: 3         # 快速验证
  patience: 1               # 无提升立即停止
```

**智能默认值的理由**：

| 默认值 | 理由 |
|--------|------|
| target_score = 0.8 | 80% 是常见的质量基准，平衡效果与可达性 |
| max_iterations = 5 | 经验表明 5 轮足以发现主要问题，避免过度优化 |
| regression_threshold = 0.05 | 5% 的下降是显著回归信号 |
| patience = 2 | 允许 1 轮波动，2 轮无提升说明达到局部最优 |
| min_improvement = 0.02 | 2% 以下的提升可能是噪声而非真实改进 |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户能在 5 分钟内使用模板创建并验证一个包含 10 个 case（含文件依赖）的测试数据集
- **SC-002**: 测试环境准备（创建项目、上传文件）在 2 分钟内完成
- **SC-003**: 数据集能在 1 分钟内同步到 Langfuse Dataset
- **SC-004**: 评估 50 个 case 的数据集在 15 分钟内完成（含文件上下文），结果全部记录到 Langfuse
- **SC-005**: 系统能自动将 Plugin 表现从 baseline 提升至少 20%（如从 0.6 提升到 0.72）
- **SC-006**: 回归检测准确率达到 95%（几乎不漏报回归问题）
- **SC-007**: 优化循环在 10 轮内收敛或明确给出无法继续优化的原因
- **SC-008**: 每轮迭代的修改都有完整的 git 记录可追溯
- **SC-009**: 所有评估结果都能在 Langfuse Dashboard 中查看（含文件上下文信息）
- **SC-010**: 系统 100% 遵守文件修改范围限制（不修改 packages 外的任何文件）

## Assumptions

- SunnyAgent 服务已部署并可通过 API 访问（含项目管理和文件上传功能）
- **测试账号**：使用 SunnyAgent 系统的 admin 账号运行测试评估
- **Langfuse 复用**：SunnyAgent 已集成 Langfuse 并正常运行，所有 Agent 执行自动产生 trace
- Meta-Agent 复用 SunnyAgent 的 Langfuse 实例（相同的 LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY）
- Meta-Agent 对 Langfuse 的操作：**写入** Dataset，**读取** trace 和评估结果
- 用户对 Plugin（Command/Skill）格式有基本了解
- 测试环境与生产环境的 Agent 行为一致
- Git 已初始化，可用于版本追踪
- 每次优化任务针对单个 Plugin，且系统同一时间只允许一个优化任务运行（单任务模式）
- LLM 调用成本在可接受范围内（用于 response_quality 评估和 Agent 协作）
- **Claude Agent Team 架构**：直接使用 Claude Agent Team 模式实现多 Agent 协作（架构详见 design-notes.md）
- 测试文件大小在 SunnyAgent 上传限制内（默认 10MB）
