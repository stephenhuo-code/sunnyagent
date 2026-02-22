"""Intent Analyzer - orchestrates classifier chain for intent analysis."""

import logging
from typing import TYPE_CHECKING, Any

from backend.aime.intent.classifiers.base import ClassifierBase
from backend.aime.intent.classifiers.llm_based import LLMClassifier
from backend.aime.intent.classifiers.rule_based import RuleBasedClassifier
from backend.aime.intent.classifiers.scheduled_task import ScheduledTaskClassifier
from backend.aime.intent.models import IntentResult
from backend.services.langfuse_service import get_langfuse_service

if TYPE_CHECKING:
    from backend.aime.context import AgentContext

logger = logging.getLogger(__name__)


class IntentAnalyzer:
    """Orchestrates intent analysis through classifier chain.

    Classifiers are executed in priority order (lower priority = higher precedence):
    1. RuleBasedClassifier (priority=0) - Explicit routing patterns
    2. LLMClassifier (priority=10) - Semantic analysis with context awareness

    Each classifier returns IntentResult or None. First non-None result is used.
    If all classifiers return None, defaults to direct_reply with low confidence.
    """

    def __init__(self, classifiers: list[ClassifierBase] | None = None):
        """Initialize with classifier chain.

        Args:
            classifiers: Optional custom classifiers. If None, uses default chain.
        """
        if classifiers is None:
            # Default classifier chain: rule-based + scheduled-task + LLM
            classifiers = [
                RuleBasedClassifier(),
                ScheduledTaskClassifier(),
                LLMClassifier(),
            ]

        # Sort by priority (lower = higher precedence)
        self._classifiers = sorted(classifiers, key=lambda c: c.priority)
        logger.info(
            f"IntentAnalyzer initialized with classifiers: "
            f"{[c.name for c in self._classifiers]}"
        )

    def add_classifier(self, classifier: ClassifierBase) -> None:
        """Add a classifier to the chain.

        Args:
            classifier: Classifier to add
        """
        self._classifiers.append(classifier)
        self._classifiers.sort(key=lambda c: c.priority)
        logger.info(f"Added classifier: {classifier.name}")

    async def analyze(
        self,
        message: str,
        context: "AgentContext | dict[str, Any] | None" = None,
    ) -> IntentResult:
        """Analyze user message and determine intent.

        Runs classifiers in priority order until one returns a confident result.

        Args:
            message: User message
            context: AgentContext or legacy dict. If AgentContext, extracts simplified
                     context (project_name, filenames only - no file_id, project_id)
                     to prevent intent pollution.

        Returns:
            IntentResult with determined action and supporting information
        """
        from backend.aime.context import AgentContext

        # Build simplified context for intent analysis (exclude technical details)
        intent_context_str = ""
        context_dict: dict[str, Any] = {}

        if isinstance(context, AgentContext):
            # Extract semantic information only (no file_id, project_id, tool hints)
            parts = []
            if context.session.project_name:
                parts.append(f"用户在项目「{context.session.project_name}」中工作")
            if context.files.files:
                file_names = [f"「{f.filename}」" for f in context.files.files]
                parts.append(f"用户选择了文件: {', '.join(file_names)}")
            if parts:
                intent_context_str = "。".join(parts) + "。\n\n"

            # Convert to dict for classifier compatibility
            context_dict = {
                "explicit_agent": context.explicit_agent,
                "skill": context.skill,
                "user_id": context.session.user_id,
                "project_id": context.session.project_id,
            }
        elif isinstance(context, dict):
            context_dict = context
        else:
            context_dict = {}

        # Build message for intent analysis (with simplified context prefix)
        intent_message = f"{intent_context_str}{message}" if intent_context_str else message

        # Log entry with message preview and context summary
        context_summary = {k: v for k, v in context_dict.items() if v is not None}
        logger.info(
            f"[analyze] Starting - message_len={len(intent_message)}, "
            f"preview='{intent_message[:80]}...', context={context_summary}"
        )

        domain = context_dict.get("domain")

        # Get Langfuse client for tracing
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None

        for classifier in self._classifiers:
            try:
                # Create Langfuse span for each classifier
                context_manager = None
                span = None
                if langfuse_client:
                    try:
                        context_manager = langfuse_client.start_as_current_observation(
                            as_type="span",
                            name=f"intent-classifier-{classifier.name}",
                            input={"message_preview": intent_message[:200]},
                        )
                        span = context_manager.__enter__()
                    except Exception:
                        pass

                result = await classifier.classify(
                    message=intent_message,
                    context=context_dict,
                    domain=domain,
                )

                # Update span with result
                if span:
                    try:
                        if result:
                            span.update(output={
                                "action": result.action,
                                "confidence": result.confidence,
                                "matched": True,
                            })
                        else:
                            span.update(output={"matched": False})
                    except Exception:
                        pass
                if context_manager:
                    try:
                        context_manager.__exit__(None, None, None)
                    except Exception:
                        pass

                if result is not None:
                    logger.debug(
                        f"Intent classified by {classifier.name}: "
                        f"action={result.action}, confidence={result.confidence}"
                    )
                    return result
            except Exception as e:
                logger.warning(f"Classifier {classifier.name} failed: {e}")
                if span:
                    try:
                        span.update(output={"error": str(e)})
                    except Exception:
                        pass
                if context_manager:
                    try:
                        context_manager.__exit__(None, None, None)
                    except Exception:
                        pass
                continue

        # No classifier matched - default to direct_reply with low confidence
        # This allows simple unmatched queries to get direct responses
        logger.debug("No classifier matched, defaulting to direct_reply")
        return IntentResult(
            action="direct_reply",
            confidence=0.3,
            domain=domain or "general",
        )
