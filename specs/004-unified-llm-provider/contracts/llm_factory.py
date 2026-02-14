"""LLM Factory Interface Contract

This module defines the interface for the LLM factory functions.
Implementation must conform to this contract.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import TypedDict

from langchain_core.language_models import BaseChatModel


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


class ProviderConfig(TypedDict):
    """Configuration for an LLM provider."""

    api_key_env: str
    models: dict[str, str]
    default_temperature: float


class ILLMFactory(ABC):
    """Interface for LLM factory."""

    @abstractmethod
    def get_model(self, agent_name: str = "default") -> BaseChatModel:
        """Get the LLM client for a specific agent.

        Args:
            agent_name: Name of the agent (e.g., "supervisor", "research", "sql", "general").
                       Falls back to "default" if not found.

        Returns:
            A LangChain BaseChatModel instance configured for the current provider.

        Raises:
            ValueError: If LLM_PROVIDER is invalid.
            EnvironmentError: If required API key is missing.
        """
        pass

    @abstractmethod
    def get_current_provider(self) -> LLMProvider:
        """Get the currently configured provider.

        Returns:
            The LLMProvider enum value for the current configuration.
        """
        pass

    @abstractmethod
    def validate_config(self) -> None:
        """Validate the current configuration.

        Raises:
            ValueError: If LLM_PROVIDER is invalid.
            EnvironmentError: If required API key is missing.
        """
        pass


# Module-level convenience function signature
def get_model(agent_name: str = "default") -> BaseChatModel:
    """Get the LLM client for a specific agent.

    This is the primary interface for agents to obtain their LLM client.

    Usage:
        from backend.llm import get_model

        model = get_model("supervisor")
        # or
        model = get_model("research")

    Args:
        agent_name: Name of the agent. Valid values:
            - "supervisor": Router/supervisor agent
            - "research": Web research agent
            - "sql": SQL database agent
            - "general": General fallback agent
            - "default": Default configuration (fallback)

    Returns:
        A configured LangChain BaseChatModel instance.
    """
    ...
