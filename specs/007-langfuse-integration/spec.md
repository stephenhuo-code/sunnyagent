# Feature Specification: Langfuse 可观测性集成

**Feature Branch**: `007-langfuse-integration`
**Created**: 2026-02-19
**Status**: Draft
**Input**: User description: "集成 Langfuse 进行可观测性管理，改动现有 Agent 代码，监控 Agent 运行状态，并支持测试数据集管理和评估"

## Clarifications

### Session 2026-02-19

- Q: SunnyAgent 与 Langfuse 的账号同步采用哪种方案？ → A: Admin API 方案（SunnyAgent 用户 CRUD 时调用 Langfuse API 同步账号）
- Q: 管理员点击 Langfuse 链接时，界面如何打开？ → A: 新窗口打开（在新标签页打开 Langfuse 完整界面）

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 查看 Agent 执行链路追踪 (Priority: P1)

作为运维人员，我希望能够查看每次 Agent 调用的完整执行链路，包括意图识别、任务规划、Actor 执行等各阶段的详细信息，以便快速定位问题和优化性能。

**Why this priority**: Agent 执行链路追踪是可观测性的核心功能，直接影响问题排查效率和系统优化能力。没有 Trace 功能，其他监控功能将缺乏上下文。

**Independent Test**: 可以通过发起一次对话请求，然后在 Langfuse 界面中查看完整的 Trace 记录来独立测试此功能。

**Acceptance Scenarios**:

1. **Given** 用户发送一条消息触发 Agent 执行, **When** Agent 处理完成, **Then** 系统通过 LangGraph Callback 自动记录完整的执行 Trace，包含各阶段耗时和关键参数
2. **Given** 运维人员打开 Langfuse 界面, **When** 选择某次对话的 Trace, **Then** 可以看到从用户输入到最终输出的完整调用链路（包括 AIME 各组件）
3. **Given** Agent 执行过程中发生错误, **When** 查看该次执行的 Trace, **Then** 错误位置和错误信息清晰标注

---

### User Story 2 - 监控 Agent 运行状态和性能指标 (Priority: P1)

作为运维人员，我希望能够实时监控所有 Agent 的运行状态、调用次数、平均响应时间、Token 消耗等关键指标，以便及时发现异常并采取措施。

**Why this priority**: 实时监控是保障系统稳定运行的基础，与 Trace 功能同等重要，共同构成可观测性的核心。

**Independent Test**: 可以通过查看 Langfuse 的监控仪表盘，验证各项指标是否正常显示和更新。

**Acceptance Scenarios**:

1. **Given** 系统正常运行, **When** 打开 Langfuse 仪表盘, **Then** 可以看到各 Agent 的调用次数、成功率、平均响应时间、Token 消耗等指标
2. **Given** 某 Agent 响应时间异常, **When** 查看监控界面, **Then** 可以快速定位到问题 Trace
3. **Given** 系统运行一段时间后, **When** 查看趋势图, **Then** 可以看到历史指标变化趋势和成本分析

---

### User Story 3 - 管理测试数据集并评估 Agent (Priority: P2)

作为开发人员，我希望能够创建测试数据集，并通过自定义评估函数调用真实的 SunnyAgent Agent 进行评估，以确保 Agent 性能持续改进。

**Why this priority**: 测试数据集管理和 Agent 评估是持续优化的基础，但在基础监控功能就绪后才能发挥最大价值。

**Independent Test**: 可以通过在 Langfuse 中创建测试数据集、编写评估脚本调用 SunnyAgent `/api/chat`、查看评估结果来独立验证此功能。

**Acceptance Scenarios**:

1. **Given** 开发人员需要创建测试数据集, **When** 在 Langfuse 界面或通过 SDK 创建数据集, **Then** 系统创建空的测试数据集
2. **Given** 已有测试数据集, **When** 通过 UI/SDK/CSV 导入测试用例（输入-期望输出对）, **Then** 测试用例被添加到数据集中
3. **Given** 测试数据集包含多个测试用例, **When** 运行 Experiment（自定义任务函数调用 `/api/chat`）, **Then** 系统逐一调用真实 Agent 并记录实际输出
4. **Given** 评估完成, **When** 配置 LLM-as-a-Judge 评估器, **Then** 系统自动对比期望输出和实际输出并给出评分

---

### User Story 4 - 使用 Prompt Playground 调试 (Priority: P3)

作为开发人员，我希望能够在 Langfuse Prompt Playground 中快速测试 LLM 和 Tool Calling，以便优化 Prompt 设计。

**Why this priority**: Playground 主要用于测试 LLM 层面的 Prompt，对于完整 Agent 测试优先使用 Dataset + Experiment 方式。

**Independent Test**: 可以通过在 Playground 中输入 Prompt 和测试消息，查看 LLM 输出结果来独立测试。

**Acceptance Scenarios**:

1. **Given** 开发人员打开 Langfuse Prompt Playground, **When** 输入系统 Prompt 和用户消息, **Then** 可以即时看到配置的 LLM 响应
2. **Given** 需要测试 Tool Calling, **When** 定义工具 JSON Schema 并执行, **Then** 可以看到 LLM 的工具调用结果
3. **Given** 从 Trace 中发现需要优化的 Prompt, **When** 在 Playground 中打开该 Trace 对应的输入, **Then** 可以快速迭代优化

---

### User Story 5 - 从系统管理访问 Langfuse (Priority: P1)

作为管理员，我希望能够从 SunnyAgent 的系统管理界面直接访问 Langfuse，并使用 SunnyAgent 账号登录，无需单独管理 Langfuse 账号。

**Why this priority**: 统一入口和账号管理是提升运维体验的关键，避免多系统账号管理的复杂性。

**Independent Test**: 可以通过在系统管理界面点击 Langfuse 链接，验证是否能直接打开 Langfuse 并自动登录。

**Acceptance Scenarios**:

1. **Given** 管理员已登录 SunnyAgent, **When** 打开系统管理页面, **Then** 可以看到 Langfuse 可观测性平台的入口链接
2. **Given** 管理员点击 Langfuse 链接, **When** 跳转到 Langfuse 界面, **Then** 自动使用 SunnyAgent 账号登录，无需再次输入密码
3. **Given** SunnyAgent 创建新用户, **When** 该用户首次访问 Langfuse, **Then** Langfuse 自动创建对应账号
4. **Given** SunnyAgent 禁用某用户, **When** 该用户尝试访问 Langfuse, **Then** Langfuse 拒绝访问

---

### Edge Cases

- 当 Langfuse 服务不可用时，Agent 应继续正常工作，Trace 数据异步上报失败后丢弃（不阻塞主流程）
- 当 Langfuse 服务不可用时，系统管理界面的 Langfuse 链接应显示服务不可用状态
- 当 Trace 数据量过大时，Langfuse 支持采样策略配置
- 当测试数据集为空时运行评估，应给出友好提示
- 当 Agent 执行超时时，Trace 应记录已完成的部分和超时信息
- 当评估任务函数调用 `/api/chat` 失败时，应记录错误并继续下一个测试用例

## Requirements *(mandatory)*

### Functional Requirements

**Trace 追踪（P1）**
- **FR-001**: 系统 MUST 通过 Langfuse LangChain/LangGraph Callback 自动记录 Agent 执行链路
- **FR-002**: 系统 MUST 记录 AIME 核心组件（IntentAnalyzer、Planner、ActorFactory、Actor）的执行信息作为 Span
- **FR-003**: 系统 MUST 记录每个执行阶段的耗时、输入参数、输出结果、Token 消耗
- **FR-004**: 系统 MUST 在 Agent 执行出错时记录错误类型、错误位置和堆栈信息
- **FR-005**: 系统 MUST 支持通过环境变量配置 Langfuse 服务地址和认证信息
- **FR-006**: 系统 MUST 在 Langfuse 不可用时不影响 Agent 正常运行（异步上报 + 优雅降级）

**监控仪表盘（P1）**
- **FR-007**: 系统 MUST 利用 Langfuse 内置仪表盘展示 Agent 运行状态和性能指标

**测试数据集与评估（P2）**
- **FR-008**: 系统 MUST 支持通过 Langfuse UI/SDK 创建、查看、编辑、删除测试数据集
- **FR-009**: 系统 MUST 支持向测试数据集添加测试用例（包含输入和期望输出）
- **FR-010**: 系统 MUST 支持编写自定义评估脚本，在 Experiment 中调用 SunnyAgent `/api/chat` 进行真实 Agent 测试
- **FR-011**: 系统 MUST 支持 LLM-as-a-Judge 评估方式，自动对比期望输出和实际输出

**Prompt Playground（P3）**
- **FR-012**: 系统 MUST 支持在 Langfuse Playground 中测试 LLM 和 Tool Calling

**系统管理集成（P1）**
- **FR-013**: 系统 MUST 在系统管理界面提供 Langfuse 可观测性平台的入口链接
- **FR-014**: 系统 MUST 支持配置 Langfuse 服务地址（用于生成跳转链接）
- **FR-015**: 系统 MUST 实现 SunnyAgent 与 Langfuse 的账号同步，用户使用 SunnyAgent 账号即可访问 Langfuse
- **FR-016**: 系统 MUST 在 SunnyAgent 创建用户时自动在 Langfuse 创建对应账号
- **FR-017**: 系统 MUST 在 SunnyAgent 禁用用户时同步禁用 Langfuse 账号访问权限

### Key Entities

- **Trace**: 表示一次完整的 Agent 执行记录，包含多个 Span，由 Langfuse 自动采集
- **Span**: 表示执行链路中的一个阶段（如意图识别、任务规划、Actor 执行），包含名称、耗时、状态、输入输出
- **Dataset**: Langfuse 测试数据集，包含名称、描述、创建时间、数据集项列表
- **DatasetItem**: 数据集项，包含输入（input）、期望输出（expected_output）、元数据
- **Experiment**: 一次评估运行，关联数据集版本，记录每个测试用例的实际输出和评分
- **Score**: 评估得分，支持 LLM-as-a-Judge、人工标注、自定义评分

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 运维人员可在 10 秒内从 Langfuse 界面找到任意一次对话的完整执行链路
- **SC-002**: 95% 的 Agent 调用的 Trace 数据成功上报到 Langfuse
- **SC-003**: Trace 数据上报（异步）不增加 Agent 主流程响应时间超过 10ms
- **SC-004**: 开发人员可在 5 分钟内通过 UI 或 SDK 创建一个包含 10 个测试用例的数据集
- **SC-005**: 系统支持同时运行 100 个测试用例的批量评估（Experiment）
- **SC-006**: 监控仪表盘数据延迟不超过 30 秒
- **SC-007**: 当 Langfuse 服务不可用时，Agent 响应时间不受影响
- **SC-008**: 管理员可从系统管理界面一键跳转到 Langfuse，无需再次登录
- **SC-009**: SunnyAgent 创建/禁用用户后，Langfuse 账号状态在 5 秒内同步完成

## Assumptions

- Langfuse 服务将被私有化部署
- 团队成员可以访问 Langfuse 的 Web 界面（英文界面，数据内容支持中文）
- 现有 Agent 代码基于 LangChain/LangGraph 框架，Langfuse 提供原生 Callback 支持
- 评估脚本通过 Langfuse Python SDK 编写，调用 SunnyAgent `/api/chat` 接口
- Langfuse Playground 用于 LLM 层面调试，完整 Agent 测试使用 Dataset + Experiment

## Dependencies

### Langfuse Server v3 基础设施

> **重要**：Langfuse Server v3 不再仅依赖 PostgreSQL，需要以下完整基础设施栈：

| 组件 | 镜像 | 用途 | 必需 |
|------|------|------|------|
| **ClickHouse** | `clickhouse/clickhouse-server:24.3` | OLAP 分析引擎，存储 Trace/Span 数据 | ✅ 是 |
| **Redis** | `redis:7-alpine` | 缓存层，队列处理 | ✅ 是 |
| **MinIO** | `minio/minio:latest` | S3 兼容对象存储，存储大型事件数据 | ✅ 是 |
| **PostgreSQL** | `postgres:15` | 元数据存储（用户、项目、配置） | ✅ 是 |
| **Langfuse** | `langfuse/langfuse:3` | 主服务 | ✅ 是 |

### SDK 版本要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Langfuse Server | `≥ 3.63.0` | SDK v3 所需的最低服务端版本 |
| Langfuse Python SDK | `≥ 3.0.0` | 基于 OpenTelemetry 的新版 SDK |

> ⚠️ **版本兼容性**：SDK v3 与 Server v2 **不兼容**，必须使用 Server v3。

### 其他依赖

- Langfuse Admin API 可用（用于账号同步）
- SunnyAgent `/api/chat` 接口稳定可用（用于评估）
- 现有 AIME Agent 核心代码支持添加 Langfuse Callback
- SunnyAgent 前端系统管理页面存在（用于嵌入 Langfuse 链接）

## Architecture Decisions

1. **部署方式**: Langfuse v3 使用 Docker Compose 部署，包含 ClickHouse + Redis + MinIO + PostgreSQL 完整栈
2. **Trace 集成**: 使用 Langfuse 原生的 LangChain/LangGraph Callback，几乎零代码改动
3. **Agent 评估**: 不使用 Langfuse Playground 测试完整 Agent，而是通过 Dataset + Experiment + 自定义任务函数调用 `/api/chat`
4. **LLM-as-a-Judge**: 评估时复用 SunnyAgent 已配置的 LLM（通过环境变量），无需在 Langfuse 单独配置
5. **账号同步方案**: 采用 Admin API 方案 — SunnyAgent 用户 CRUD 操作时调用 Langfuse Instance Management API 同步账号（创建、禁用、删除）
6. **系统管理集成**: 在 SunnyAgent 管理后台添加 Langfuse 外链，点击后在新窗口（新标签页）打开 Langfuse 完整界面
7. **Span 处理模式**: 在 async generator 中使用直接 span 引用（`start_span()`/`start_generation()`）而非上下文管理器，避免 OpenTelemetry context 丢失问题（详见 research.md）
