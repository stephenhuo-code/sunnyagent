"""Configuration loading for Meta-Agent system."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from meta_agent.models.optimization import OptimizationConfig


class SunnyAgentConfig(BaseModel):
    """SunnyAgent connection configuration."""

    base_url: str = "http://localhost:8008"
    admin_username: str = "admin"
    admin_password: str = ""


class LangfuseConfig(BaseModel):
    """Langfuse connection configuration."""

    public_key: str = ""
    secret_key: str = ""
    base_url: str = "http://localhost:3001"


class MetaAgentConfig(BaseModel):
    """Root configuration for Meta-Agent."""

    optimization: OptimizationConfig | None = None
    sunnyagent: SunnyAgentConfig = Field(default_factory=SunnyAgentConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)


def _resolve_env_vars(data: dict[str, Any]) -> dict[str, Any]:
    """Resolve ${ENV_VAR} placeholders in config values."""
    resolved: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_env_vars(value)
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            resolved[key] = os.environ.get(env_var, "")
        else:
            resolved[key] = value
    return resolved


def load_config(config_path: str | Path | None = None) -> MetaAgentConfig:
    """
    Load configuration from YAML file and environment variables.

    Priority (highest to lowest):
    1. Environment variables
    2. Config file values
    3. Default values

    Args:
        config_path: Path to config.yaml (optional)

    Returns:
        Loaded configuration

    Environment Variables:
        SUNNYAGENT_BASE_URL: SunnyAgent API base URL
        SUNNYAGENT_ADMIN_USERNAME: Admin username
        SUNNYAGENT_ADMIN_PASSWORD: Admin password (or ADMIN_PASSWORD)
        LANGFUSE_PUBLIC_KEY: Langfuse public key
        LANGFUSE_SECRET_KEY: Langfuse secret key
        LANGFUSE_BASE_URL: Langfuse base URL
    """
    config_data: dict[str, Any] = {}

    # Load from file if provided
    if config_path:
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                config_data = yaml.safe_load(f) or {}
            # Resolve environment variable placeholders
            config_data = _resolve_env_vars(config_data)

    # Build SunnyAgent config
    sunnyagent_data = config_data.get("sunnyagent", {})
    sunnyagent = SunnyAgentConfig(
        base_url=os.environ.get("SUNNYAGENT_BASE_URL")
        or sunnyagent_data.get("base_url")
        or "http://localhost:8008",
        admin_username=os.environ.get("SUNNYAGENT_ADMIN_USERNAME")
        or sunnyagent_data.get("admin_username")
        or "admin",
        admin_password=os.environ.get("SUNNYAGENT_ADMIN_PASSWORD")
        or os.environ.get("ADMIN_PASSWORD")
        or sunnyagent_data.get("admin_password")
        or "",
    )

    # Build Langfuse config
    langfuse_data = config_data.get("langfuse", {})
    langfuse = LangfuseConfig(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY")
        or langfuse_data.get("public_key")
        or "",
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY")
        or langfuse_data.get("secret_key")
        or "",
        base_url=os.environ.get("LANGFUSE_BASE_URL")
        or langfuse_data.get("base_url")
        or "http://localhost:3001",
    )

    # Build optimization config if present
    optimization = None
    opt_data = config_data.get("optimization")
    if opt_data and "target_plugin" in opt_data and "dataset_path" in opt_data:
        optimization = OptimizationConfig(**opt_data)

    return MetaAgentConfig(
        optimization=optimization,
        sunnyagent=sunnyagent,
        langfuse=langfuse,
    )


# Re-export for convenience
__all__ = [
    "load_config",
    "MetaAgentConfig",
    "SunnyAgentConfig",
    "LangfuseConfig",
    "OptimizationConfig",
]

# Also export OptimizationConfig at module level for backwards compatibility
OptimizationConfig = OptimizationConfig
