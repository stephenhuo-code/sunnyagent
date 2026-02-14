# Data Model: Unified LLM Provider

**Date**: 2026-02-13
**Feature**: 004-unified-llm-provider

## Overview

本功能不涉及数据库存储，所有配置通过环境变量和代码内置预设完成。

## Configuration Entities

### LLMProvider (Enum)

表示支持的 LLM 提供商。

```python
class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
```

### ProviderConfig (TypedDict)

每个提供商的配置信息。

| Field | Type | Description |
|-------|------|-------------|
| api_key_env | str | API 密钥的环境变量名 |
| models | dict[str, str] | Agent 名称到模型名称的映射 |
| default_temperature | float | 默认 temperature 参数 |

### Model Presets (Constants)

内置的提供商预设配置。

```python
PROVIDER_PRESETS: dict[LLMProvider, ProviderConfig] = {
    LLMProvider.ANTHROPIC: {
        "api_key_env": "ANTHROPIC_API_KEY",
        "models": {
            "supervisor": "claude-sonnet-4-20250514",
            "research": "claude-sonnet-4-20250514",
            "sql": "claude-sonnet-4-20250514",
            "general": "claude-sonnet-4-20250514",
            "default": "claude-sonnet-4-20250514",
        },
        "default_temperature": 0.0,
    },
    LLMProvider.OPENAI: {
        "api_key_env": "OPENAI_API_KEY",
        "models": {
            "supervisor": "gpt-4o",
            "research": "gpt-4o",
            "sql": "gpt-4o-mini",
            "general": "gpt-4o",
            "default": "gpt-4o",
        },
        "default_temperature": 0.0,
    },
    LLMProvider.DEEPSEEK: {
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": {
            "supervisor": "deepseek/deepseek-chat",
            "research": "deepseek/deepseek-chat",
            "sql": "deepseek/deepseek-chat",
            "general": "deepseek/deepseek-chat",
            "default": "deepseek/deepseek-chat",
        },
        "default_temperature": 0.0,
    },
}
```

## State Transitions

无状态转换。配置在启动时加载，运行期间不变。

## Validation Rules

1. `LLM_PROVIDER` 必须是 `anthropic`、`openai` 或 `deepseek` 之一
2. 所选提供商对应的 API 密钥环境变量必须存在且非空
3. Agent 名称必须在预设配置中存在（否则使用 `default`）

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| LLM_PROVIDER | No | anthropic | 选择的 LLM 提供商 |
| ANTHROPIC_API_KEY | If provider=anthropic | - | Anthropic API 密钥 |
| OPENAI_API_KEY | If provider=openai | - | OpenAI API 密钥 |
| DEEPSEEK_API_KEY | If provider=deepseek | - | DeepSeek API 密钥 |
