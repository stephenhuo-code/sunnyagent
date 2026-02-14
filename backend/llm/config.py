"""LLM provider configuration and presets.

This module defines the supported LLM providers and their model presets.
"""

import logging
import os
from enum import Enum
from typing import TypedDict

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"                  # Native (api.deepseek.com)
    DEEPSEEK_GATEWAY = "deepseek_gateway"  # Gateway (volceapi.com)


class ProviderConfig(TypedDict):
    """Configuration for an LLM provider."""

    api_key_env: str
    api_base: str | None  # Base URL for the API (None = use litellm default)
    models: dict[str, str]
    default_temperature: float


# Built-in provider presets - users don't need to configure these
PROVIDER_PRESETS: dict[LLMProvider, ProviderConfig] = {
    LLMProvider.ANTHROPIC: {
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_base": None,  # Use litellm default
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
        "api_base": None,  # Use litellm default
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
        "api_base": None,  # Use LiteLLM default (api.deepseek.com)
        "models": {
            # deepseek/ prefix for LiteLLM native support
            "supervisor": "deepseek/deepseek-chat",
            "research": "deepseek/deepseek-chat",
            "sql": "deepseek/deepseek-chat",
            "general": "deepseek/deepseek-chat",
            "default": "deepseek/deepseek-chat",
        },
        "default_temperature": 0.0,
    },
    LLMProvider.DEEPSEEK_GATEWAY: {
        "api_key_env": "DEEPSEEK_GATEWAY_API_KEY",
        "api_base": "https://sd006c45baeogm6blrt20.apigateway-cn-beijing.volceapi.com/mlp/s-20250416230559-mb6qq/v1",
        "models": {
            # Model name expected by the OpenAI-compatible gateway
            "supervisor": "deepseek-ai/DeepSeek-V3",
            "research": "deepseek-ai/DeepSeek-V3",
            "sql": "deepseek-ai/DeepSeek-V3",
            "general": "deepseek-ai/DeepSeek-V3",
            "default": "deepseek-ai/DeepSeek-V3",
        },
        "default_temperature": 0.0,
    },
}

# Default provider if LLM_PROVIDER is not set
DEFAULT_PROVIDER = LLMProvider.ANTHROPIC


def get_current_provider() -> LLMProvider:
    """Get the currently configured LLM provider from environment.

    Returns:
        The LLMProvider enum value for the current configuration.

    Raises:
        ValueError: If LLM_PROVIDER environment variable has an invalid value.
    """
    provider_str = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER.value).lower()

    try:
        return LLMProvider(provider_str)
    except ValueError:
        valid_providers = ", ".join(p.value for p in LLMProvider)
        raise ValueError(
            f"Invalid LLM_PROVIDER '{provider_str}'. Valid options: {valid_providers}"
        )


def get_provider_config(provider: LLMProvider | None = None) -> ProviderConfig:
    """Get the configuration for a provider.

    Args:
        provider: The provider to get config for. If None, uses current provider.

    Returns:
        The ProviderConfig for the specified provider.
    """
    if provider is None:
        provider = get_current_provider()
    return PROVIDER_PRESETS[provider]
