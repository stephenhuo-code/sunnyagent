"""Intent Classifiers Package.

Classifiers are executed in priority order (lower number = higher priority).
Each classifier can return an IntentResult or None to pass to the next.

Architecture (simplified):
1. RuleBasedClassifier (priority=0) - Explicit routing patterns
2. LLMClassifier (priority=10) - Semantic analysis with context awareness
"""

from backend.aime.intent.classifiers.base import ClassifierBase
from backend.aime.intent.classifiers.llm_based import LLMClassifier
from backend.aime.intent.classifiers.rule_based import RuleBasedClassifier

__all__ = [
    "ClassifierBase",
    "RuleBasedClassifier",
    "LLMClassifier",
]
