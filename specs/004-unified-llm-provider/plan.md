# Implementation Plan: Unified LLM Provider

**Branch**: `004-unified-llm-provider` | **Date**: 2026-02-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-unified-llm-provider/spec.md`

## Summary

实现一键切换 LLM 提供商功能。通过 `LLM_PROVIDER` 环境变量选择提供商（anthropic/openai/deepseek），系统内置每个提供商的 Agent 模型预设配置。使用 litellm 作为统一接口，通过 `ChatLiteLLM` 与 LangChain 集成。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: litellm, langchain-litellm, FastAPI, LangGraph, deepagents
**Storage**: N/A（配置通过环境变量）
**Testing**: pytest
**Target Platform**: Linux server / macOS
**Project Type**: Web application (backend)
**Performance Goals**: 与现有性能一致（LLM 调用延迟取决于提供商）
**Constraints**: 启动时验证 API 密钥；不支持运行时切换

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Agent 隔离 | ✅ PASS | 每个 Agent 独立获取 LLM 客户端，不共享可变状态 |
| II. 注册驱动发现 | ✅ PASS | Agent 注册机制不变，仅更改 LLM 获取方式 |
| III. 流式优先 | ✅ PASS | ChatLiteLLM 支持流式输出，不影响 SSE 管线 |
| IV. 包扩展性 | ✅ PASS | 包 Agent 同样通过 `get_model()` 获取 LLM |
| V. 简洁性 | ✅ PASS | 单一环境变量配置，内置预设，无过度抽象 |
| VI. 测试优先 | ✅ PASS | 将添加配置验证和 LLM 客户端创建的单元测试 |
| VII. 分层依赖 | ✅ PASS | LLM 配置模块作为基础设施层，Agent 层调用 |
| VIII. 接口优先 | ✅ PASS | `get_model(agent_name)` 作为统一接口 |
| IX. 安全边界 | ✅ PASS | API 密钥通过环境变量读取，不在日志中暴露 |

**Gate Status**: ✅ PASS - 可以进入 Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/004-unified-llm-provider/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── llm/                     # 新增：LLM 配置模块
│   ├── __init__.py
│   ├── config.py            # 提供商配置和预设
│   └── factory.py           # get_model() 工厂函数
├── agents/
│   ├── __init__.py
│   ├── research.py          # 修改：使用 get_model("research")
│   ├── sql.py               # 修改：使用 get_model("sql")
│   ├── general.py           # 修改：使用 get_model("general")
│   └── loader.py            # 修改：使用 get_model(agent_name)
├── supervisor.py            # 修改：使用 get_model("supervisor")
└── main.py                  # 修改：启动时验证配置

tests/
└── unit/
    └── test_llm_config.py   # 新增：LLM 配置单元测试
```

**Structure Decision**: 新增 `backend/llm/` 模块作为 LLM 配置的统一入口，遵循分层依赖原则。

## Constitution Re-Check (Post-Design)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | 确认：每个 Agent 调用 `get_model()` 获取独立实例 |
| II. 注册驱动发现 | ✅ PASS | 确认：Agent 注册机制未受影响 |
| III. 流式优先 | ✅ PASS | 确认：ChatLiteLLM 支持 `astream()` |
| IV. 包扩展性 | ✅ PASS | 确认：loader.py 使用 `get_model(agent_name)` |
| V. 简洁性 | ✅ PASS | 确认：单一环境变量 + 内置预设，最小实现 |
| VI. 测试优先 | ✅ PASS | 计划：添加 test_llm_config.py |
| VII. 分层依赖 | ✅ PASS | 确认：backend/llm/ 作为基础设施层 |
| VIII. 接口优先 | ✅ PASS | 确认：contracts/llm_factory.py 定义接口 |
| IX. 安全边界 | ✅ PASS | 确认：API 密钥仅通过 os.environ 读取 |

**Post-Design Gate**: ✅ PASS - 可以进入 Phase 2 (tasks generation)

## Complexity Tracking

> 无违规需要记录
