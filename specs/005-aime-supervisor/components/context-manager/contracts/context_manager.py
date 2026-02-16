"""ContextManager Interface Contract.

This module defines the interface for AIME task context management.
Implementation must conform to this contract.

Date: 2026-02-16
Feature: ContextManager for AIME
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


# =============================================================================
# Data Transfer Objects
# =============================================================================


@dataclass
class ContextEntry:
    """Task context entry.

    Attributes:
        context_id: Unique task identifier (primary key)
        thread_id: Session ID (foreign key to conversations)
        content: Original output content
        summary: LLM-generated summary (for long contexts)
        key_data: Structured key data extracted from content
        output_types: Auto-classified output types
        expected_output: Expected output types from SubtaskSpec
        token_count: Estimated token count
        created_at: Creation timestamp
        last_accessed_at: Last access timestamp (for sliding expiration)
        expires_at: Expiration timestamp
        metadata: Additional metadata
    """

    context_id: str
    thread_id: str
    content: str
    summary: str | None = None
    key_data: dict[str, Any] | None = None
    output_types: list[str] = field(default_factory=list)
    expected_output: list[str] = field(default_factory=list)
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Interface Contract
# =============================================================================


class IContextManager(ABC):
    """Interface for AIME task context management.

    Implementations must provide:
    - store(): Store task output with auto-classification
    - get(): Retrieve context with thread_id validation
    - prepare_for_task(): Prepare context for dependent task
    - cleanup_thread(): Clean up all contexts for a thread
    - cleanup_expired(): Clean up expired contexts
    """

    @abstractmethod
    async def store(
        self,
        context_id: str,
        thread_id: str,
        content: str,
        expected_output: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextEntry:
        """Store task output with auto-classification.

        Args:
            context_id: Unique task identifier
            thread_id: Session ID for isolation
            content: Task output content
            expected_output: Expected output types from SubtaskSpec
            metadata: Additional metadata

        Returns:
            ContextEntry with auto-classified output_types

        Behavior:
            - Estimates token count
            - If tokens > 2000: generates summary and extracts key_data
            - Auto-classifies output_types using LLM
            - Validates against expected_output (logs warning on mismatch)
            - Stores to LRU cache and PostgreSQL
            - Uses ON CONFLICT DO UPDATE for concurrent writes

        Graceful Degradation:
            - LLM failure: Uses truncated content and ["raw_data"]
            - DB failure: Continues with cache only, logs error
        """
        ...

    @abstractmethod
    async def get(
        self,
        context_id: str,
        thread_id: str,
    ) -> ContextEntry | None:
        """Retrieve context with thread_id validation.

        Args:
            context_id: Task identifier to retrieve
            thread_id: Session ID for validation

        Returns:
            ContextEntry if found and valid, None otherwise

        Behavior:
            - Checks LRU cache first
            - Falls back to PostgreSQL on cache miss
            - Validates thread_id matches (security isolation)
            - Updates last_accessed_at and expires_at (sliding expiration)
            - Returns None for expired or mismatched contexts
            - Logs security warning on thread_id mismatch
        """
        ...

    @abstractmethod
    async def prepare_for_task(
        self,
        task_description: str,
        depends_on: list[str],
        thread_id: str,
        expected_input: list[str] | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """Prepare context for a dependent task.

        Args:
            task_description: Description of the task needing context
            depends_on: List of task IDs to get context from
            thread_id: Session ID for validation
            expected_input: Expected input types for filtering
            max_tokens: Maximum total tokens for context

        Returns:
            Formatted context string for the task

        Behavior:
            - Retrieves contexts for all depends_on tasks
            - Validates thread_id for each context
            - If expected_input provided: filters by output_types match
            - Distributes token budget across dependencies
            - Short contexts: returns full content
            - Long contexts: returns summary + key_data
            - Formats as markdown sections
            - Logs warning on I/O type mismatch
        """
        ...

    @abstractmethod
    async def cleanup_thread(self, thread_id: str) -> int:
        """Clean up all contexts for a thread.

        Args:
            thread_id: Session ID to clean up

        Returns:
            Number of contexts deleted

        Behavior:
            - Removes from LRU cache
            - Deletes from PostgreSQL
            - Called when user deletes conversation
        """
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up all expired contexts.

        Returns:
            Number of contexts deleted

        Behavior:
            - Removes expired entries from LRU cache
            - Deletes from PostgreSQL where expires_at < NOW()
            - Called periodically by background task
        """
        ...


# =============================================================================
# Output Types
# =============================================================================

OUTPUT_TYPES = [
    "financial_report",  # 财务报告
    "revenue_data",      # 营收数据
    "table",             # 表格数据
    "chart",             # 图表
    "code",              # 代码片段
    "analysis_report",   # 分析报告
    "summary",           # 摘要总结
    "file",              # 生成的文件
    "raw_data",          # 原始数据（默认）
]


# =============================================================================
# Configuration
# =============================================================================

class ContextManagerConfig(Protocol):
    """Configuration protocol for ContextManager."""

    @property
    def expiration_days(self) -> int:
        """Days before context expires (default: 7)."""
        ...

    @property
    def cache_size(self) -> int:
        """Maximum LRU cache entries (default: 100)."""
        ...

    @property
    def short_context_threshold(self) -> int:
        """Token threshold for summarization (default: 2000)."""
        ...

    @property
    def cleanup_interval(self) -> int:
        """Seconds between cleanup runs (default: 3600)."""
        ...
