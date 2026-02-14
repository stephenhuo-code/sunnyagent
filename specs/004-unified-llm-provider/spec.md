# Feature Specification: Unified LLM Provider

**Feature Branch**: `004-unified-llm-provider`
**Created**: 2026-02-13
**Status**: Draft
**Input**: "修改LLM的统一创建,支持openai和claude和deepseek"

## Overview

当前系统中 LLM 模型硬编码为 Anthropic Claude。本功能实现一键切换 LLM 提供商，系统内置每个提供商对应的 Agent 默认模型配置。

## Design Decisions

### 极简配置

用户只需在 `.env` 中设置一个变量：

```bash
LLM_PROVIDER=anthropic   # 可选: openai / anthropic / deepseek
```

### 内置预设配置

系统内置每个提供商的 Agent 模型预设，用户无需手动配置：

| Agent | anthropic | openai | deepseek |
|-------|-----------|--------|----------|
| supervisor | claude-sonnet-4-20250514 | gpt-4o | deepseek-chat |
| research | claude-sonnet-4-20250514 | gpt-4o | deepseek-chat |
| sql | claude-sonnet-4-20250514 | gpt-4o-mini | deepseek-chat |
| general | claude-sonnet-4-20250514 | gpt-4o | deepseek-chat |

### 为什么使用 litellm

- 统一接口支持所有提供商
- 兼容 LangChain (`ChatLiteLLM`)
- 统一模型命名格式

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 一键切换 LLM 提供商 (Priority: P1)

作为系统管理员，我希望通过设置一个环境变量就能切换整个系统的 LLM 提供商。

**Acceptance Scenarios**:

1. **Given** `LLM_PROVIDER=anthropic`，**When** 系统启动，**Then** 所有 Agent 使用 Claude 模型
2. **Given** `LLM_PROVIDER=openai`，**When** 系统启动，**Then** 所有 Agent 使用 OpenAI 模型
3. **Given** `LLM_PROVIDER=deepseek`，**When** 系统启动，**Then** 所有 Agent 使用 DeepSeek 模型
4. **Given** `LLM_PROVIDER` 未设置，**When** 系统启动，**Then** 默认使用 anthropic
5. **Given** 缺少所选提供商的 API 密钥，**When** 系统启动，**Then** 报错并提示需要哪个密钥

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须通过 `LLM_PROVIDER` 环境变量选择提供商（openai/anthropic/deepseek）
- **FR-002**: 系统必须内置每个提供商的 Agent 模型预设
- **FR-003**: 系统必须使用 litellm 作为统一 LLM 调用接口
- **FR-004**: 系统必须提供统一函数 `get_model(agent_name)` 获取 LLM 客户端
- **FR-005**: 缺少 API 密钥时必须启动报错

### 环境变量

```bash
# .env
LLM_PROVIDER=anthropic   # openai / anthropic / deepseek

# API 密钥 (根据所选提供商配置)
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
```

## Success Criteria *(mandatory)*

- **SC-001**: 修改一个环境变量即可切换所有 Agent 的提供商
- **SC-002**: 切换提供商后所有功能正常工作
- **SC-003**: 无需额外配置

## Out of Scope

- 自定义每个 Agent 的模型
- 运行时动态切换
- Web UI 配置
