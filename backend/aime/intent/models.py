"""Intent Module Data Models.

Defines core types for intent analysis results.
"""

from dataclasses import dataclass, field
from typing import Literal

# =============================================================================
# Type Definitions
# =============================================================================

Action = Literal["direct_reply", "delegate", "plan", "clarify", "command"]
"""
Action types that determine Planner behavior:
- direct_reply: Simple question, respond directly without tools
- delegate: Single task, route to specialist agent
- plan: Complex task, decompose into multiple subtasks
- clarify: Unclear intent, ask user for clarification
- command: User invoked a /command, execute its workflow
"""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class IntentResult:
    """Result of intent analysis.

    Attributes:
        action: The determined action type
        confidence: Confidence score (0.0-1.0)
        capabilities: Required capabilities for agent matching
        domain: Domain identifier (for future extension)
        clarify_questions: Questions to ask when action is 'clarify'
        explicit_agent: User-specified agent name (from [ROUTE_TO: xxx])
        command_name: Command name when action is 'command' (e.g., "analyze")
        plugin_name: Plugin name for permission check (e.g., "package:data")
    """

    action: Action
    confidence: float = 0.0
    capabilities: list[str] = field(default_factory=list)
    domain: str = "general"
    clarify_questions: list[str] | None = None
    explicit_agent: str | None = None
    command_name: str | None = None
    plugin_name: str | None = None


# =============================================================================
# Capability Mapping
# =============================================================================

CAPABILITY_AGENT_MAP: dict[str, str] = {
    # Search capabilities
    "web_search": "research",
    "news_search": "research",
    "academic_search": "research",
    # Database capabilities
    "database": "sql",
    "sql_query": "sql",
    # General capabilities (handled by generic actor)
    "code_execution": "generic",
    "file_processing": "generic",
    "document_generation": "generic",
    # Future extensions
    "knowledge_base": "knowledge",
}
"""
Mapping from capability names to default agent names.

Note: This is a quick reference for IntentAnalyzer. Actual agent selection
is performed by ActorFactory using AGENT_REGISTRY capabilities.
"""
