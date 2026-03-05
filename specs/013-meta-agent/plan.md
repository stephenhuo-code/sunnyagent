# Implementation Plan: Meta-Agent Plugin Optimization System

**Branch**: `013-meta-agent` | **Date**: 2026-03-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-meta-agent/spec.md`

## Summary

构建一个独立的 Meta-Agent 系统，使用 Claude Agent Team 架构实现多 Agent 协作，通过 Langfuse 管理测试数据集并读取 SunnyAgent 产生的 trace 进行评估分析，自动优化 `packages/` 目录下的 Plugin（Commands 和 Skills）直到达到目标分数或终止条件。

**核心技术方案**：
- 使用 Claude Agent Team 模式实现 Orchestrator → Evaluator → Analyzer → Generator → Reviewer 协作
- 复用 SunnyAgent 的 Langfuse 实例（写入 Dataset，读取 Trace）
- 通过 SunnyAgent API 执行测试（SunnyAgent 自动产生 trace）
- 仅修改 `packages/` 目录下的 Markdown 文件

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `anthropic` - Claude Agent Team SDK
- `langfuse` - Dataset 管理和 Trace 读取
- `httpx` / `aiohttp` - SunnyAgent API 调用
- `gitpython` - 版本控制和回滚
- `pyyaml` - 配置文件解析
- `pydantic` - 数据模型验证

**Storage**:
- 文件系统（`packages/` 目录、测试资源目录）
- Langfuse（Dataset、Trace、Score）
- 本地 YAML/JSON（优化配置、检查点）

**Testing**: pytest + pytest-asyncio
**Target Platform**: CLI 工具 / 脚本（与 SunnyAgent 并行运行）
**Project Type**: Single project（独立子系统）

**Performance Goals**:
- 5 分钟内创建 10 case 数据集
- 2 分钟内完成测试环境准备
- 15 分钟内评估 50 个 case
- 10 轮内优化收敛

**Constraints**:
- 仅修改 `packages/` 目录
- 单任务模式（同时只允许一个优化运行）
- 复用 SunnyAgent 的 Langfuse 实例
- 使用 admin 账号执行测试

**Scale/Scope**: 单个 Plugin 优化，50-100 个测试用例

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. Agent 隔离 | ✅ PASS | Meta-Agent 是独立系统，内部 Agent（Orchestrator/Evaluator/Analyzer/Generator/Reviewer）各自隔离 |
| II. 注册驱动发现 | ✅ N/A | Meta-Agent 是外部系统，通过 API 调用 SunnyAgent，不注册到 AGENT_REGISTRY |
| III. 流式优先 | ✅ N/A | Meta-Agent 是批处理优化工具，非交互式聊天；SunnyAgent 的 SSE 保持不变 |
| IV. 包扩展性 | ✅ PASS | Meta-Agent 的目标就是优化 `packages/` 下的 Plugin，完全符合此原则 |
| V. 简洁性 | ✅ PASS | 直接使用 Claude Agent Team，不引入额外框架；最小化自定义基础设施 |
| VI. 测试优先 | ✅ PASS | 系统本身就是测试和评估工具；核心组件将有单元测试覆盖 |
| VII. 分层依赖 | ✅ PASS | Meta-Agent 通过 API 调用 SunnyAgent（不直接访问数据库）；内部结构遵循分层 |
| VIII. 接口优先 | ✅ PASS | 将定义 Langfuse 集成和 Agent 间通信的契约 |
| IX. 安全边界 | ✅ PASS | 使用 admin 账号认证；仅修改 `packages/` 目录；不执行任意代码 |

**结论**: 所有适用原则均通过，可以继续 Phase 0。

## Project Structure

### Documentation (this feature)

```text
specs/013-meta-agent/
├── spec.md              # 功能规范
├── plan.md              # 本文件
├── research.md          # Phase 0: 技术研究
├── data-model.md        # Phase 1: 数据模型
├── quickstart.md        # Phase 1: 快速开始指南
├── contracts/           # Phase 1: 接口契约
├── design-notes.md      # 设计笔记（已存在）
├── templates/           # 数据集模板（已存在）
│   ├── README.md
│   ├── dataset-template.csv
│   └── dataset-template.jsonl
└── tasks.md             # Phase 2: 任务分解（/speckit.tasks 生成）
```

### Source Code (repository root)

```text
meta_agent/                      # Meta-Agent 系统根目录
├── __init__.py
├── config.py                    # 配置加载（OptimizationConfig）
├── main.py                      # CLI 入口
│
├── agents/                      # Claude Agent Team 实现
│   ├── __init__.py
│   ├── orchestrator.py          # 协调整体优化流程
│   ├── environment_setup.py     # 准备测试环境
│   ├── evaluator.py             # 执行评估、读取 trace
│   ├── analyzer.py              # 分析失败、生成建议
│   ├── generator.py             # 生成/修改 Command/Skill
│   └── reviewer.py              # 检查生成内容质量
│
├── services/                    # 业务服务层
│   ├── __init__.py
│   ├── dataset_service.py       # 数据集管理（验证、同步到 Langfuse）
│   ├── evaluation_service.py    # 评估执行（调用 SunnyAgent、计算分数）
│   ├── langfuse_client.py       # Langfuse API 封装
│   ├── sunnyagent_client.py     # SunnyAgent API 封装
│   └── file_service.py          # 文件操作（packages/ 限制）
│
├── models/                      # Pydantic 数据模型
│   ├── __init__.py
│   ├── dataset.py               # TestCase, TestDataset
│   ├── evaluation.py            # EvaluationResult, FailedCase
│   ├── optimization.py          # OptimizationConfig, Checkpoint
│   └── plugin.py                # Command, Skill 结构
│
├── utils/                       # 工具函数
│   ├── __init__.py
│   ├── git_utils.py             # Git 操作（commit, revert）
│   └── score_calculator.py      # 分数计算（加权平均）
│
└── test-resources/              # 测试资源目录
    ├── datasets/                # 测试数据集文件
    └── files/                   # 测试所需的上下文文件

tests/
├── __init__.py
├── unit/
│   ├── test_dataset_service.py
│   ├── test_evaluation_service.py
│   ├── test_score_calculator.py
│   └── test_file_service.py
├── integration/
│   ├── test_langfuse_client.py
│   ├── test_sunnyagent_client.py
│   └── test_optimization_loop.py
└── conftest.py
```

**Structure Decision**: 选择 Single Project 结构。Meta-Agent 作为独立的 CLI 工具，放在仓库根目录的 `meta_agent/` 目录下，与 SunnyAgent 的 `backend/` 和 `frontend/` 平级。测试资源目录放在 `meta_agent/test-resources/` 下。

## Complexity Tracking

> 无宪法违规需要说明。系统设计遵循简洁性原则。

| 决策 | 理由 | 备选方案及拒绝原因 |
|------|------|-------------------|
| 独立目录 `meta_agent/` | 与 SunnyAgent 主系统分离，明确边界 | 放在 `backend/` 下会模糊职责边界 |
| Claude Agent Team | spec 明确要求使用此架构 | 自定义 LangGraph 会增加复杂度 |
| 复用 Langfuse | 避免重复部署，数据一致性 | 独立 Langfuse 实例增加运维成本 |
