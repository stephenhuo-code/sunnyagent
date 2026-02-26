"""Rule-based classifier for explicit routing detection."""

import logging
import re
from typing import Any

from backend.aime.intent.models import IntentResult
from backend.commands import COMMAND_REGISTRY
from backend.registry import AGENT_REGISTRY

from .base import ClassifierBase

logger = logging.getLogger(__name__)


class RuleBasedClassifier(ClassifierBase):
    """Rule-based classifier for explicit routing patterns.

    Detects:
    - /command - User-invocable commands (highest priority)
    - [ROUTE_TO: agent_name] - Explicit agent routing

    Priority: 0 (highest - explicit user instructions)
    """

    @property
    def name(self) -> str:
        return "rule_based"

    @property
    def priority(self) -> int:
        return 0

    async def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> IntentResult | None:
        """Check for explicit routing patterns.

        Args:
            message: User message
            context: Optional context (may contain explicit_agent from frontend)
            domain: Optional domain hint

        Returns:
            IntentResult with appropriate action type
        """
        logger.debug(f"[rule_based] Checking - message='{message[:50]}...'")

        # Check for /command pattern first (highest priority)
        if message.startswith("/"):
            parts = message.split(maxsplit=1)
            command_name = parts[0][1:]  # Remove leading "/"

            if command_name in COMMAND_REGISTRY:
                command = COMMAND_REGISTRY[command_name]
                logger.info(
                    f"[rule_based] Matched /command pattern -> "
                    f"command={command_name}, plugin={command.plugin_name}"
                )
                return IntentResult(
                    action="command",
                    confidence=1.0,
                    command_name=command_name,
                    plugin_name=command.plugin_name,
                    domain=domain or "general",
                )
            else:
                logger.debug(f"[rule_based] Unknown command: /{command_name}")
                # Fall through to other classifiers

        # Check context for frontend-selected agent
        if context and context.get("explicit_agent"):
            agent_name = context["explicit_agent"]
            logger.info(f"[rule_based] Detected explicit_agent in context: {agent_name}")
            if agent_name in AGENT_REGISTRY:
                return IntentResult(
                    action="delegate",
                    confidence=1.0,
                    explicit_agent=agent_name,
                    domain=domain or "general",
                )

        # Check for [ROUTE_TO: agent_name] pattern in message
        route_match = re.search(r"\[ROUTE_TO:\s*(\w+)\]", message, re.IGNORECASE)
        if route_match:
            agent_name = route_match.group(1).lower()
            logger.info(f"[rule_based] Matched [ROUTE_TO:] pattern -> agent={agent_name}")
            if agent_name in AGENT_REGISTRY:
                return IntentResult(
                    action="delegate",
                    confidence=1.0,
                    explicit_agent=agent_name,
                    domain=domain or "general",
                )
            # Agent not found - fall through to other classifiers

        # No explicit routing found
        return None
