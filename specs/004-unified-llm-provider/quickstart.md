# Quickstart: Unified LLM Provider

**Feature**: 004-unified-llm-provider

## 快速开始

### 1. 配置环境变量

在 `.env` 文件中设置提供商和 API 密钥：

```bash
# 选择提供商 (anthropic / openai / deepseek)
LLM_PROVIDER=anthropic

# 配置所选提供商的 API 密钥
ANTHROPIC_API_KEY=sk-ant-xxx
# OPENAI_API_KEY=sk-xxx
# DEEPSEEK_API_KEY=sk-xxx
```

### 2. 切换提供商

只需修改 `LLM_PROVIDER` 并确保对应的 API 密钥已配置：

```bash
# 切换到 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx

# 切换到 DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
```

### 3. 重启服务

```bash
# 重启后端服务
uv run uvicorn backend.main:app --reload --port 8008
```

## 开发者使用

### 在 Agent 中获取 LLM 客户端

```python
from backend.llm import get_model

# 获取指定 Agent 的模型
model = get_model("supervisor")
model = get_model("research")
model = get_model("sql")
model = get_model("general")

# 获取默认模型
model = get_model()  # 或 get_model("default")
```

### 在 create_deep_agent 中使用

```python
from deepagents import create_deep_agent
from backend.llm import get_model

agent = create_deep_agent(
    model=get_model("research"),
    tools=tools,
    system_prompt=prompt,
    name="research",
)
```

## 预设模型配置

| Agent | Anthropic | OpenAI | DeepSeek |
|-------|-----------|--------|----------|
| supervisor | claude-sonnet-4-20250514 | gpt-4o | deepseek-chat |
| research | claude-sonnet-4-20250514 | gpt-4o | deepseek-chat |
| sql | claude-sonnet-4-20250514 | gpt-4o-mini | deepseek-chat |
| general | claude-sonnet-4-20250514 | gpt-4o | deepseek-chat |

## 错误处理

### 无效提供商

```
ValueError: Invalid LLM_PROVIDER 'invalid'. Valid options: anthropic, openai, deepseek
```

**解决**: 检查 `LLM_PROVIDER` 环境变量拼写

### 缺少 API 密钥

```
EnvironmentError: Missing API key for provider 'openai'. Please set OPENAI_API_KEY environment variable.
```

**解决**: 确保配置了所选提供商对应的 API 密钥

## 验证配置

启动日志会显示当前使用的提供商：

```
INFO: Using LLM provider: anthropic
INFO: Models configured: supervisor=claude-sonnet-4-20250514, research=claude-sonnet-4-20250514, ...
```
