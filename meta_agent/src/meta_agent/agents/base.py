"""Base agent class for Claude Agent Team architecture."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Shared context passed between agents."""

    # Optimization info
    optimization_id: str = ""
    plugin_name: str = ""
    iteration: int = 0

    # Project info
    project_id: str = ""
    project_name: str = ""

    # File mappings
    file_id_map: dict[str, str] = field(default_factory=dict)

    # Results from previous agents
    evaluation_result: Any = None
    analysis_result: Any = None
    generation_result: Any = None

    # Metadata
    started_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result from an agent execution."""

    success: bool
    message: str = ""
    data: Any = None
    error: str | None = None
    duration_seconds: float = 0.0

    @classmethod
    def ok(cls, message: str = "Success", data: Any = None) -> "AgentResult":
        """Create a success result."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, error: str, data: Any = None) -> "AgentResult":
        """Create a failure result."""
        return cls(success=False, error=error, data=data)


T = TypeVar("T")


class BaseAgent(ABC, Generic[T]):
    """Base class for all agents in the Claude Agent Team.

    Each agent is responsible for a specific task in the optimization loop:
    - OrchestratorAgent: Coordinates the overall flow
    - EnvironmentSetupAgent: Prepares test environment
    - EvaluatorAgent: Runs tests and calculates scores
    - AnalyzerAgent: Analyzes failures and generates suggestions
    - GeneratorAgent: Creates/modifies Commands and Skills
    - ReviewerAgent: Reviews generated content quality
    """

    def __init__(
        self,
        name: str,
        description: str,
        api_key: str | None = None,
    ):
        """
        Initialize agent.

        Args:
            name: Agent name
            description: Agent description/purpose
            api_key: Anthropic API key (optional, uses env var if not provided)
        """
        self.name = name
        self.description = description
        self._client: anthropic.Anthropic | None = None
        self._api_key = api_key

    def _get_client(self) -> anthropic.Anthropic:
        """Get or create Anthropic client."""
        if self._client is None:
            if self._api_key:
                self._client = anthropic.Anthropic(api_key=self._api_key)
            else:
                self._client = anthropic.Anthropic()
        return self._client

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent's task.

        Args:
            context: Shared context with optimization state

        Returns:
            result: Agent execution result
        """
        pass

    async def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        model: str = "claude-sonnet-4-20250514",
    ) -> str:
        """
        Call Claude for text generation.

        Args:
            system_prompt: System prompt
            user_message: User message
            max_tokens: Maximum tokens to generate
            model: Model to use

        Returns:
            Generated text
        """
        client = self._get_client()

        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )

        # Extract text from response
        if message.content and len(message.content) > 0:
            content_block = message.content[0]
            if hasattr(content_block, "text"):
                return content_block.text
        return ""

    def log(self, message: str, level: str = "info") -> None:
        """Log a message with agent name prefix."""
        log_message = f"[{self.name}] {message}"
        if level == "debug":
            logger.debug(log_message)
        elif level == "warning":
            logger.warning(log_message)
        elif level == "error":
            logger.error(log_message)
        else:
            logger.info(log_message)
