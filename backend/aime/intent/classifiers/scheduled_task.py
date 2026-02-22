"""Scheduled task intent classifier.

Detects schedule-related keywords and patterns in user messages
for creating scheduled tasks from chat.
"""

import logging
from typing import Any

from backend.aime.intent.models import IntentResult
from backend.scheduled_tasks.intent_parser import detect_schedule_intent, parse_schedule_intent

from .base import ClassifierBase

logger = logging.getLogger(__name__)


class ScheduledTaskClassifier(ClassifierBase):
    """Classifier for scheduled task creation intent.

    Detects schedule-related keywords and patterns such as:
    - "每天早上9点执行：分析今日新闻"
    - "每周一提醒我开会"
    - "明天下午3点提醒我打电话"

    Priority: 5 (after rule-based, before LLM)
    """

    @property
    def name(self) -> str:
        return "scheduled_task"

    @property
    def priority(self) -> int:
        return 5

    async def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> IntentResult | None:
        """Check for schedule task patterns.

        Args:
            message: User message
            context: Optional context
            domain: Optional domain hint

        Returns:
            IntentResult with schedule_task action if schedule intent detected
        """
        logger.debug(f"[scheduled_task] Checking - message='{message[:50]}...'")

        # Quick check for schedule-related keywords
        if not detect_schedule_intent(message):
            return None

        # Parse the schedule intent to extract details
        parsed = parse_schedule_intent(message)
        if parsed is None:
            # Has keywords but couldn't parse - let other classifiers handle
            logger.debug("[scheduled_task] Has keywords but parse failed, passing to next")
            return None

        logger.info(
            f"[scheduled_task] Detected schedule intent - "
            f"type={parsed.schedule_type}, prompt='{parsed.prompt[:50]}...'"
        )

        # Return schedule_task action with parsed details
        # Note: We use a custom action that will be handled by the planner
        return IntentResult(
            action="schedule_task",  # type: ignore[arg-type]
            confidence=0.9,
            domain=domain or "scheduling",
            capabilities=["scheduling"],
        )
