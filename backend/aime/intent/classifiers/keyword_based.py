"""Keyword-based classifier for quick pattern matching."""

import logging
import re
from typing import Any

from backend.aime.intent.models import CAPABILITY_AGENT_MAP, IntentResult

from .base import ClassifierBase

logger = logging.getLogger(__name__)

# Simple greetings and short queries that should get direct responses
_DIRECT_REPLY_PATTERNS = [
    r"^(你好|hello|hi|hey|嗨|哈喽|早上好|下午好|晚上好|good\s*(morning|afternoon|evening))[\s!！。.]*$",
    r"^(谢谢|感谢|thanks?|thank\s*you|thx)[\s!！。.]*$",
    r"^(再见|拜拜|bye|goodbye|see\s*you)[\s!！。.]*$",
    r"^[\d\s+\-*/()=？?]+$",  # Simple math like "1+1=?"
    r"^(是的?|不是?|对|没问题|ok|okay|yes|no|好的?)[\s!！。.]*$",
    r"^(什么是|who\s+is|what\s+is).{0,20}$",  # Very short factual questions
]

# Patterns that indicate need for web search / research
_RESEARCH_PATTERNS = [
    r"(搜索|查找|查询|search|find|look\s*up)",
    r"(最新|latest|recent|news|新闻|资讯)",
    r"(比较|对比|compare|vs\.?|versus)",
    r"(怎么样|如何|how\s+to|tutorial)",
    r"(现在|目前|当前|today|now|currently)",
]

# Patterns that indicate SQL/database queries
_DATABASE_PATTERNS = [
    r"(数据库|database|sql|查询数据)",
    r"(表|table|记录|record)",
    r"(chinook|artists?|albums?|tracks?|customers?|invoices?|employees?)",
    r"(销售|订单|发票|sales|orders?|invoice)",
]

# Patterns that indicate complex multi-step tasks
_COMPLEX_TASK_PATTERNS = [
    r"(并且|然后|接着|同时|and\s+then|also|additionally)",
    r"(分析.*生成|搜索.*总结|查询.*分析)",
    r"(第一|第二|step\s*\d|steps?)",
    r"(报告|report|汇总|summary|总结)",
]


class KeywordClassifier(ClassifierBase):
    """Keyword-based classifier for quick pattern matching.

    Uses regex patterns to quickly identify:
    - Simple greetings/queries → direct_reply
    - Research-related keywords → delegate with web_search capability
    - Database-related keywords → delegate with database capability
    - Complex task indicators → plan action

    Priority: 10 (after rule-based, before LLM)
    """

    @property
    def name(self) -> str:
        return "keyword_based"

    @property
    def priority(self) -> int:
        return 10

    async def classify(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        domain: str | None = None,
    ) -> IntentResult | None:
        """Classify based on keyword patterns.

        Args:
            message: User message
            context: Optional context
            domain: Optional domain hint

        Returns:
            IntentResult if pattern matched, None otherwise
        """
        logger.debug(f"[keyword_based] Checking - message='{message[:50]}...'")
        msg_lower = message.lower().strip()

        # Check for simple direct reply patterns (high confidence)
        for pattern in _DIRECT_REPLY_PATTERNS:
            if re.match(pattern, msg_lower, re.IGNORECASE):
                logger.info(f"[keyword_based] Matched direct_reply pattern: {pattern[:30]}...")
                return IntentResult(
                    action="direct_reply",
                    confidence=0.9,
                    domain=domain or "general",
                )

        # Check for complex task patterns (multiple steps/outputs)
        complex_score = sum(
            1 for p in _COMPLEX_TASK_PATTERNS if re.search(p, msg_lower, re.IGNORECASE)
        )
        if complex_score >= 2:
            logger.info(f"[keyword_based] Complex task detected - score={complex_score}")
            # Strong indicator of complex task
            return IntentResult(
                action="plan",
                confidence=0.7,
                domain=domain or "general",
            )

        # Check for research patterns
        research_score = sum(
            1 for p in _RESEARCH_PATTERNS if re.search(p, msg_lower, re.IGNORECASE)
        )
        logger.debug(f"[keyword_based] Pattern scores - research={research_score}")
        if research_score >= 2:
            logger.info(f"[keyword_based] Research pattern matched - score={research_score}")
            return IntentResult(
                action="delegate",
                confidence=0.75,
                capabilities=["web_search"],
                domain=domain or "general",
            )

        # Check for database patterns
        db_score = sum(
            1 for p in _DATABASE_PATTERNS if re.search(p, msg_lower, re.IGNORECASE)
        )
        logger.debug(f"[keyword_based] Pattern scores - db={db_score}, complex={complex_score}")
        if db_score >= 2:
            logger.info(f"[keyword_based] Database pattern matched - score={db_score}")
            return IntentResult(
                action="delegate",
                confidence=0.75,
                capabilities=["database", "sql_query"],
                domain=domain or "general",
            )

        # Single pattern match with lower confidence
        if research_score == 1:
            return IntentResult(
                action="delegate",
                confidence=0.5,
                capabilities=["web_search"],
                domain=domain or "general",
            )

        if db_score == 1:
            return IntentResult(
                action="delegate",
                confidence=0.5,
                capabilities=["database"],
                domain=domain or "general",
            )

        # No confident match - pass to next classifier
        return None
