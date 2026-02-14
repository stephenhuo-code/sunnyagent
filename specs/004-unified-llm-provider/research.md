# Research: Unified LLM Provider

**Date**: 2026-02-13
**Feature**: 004-unified-llm-provider

## Research Topics

### 1. litellm 与 LangChain 集成方式

**Decision**: 使用 `langchain-litellm` 包的 `ChatLiteLLM` 类

**Rationale**:
- 官方支持的集成方式
- 支持所有 litellm 支持的提供商
- 与现有 LangChain 代码兼容
- 支持流式输出

**Alternatives Considered**:
- 直接使用 litellm.completion() - 需要额外封装才能与 LangChain 工具链兼容
- 使用 init_chat_model() - 需要为每个提供商写不同的调用代码

**Code Example**:
```python
from langchain_litellm import ChatLiteLLM

# OpenAI
chat = ChatLiteLLM(model="gpt-4o", temperature=0.0)

# Anthropic
chat = ChatLiteLLM(model="claude-sonnet-4-20250514", temperature=0.0)

# DeepSeek (通过 OpenAI 兼容接口)
chat = ChatLiteLLM(
    model="deepseek/deepseek-chat",
    api_base="https://api.deepseek.com/v1",
    api_key=os.environ["DEEPSEEK_API_KEY"]
)
```

### 2. DeepSeek API 兼容性

**Decision**: DeepSeek 使用 OpenAI 兼容格式，通过 litellm 的 `openai/` 前缀或自定义 api_base 调用

**Rationale**:
- DeepSeek 官方 API 兼容 OpenAI 格式
- litellm 原生支持 DeepSeek（使用 `deepseek/` 前缀）

**Configuration**:
```python
# 方式 1: litellm 原生支持
chat = ChatLiteLLM(model="deepseek/deepseek-chat")

# 方式 2: 通过 OpenAI 兼容接口
chat = ChatLiteLLM(
    model="openai/deepseek-chat",
    api_base="https://api.deepseek.com/v1",
    api_key=os.environ["DEEPSEEK_API_KEY"]
)
```

### 3. 模型命名格式

**Decision**: 使用 litellm 的模型命名格式

**Model Mapping**:

| Provider | Agent | Model Name |
|----------|-------|------------|
| anthropic | supervisor | claude-sonnet-4-20250514 |
| anthropic | research | claude-sonnet-4-20250514 |
| anthropic | sql | claude-sonnet-4-20250514 |
| anthropic | general | claude-sonnet-4-20250514 |
| openai | supervisor | gpt-4o |
| openai | research | gpt-4o |
| openai | sql | gpt-4o-mini |
| openai | general | gpt-4o |
| deepseek | supervisor | deepseek/deepseek-chat |
| deepseek | research | deepseek/deepseek-chat |
| deepseek | sql | deepseek/deepseek-chat |
| deepseek | general | deepseek/deepseek-chat |

### 4. API 密钥环境变量

**Decision**: 使用标准环境变量名

| Provider | Environment Variable |
|----------|---------------------|
| anthropic | ANTHROPIC_API_KEY |
| openai | OPENAI_API_KEY |
| deepseek | DEEPSEEK_API_KEY |

**Validation**: 启动时检查所选提供商的密钥是否存在

### 5. 与 deepagents 库的兼容性

**Decision**: `ChatLiteLLM` 实现 `BaseChatModel` 接口，可直接传入 `create_deep_agent()`

**Evidence**: `create_deep_agent(model=...)` 参数接受任何 LangChain `BaseChatModel`

**Code Example**:
```python
from deepagents import create_deep_agent
from langchain_litellm import ChatLiteLLM

model = ChatLiteLLM(model="gpt-4o", temperature=0.0)
agent = create_deep_agent(model=model, tools=tools, system_prompt=prompt)
```

## Dependencies

### New Dependencies

```toml
# pyproject.toml
[project.dependencies]
litellm = ">=1.0.0"
langchain-litellm = ">=0.1.0"
```

### Removed Dependencies

无需移除现有依赖。`langchain.chat_models.init_chat_model` 可继续保留作为后备。

## Implementation Notes

1. **模块结构**: 创建 `backend/llm/` 目录，包含 `config.py`（预设配置）和 `factory.py`（工厂函数）

2. **工厂函数签名**:
   ```python
   def get_model(agent_name: str = "default") -> BaseChatModel:
       """获取指定 Agent 的 LLM 客户端"""
   ```

3. **配置加载顺序**:
   - 读取 `LLM_PROVIDER` 环境变量
   - 验证提供商名称有效
   - 验证对应 API 密钥存在
   - 返回预设模型配置

4. **错误处理**:
   - 无效提供商 → 启动时抛出 `ValueError`
   - 缺少 API 密钥 → 启动时抛出 `EnvironmentError`
   - 记录当前使用的提供商到日志

## Sources

- [ChatLiteLLM - LangChain Docs](https://docs.langchain.com/oss/python/integrations/chat/litellm)
- [langchain-litellm - PyPI](https://pypi.org/project/langchain-litellm/)
- [Using ChatLiteLLM - liteLLM Docs](https://docs.litellm.ai/docs/langchain/)
