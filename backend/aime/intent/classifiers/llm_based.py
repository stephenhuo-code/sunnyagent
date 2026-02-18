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
你是一个多智能体 AI 系统的意图分类器。分析用户消息和上下文，决定合适的处理动作。

## 上下文感知

注意消息中的上下文线索：
- "用户选择了文件: 「xxx」" 表示用户选择了文件
- "用户在项目「xxx」中工作" 表示用户在某个项目中

## 可用动作

1. **direct_reply**: 简单问题，可以直接回答
   - 问候语：你好、hello、hi
   - 简单数学：1+1=?
   - 基础事实问题：什么是Python?
   - 确认回复：谢谢、好的

2. **delegate**: 需要专业代理处理的任务
   - 网络搜索、新闻、时事 → capabilities: ["web_search"]
   - 数据库查询、SQL、数据分析 → capabilities: ["database", "sql_query"]
   - **文件读取、文档分析** → capabilities: ["file_processing"]
   - 代码执行、文件生成 → capabilities: ["code_execution"]

   **重要**: 如果消息中包含"用户选择了文件"，则任何与文件相关的问题都应使用 capabilities: ["file_processing"]

3. **plan**: 复杂的多步骤任务，需要分解执行
   - 包含多个步骤（并且、然后、接着）
   - 需要多个输出
   - 跨领域任务（搜索...然后分析...）

4. **clarify**: 用户意图真的不清楚时（置信度 < 0.4）
   - 提供 1-2 个具体的澄清问题
   - 仅在绝对必要时使用

## 响应格式

返回 JSON 对象：
```json
{
  "action": "direct_reply|delegate|plan|clarify",
  "confidence": 0.0-1.0,
  "capabilities": ["capability1"],
  "reasoning": "简要说明"
}
```

仅当 action 为 "delegate" 时包含 capabilities。
仅当 action 为 "clarify" 时包含 clarify_questions。
"""


class LLMClassifier(ClassifierBase):
    """LLM-based classifier for semantic intent analysis.

    Uses an LLM to analyze user messages with context awareness.
    Handles all intent classification after rule-based routing.

    Priority: 10 (after rule-based)
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
        return 10

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
