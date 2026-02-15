"""Rule-based classifier for explicit routing detection."""

import logging
import re
from typing import Any

from backend.aime.intent.models import IntentResult
from backend.registry import AGENT_REGISTRY

from .base import ClassifierBase

logger = logging.getLogger(__name__)


class RuleBasedClassifier(ClassifierBase):
    """Rule-based classifier for explicit routing patterns.

    Detects:
    - [ROUTE_TO: agent_name] - Explicit agent routing
    - [SKILL: skill_name] - Skill invocation (future)

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
            IntentResult with delegate action if explicit routing found
        """
        logger.debug(f"[rule_based] Checking - message='{message[:50]}...'")

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

        # Check for [SKILL: skill_name] pattern (for US4 skill integration)
        skill_match = re.search(r"\[SKILL:\s*([\w-]+)\]", message, re.IGNORECASE)
        if skill_match:
            skill_name = skill_match.group(1).lower()
            logger.info(f"[rule_based] Matched [SKILL:] pattern -> skill={skill_name}")
            # Skills trigger delegate to generic actor with skill context
            return IntentResult(
                action="delegate",
                confidence=1.0,
                capabilities=["skill_execution"],
                domain=domain or "general",
                # Note: skill_name will be handled by Planner
            )

        # No explicit routing found
        return None
