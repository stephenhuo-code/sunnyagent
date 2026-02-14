"""LLM configuration and factory module.

This module provides a unified interface for obtaining LLM clients
across all agents. The provider is configured via the LLM_PROVIDER
environment variable.

Usage:
    from backend.llm import get_model, validate_config

    # At startup (in main.py)
    validate_config()

    # In agents
    model = get_model("supervisor")
    model = get_model("research")
"""

from .config import LLMProvider, get_current_provider
from .factory import get_model, validate_config

__all__ = [
    "LLMProvider",
    "get_current_provider",
    "get_model",
    "validate_config",
]
