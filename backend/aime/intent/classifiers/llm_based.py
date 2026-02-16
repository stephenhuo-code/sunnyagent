"""LLM-based classifier for semantic intent analysis."""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.aime.intent.models import CAPABILITY_AGENT_MAP, IntentResult
from backend.llm import get_model

from .base import ClassifierBase

logger = logging.getLogger(__name__)


_CLASSIFIER_PROMPT = """\
You are an intent classifier for a multi-agent AI system. Analyze the user's message and determine the appropriate action.

## Available Actions

1. **direct_reply**: For simple questions, greetings, or queries that can be answered directly
   - Examples: "你好", "1+1=?", "什么是Python?", "谢谢"

2. **delegate**: For tasks that should be handled by a specialist agent
   - Web search, news, research → capabilities: ["web_search"]
   - Database queries, SQL → capabilities: ["database", "sql_query"]
   - Code execution, file generation → capabilities: ["code_execution"]

3. **plan**: For complex, multi-step tasks that need decomposition
   - Multiple steps mentioned
   - Multiple outputs required
   - Cross-domain tasks

4. **clarify**: When the user's intent is unclear (confidence < 0.5)
   - Provide specific clarification questions

## Response Format

Respond with a JSON object:
```json
{
  "action": "direct_reply|delegate|plan|clarify",
  "confidence": 0.0-1.0,
  "capabilities": ["capability1", "capability2"],
  "reasoning": "Brief explanation",
  "clarify_questions": ["Question 1", "Question 2"]
}
```

Only include clarify_questions when action is "clarify".
Only include capabilities when action is "delegate".
"""


class LLMClassifier(ClassifierBase):
    """LLM-based classifier for semantic intent analysis.

    Uses an LLM to analyze user messages when simpler classifiers
    cannot determine intent. This is the fallback classifier with
    the lowest priority.

    Priority: 20 (after rule-based and keyword-based)
    """

    def __init__(self, model=None):
        """Initialize the LLM classifier.

        Args:
            model: Optional LLM model (defaults to supervisor model)
        """
        self._model = model or get_model("supervisor")

    @property
    def name(self) -> str:
        return "llm_based"

    @property
    def priority(self) -> int:
        return 20

    async def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> IntentResult | None:
        """Classify intent using LLM analysis.

        Args:
            message: User message
            context: Optional context
            domain: Optional domain hint

        Returns:
            IntentResult from LLM analysis
        """
        logger.info(f"[llm_based] Starting classification - message='{message[:50]}...'")
        try:
            messages = [
                SystemMessage(content=_CLASSIFIER_PROMPT),
                HumanMessage(content=f"User message: {message}"),
            ]

            # Get LLM response
            response = await self._model.ainvoke(messages)
            logger.debug("[llm_based] LLM response received")
            content = response.content if hasattr(response, "content") else str(response)
            result_text = str(content) if not isinstance(content, str) else content

            # Parse JSON response
            result = self._parse_response(result_text)
            if result:
                logger.info(
                    f"[llm_based] Classification complete - action={result.action}, "
                    f"confidence={result.confidence}, capabilities={result.capabilities}"
                )
                return result

        except Exception as e:
            logger.warning(f"LLM classifier error: {e}")

        # Return None to indicate no classification (shouldn't happen often)
        return None

    def _parse_response(self, response_text: str) -> IntentResult | None:
        """Parse LLM response into IntentResult.

        Args:
            response_text: Raw LLM response

        Returns:
            IntentResult or None if parsing fails
        """
        try:
            # Extract JSON from response (may be wrapped in markdown)
            json_str = response_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            action = data.get("action", "direct_reply")
            if action not in ("direct_reply", "delegate", "plan", "clarify"):
                action = "direct_reply"

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            capabilities = data.get("capabilities", [])
            if not isinstance(capabilities, list):
                capabilities = []

            clarify_questions = data.get("clarify_questions")
            if clarify_questions and not isinstance(clarify_questions, list):
                clarify_questions = [str(clarify_questions)]

            return IntentResult(
                action=action,
                confidence=confidence,
                capabilities=capabilities,
                domain=data.get("domain", "general"),
                clarify_questions=clarify_questions if action == "clarify" else None,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return None
