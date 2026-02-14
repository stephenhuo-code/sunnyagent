"""LLM factory for creating model instances.

This module provides the get_model() function that agents use to obtain
their LLM client based on the configured provider.
"""

import logging
import os

from langchain_core.language_models import BaseChatModel
from langchain_litellm import ChatLiteLLM

from .config import (
    LLMProvider,
    get_current_provider,
    get_provider_config,
)

logger = logging.getLogger(__name__)

# Cache for validated state
_validated = False


def validate_config() -> None:
    """Validate the current LLM configuration.

    This should be called at application startup to fail fast if
    configuration is invalid.

    Raises:
        ValueError: If LLM_PROVIDER is invalid.
        EnvironmentError: If required API key is missing.
    """
    global _validated

    # Get current provider (raises ValueError if invalid)
    provider = get_current_provider()
    config = get_provider_config(provider)

    # Check API key exists
    api_key_env = config["api_key_env"]
    api_key = os.environ.get(api_key_env)

    if not api_key:
        raise EnvironmentError(
            f"Missing API key for provider '{provider.value}'. "
            f"Please set {api_key_env} environment variable."
        )

    print(f"[LLM] Configuration validated: provider={provider.value}, models={config['models']}")
    logger.info(f"LLM configuration validated: provider={provider.value}")
    _validated = True


def get_model(agent_name: str = "default") -> BaseChatModel:
    """Get the LLM client for a specific agent.

    This is the primary interface for agents to obtain their LLM client.
    The model returned is based on the current LLM_PROVIDER setting and
    the built-in presets for each agent.

    Args:
        agent_name: Name of the agent (e.g., "supervisor", "research", "sql", "general").
                   Falls back to "default" if not found in presets.

    Returns:
        A LangChain BaseChatModel instance (ChatLiteLLM) configured for
        the current provider.

    Raises:
        ValueError: If LLM_PROVIDER is invalid.
        EnvironmentError: If required API key is missing.

    Example:
        >>> from backend.llm import get_model
        >>> model = get_model("supervisor")
        >>> # Use model with LangChain/LangGraph
    """
    provider = get_current_provider()
    config = get_provider_config(provider)

    # Get model name for this agent, fallback to default
    models = config["models"]
    model_name = models.get(agent_name, models["default"])
    temperature = config["default_temperature"]
    api_base = config.get("api_base")

    print(f"[LLM] Creating model for '{agent_name}': provider={provider.value}, model={model_name}")
    logger.info(
        f"Creating LLM for agent '{agent_name}': "
        f"provider={provider.value}, model={model_name}, api_base={api_base}"
    )

    # Get API key from configured environment variable
    api_key_env = config["api_key_env"]
    api_key = os.environ.get(api_key_env)

    # Build kwargs for ChatLiteLLM
    kwargs: dict = {
        "model": model_name,
        "temperature": temperature,
        "api_key": api_key,  # Always pass API key explicitly
    }

    # For custom endpoints with OpenAI-compatible API format
    if api_base:
        kwargs["api_base"] = api_base              # Custom endpoint URL
        kwargs["custom_llm_provider"] = "openai"   # Use OpenAI-compatible protocol

    return ChatLiteLLM(**kwargs)
