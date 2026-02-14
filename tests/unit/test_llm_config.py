"""Unit tests for LLM configuration and factory."""

import os
from unittest.mock import patch

import pytest

from backend.llm import LLMProvider, get_current_provider, get_model, validate_config
from backend.llm.config import PROVIDER_PRESETS, get_provider_config


class TestLLMProvider:
    """Tests for LLMProvider enum."""

    def test_provider_values(self):
        """Test that all expected providers are defined."""
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.DEEPSEEK.value == "deepseek"

    def test_provider_from_string(self):
        """Test creating provider from string value."""
        assert LLMProvider("anthropic") == LLMProvider.ANTHROPIC
        assert LLMProvider("openai") == LLMProvider.OPENAI
        assert LLMProvider("deepseek") == LLMProvider.DEEPSEEK


class TestProviderPresets:
    """Tests for provider preset configurations."""

    def test_all_providers_have_presets(self):
        """Test that all providers have preset configurations."""
        for provider in LLMProvider:
            assert provider in PROVIDER_PRESETS
            config = PROVIDER_PRESETS[provider]
            assert "api_key_env" in config
            assert "models" in config
            assert "default_temperature" in config

    def test_all_presets_have_required_agents(self):
        """Test that all presets have models for required agents."""
        required_agents = ["supervisor", "research", "sql", "general", "default"]
        for provider in LLMProvider:
            config = PROVIDER_PRESETS[provider]
            for agent in required_agents:
                assert agent in config["models"], f"{provider} missing model for {agent}"


class TestGetCurrentProvider:
    """Tests for get_current_provider function."""

    def test_default_provider_when_not_set(self):
        """Test that default provider is anthropic when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove LLM_PROVIDER if it exists
            os.environ.pop("LLM_PROVIDER", None)
            provider = get_current_provider()
            assert provider == LLMProvider.ANTHROPIC

    def test_provider_from_env_anthropic(self):
        """Test getting anthropic provider from env."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
            provider = get_current_provider()
            assert provider == LLMProvider.ANTHROPIC

    def test_provider_from_env_openai(self):
        """Test getting openai provider from env."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            provider = get_current_provider()
            assert provider == LLMProvider.OPENAI

    def test_provider_from_env_deepseek(self):
        """Test getting deepseek provider from env."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek"}):
            provider = get_current_provider()
            assert provider == LLMProvider.DEEPSEEK

    def test_provider_case_insensitive(self):
        """Test that provider name is case insensitive."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "OPENAI"}):
            provider = get_current_provider()
            assert provider == LLMProvider.OPENAI

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "invalid"}):
            with pytest.raises(ValueError) as exc_info:
                get_current_provider()
            assert "Invalid LLM_PROVIDER" in str(exc_info.value)
            assert "invalid" in str(exc_info.value)


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config_anthropic(self):
        """Test validation passes with valid anthropic config."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
        ):
            # Should not raise
            validate_config()

    def test_valid_config_openai(self):
        """Test validation passes with valid openai config."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"},
        ):
            validate_config()

    def test_valid_config_deepseek(self):
        """Test validation passes with valid deepseek config."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "test-key"},
        ):
            validate_config()

    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises EnvironmentError."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(EnvironmentError) as exc_info:
                validate_config()
            assert "Missing API key" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "invalid"}):
            with pytest.raises(ValueError):
                validate_config()


class TestGetModel:
    """Tests for get_model function."""

    def test_get_model_returns_chat_model(self):
        """Test that get_model returns a ChatLiteLLM instance."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
        ):
            model = get_model("supervisor")
            # Check it's a ChatLiteLLM (or at least has the expected interface)
            assert hasattr(model, "invoke")
            assert hasattr(model, "ainvoke")

    def test_get_model_default_agent(self):
        """Test get_model with default agent name."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"},
        ):
            model = get_model()
            assert model is not None

    def test_get_model_unknown_agent_uses_default(self):
        """Test that unknown agent name falls back to default model."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
        ):
            model = get_model("unknown_agent")
            # Should not raise, uses default model
            assert model is not None

    def test_get_model_for_each_agent(self):
        """Test get_model works for all known agents."""
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
        ):
            for agent in ["supervisor", "research", "sql", "general"]:
                model = get_model(agent)
                assert model is not None
