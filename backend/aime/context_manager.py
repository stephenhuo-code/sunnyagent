"""AIME Context Manager - Task context storage and retrieval.

Manages task-to-task context passing in multi-step workflows:
- LRU cache for hot data access
- PostgreSQL persistence for session recovery
- Sliding expiration (7 days from last access)
- LLM-powered summarization for long contexts
- Automatic output type classification
"""

import json
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import SystemMessage

from backend.db import get_pool
from backend.llm import get_model
from backend.services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration Constants
# =============================================================================

CONTEXT_EXPIRATION_DAYS = int(os.getenv("CONTEXT_EXPIRATION_DAYS", "7"))
CONTEXT_CACHE_SIZE = int(os.getenv("CONTEXT_CACHE_SIZE", "100"))
SHORT_CONTEXT_THRESHOLD = 2000  # tokens
CONTEXT_CLEANUP_INTERVAL = int(os.getenv("CONTEXT_CLEANUP_INTERVAL", "3600"))

# Predefined output types for classification
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
# Data Model
# =============================================================================


@dataclass
class ContextEntry:
    """Task context entry for storage and retrieval.

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

    def __post_init__(self) -> None:
        """Initialize expires_at if not set."""
        if self.expires_at is None:
            self.expires_at = self.last_accessed_at + timedelta(
                days=CONTEXT_EXPIRATION_DAYS
            )

    def is_expired(self) -> bool:
        """Check if context has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def touch(self) -> None:
        """Sliding expiration: update access time and extend expiration."""
        self.last_accessed_at = datetime.now()
        self.expires_at = self.last_accessed_at + timedelta(
            days=CONTEXT_EXPIRATION_DAYS
        )


# =============================================================================
# Context Manager
# =============================================================================


class ContextManager:
    """AIME task context manager with LRU cache and PostgreSQL persistence.

    Provides:
    - store(): Store task output with auto-classification
    - get(): Retrieve context with thread_id validation
    - prepare_for_task(): Prepare context for dependent task
    - cleanup_thread(): Clean up all contexts for a thread
    - cleanup_expired(): Clean up expired contexts
    """

    def __init__(self) -> None:
        """Initialize context manager with LRU cache."""
        self._cache: OrderedDict[str, ContextEntry] = OrderedDict()
        self._model = get_model("supervisor")
        logger.info(
            f"[ContextManager] Initialized: cache_size={CONTEXT_CACHE_SIZE}, "
            f"expiration_days={CONTEXT_EXPIRATION_DAYS}"
        )

    # =========================================================================
    # Public API
    # =========================================================================

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
        """
        token_count = self._estimate_tokens(content)
        now = datetime.now()
        expires_at = now + timedelta(days=CONTEXT_EXPIRATION_DAYS)

        # Auto-classify output types
        output_types = await self._classify_output_types(content)

        # Extract file references and store in metadata (P1 enhancement)
        file_refs = self._extract_file_references(content)
        enriched_metadata = metadata.copy() if metadata else {}
        if file_refs:
            enriched_metadata["file_references"] = file_refs
            # Ensure output_types includes "file"
            if "file" not in output_types:
                output_types.append("file")

        entry = ContextEntry(
            context_id=context_id,
            thread_id=thread_id,
            content=content,
            output_types=output_types,
            expected_output=expected_output or [],
            token_count=token_count,
            created_at=now,
            last_accessed_at=now,
            expires_at=expires_at,
            metadata=enriched_metadata,
        )

        # Generate summary for long contexts
        if token_count > SHORT_CONTEXT_THRESHOLD:
            entry.summary = await self._generate_summary(content)
            entry.key_data = await self._extract_key_data(content)

        # Validate output types match expected
        if expected_output:
            missing = set(expected_output) - set(output_types)
            if missing:
                logger.warning(
                    f"[ContextManager] Output type mismatch: "
                    f"expected={expected_output}, actual={output_types}, missing={list(missing)}"
                )

        # Store in LRU cache
        if context_id in self._cache:
            self._cache.move_to_end(context_id)
        self._cache[context_id] = entry

        # Enforce cache size limit
        while len(self._cache) > CONTEXT_CACHE_SIZE:
            self._cache.popitem(last=False)

        # Persist to PostgreSQL
        await self._save_to_db(entry)

        logger.info(
            f"[ContextManager] Stored: id={context_id[:8]}..., "
            f"tokens={token_count}, output_types={output_types}, "
            f"has_summary={entry.summary is not None}"
        )

        return entry

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
        """
        # Check LRU cache first
        if context_id in self._cache:
            entry = self._cache[context_id]
            if entry.is_expired():
                del self._cache[context_id]
                return None

            # Security: validate thread_id
            if entry.thread_id != thread_id:
                logger.warning(
                    f"[ContextManager] Access denied: thread_id mismatch for {context_id[:8]}..."
                )
                return None

            # Sliding expiration
            entry.touch()
            await self._touch_in_db(context_id)
            self._cache.move_to_end(context_id)
            return entry

        # Cache miss - load from DB
        entry = await self._load_from_db(context_id)
        if entry is None:
            return None

        if entry.is_expired():
            return None

        # Security: validate thread_id
        if entry.thread_id != thread_id:
            logger.warning(
                f"[ContextManager] Access denied: thread_id mismatch for {context_id[:8]}..."
            )
            return None

        # Sliding expiration
        entry.touch()
        await self._touch_in_db(context_id)

        # Add to cache
        self._cache[context_id] = entry

        return entry

    async def prepare_for_task(
        self,
        task_description: str,
        depends_on: list[str],
        thread_id: str,
        expected_input: list[str] | None = None,
        max_tokens: int = SHORT_CONTEXT_THRESHOLD,
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
        """
        if not depends_on:
            return ""

        context_parts: list[str] = []
        total_tokens = 0
        per_dep_budget = max_tokens // len(depends_on) if depends_on else max_tokens

        for dep_id in depends_on:
            entry = await self.get(dep_id, thread_id)
            if entry is None:
                logger.warning(
                    f"[ContextManager] Dependency {dep_id[:8]}... not found or expired"
                )
                continue

            # Check I/O type matching
            if expected_input:
                matched_types = set(expected_input) & set(entry.output_types)
                if not matched_types:
                    logger.warning(
                        f"[ContextManager] I/O mismatch: "
                        f"expected_input={expected_input}, output_types={entry.output_types}"
                    )
                else:
                    logger.debug(f"[ContextManager] I/O matched: {matched_types}")

            # Select content based on length
            if entry.token_count <= per_dep_budget:
                context_text = entry.content
                source_type = "全文"
            elif entry.summary:
                parts = [entry.summary]
                if entry.key_data:
                    parts.append(
                        f"关键数据: {json.dumps(entry.key_data, ensure_ascii=False)}"
                    )
                context_text = "\n\n".join(parts)
                source_type = "摘要"
            else:
                # Fallback: truncate
                context_text = entry.content[: per_dep_budget * 4]
                source_type = "截断"

            # Add output type labels
            type_label = (
                f"[类型: {', '.join(entry.output_types)}]"
                if entry.output_types
                else ""
            )

            # Build context block
            context_block = f"### 前置任务输出 ({source_type}) {type_label}\n{context_text}"

            # Explicitly add file list if available (P1: ensures files survive summarization)
            if entry.metadata and entry.metadata.get("file_references"):
                files_info = "\n**可用文件（来自此任务）:**\n"
                for f in entry.metadata["file_references"]:
                    files_info += f"- [{f['filename']}]({f['url']})\n"
                context_block += "\n" + files_info

            context_parts.append(context_block)
            total_tokens += self._estimate_tokens(context_block)

        if not context_parts:
            return ""

        logger.info(
            f"[ContextManager] Prepared context: "
            f"deps={len(depends_on)}, total_tokens~={total_tokens}"
        )

        return "\n\n---\n\n".join(context_parts)

    async def cleanup_thread(self, thread_id: str) -> int:
        """Clean up all contexts for a thread.

        Args:
            thread_id: Session ID to clean up

        Returns:
            Number of contexts deleted
        """
        # Clean from cache
        to_remove = [k for k, v in self._cache.items() if v.thread_id == thread_id]
        for k in to_remove:
            del self._cache[k]

        # Clean from database
        deleted_count = 0
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM task_contexts WHERE thread_id = $1",
                    thread_id,
                )
                # Parse "DELETE N" result
                if result:
                    parts = result.split()
                    if len(parts) >= 2:
                        deleted_count = int(parts[1])
        except Exception as e:
            logger.error(f"[ContextManager] cleanup_thread DB error: {e}")

        logger.info(
            f"[ContextManager] Cleaned up thread {thread_id[:8]}...: "
            f"cache={len(to_remove)}, db={deleted_count}"
        )

        return deleted_count + len(to_remove)

    async def cleanup_expired(self) -> int:
        """Clean up all expired contexts.

        Returns:
            Number of contexts deleted
        """
        # Clean expired from cache
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            del self._cache[k]

        # Clean from database
        deleted_count = 0
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM task_contexts WHERE expires_at < NOW()"
                )
                if result:
                    parts = result.split()
                    if len(parts) >= 2:
                        deleted_count = int(parts[1])
        except Exception as e:
            logger.error(f"[ContextManager] cleanup_expired DB error: {e}")

        logger.info(
            f"[ContextManager] Cleaned up expired: "
            f"cache={len(expired_keys)}, db={deleted_count}"
        )

        return deleted_count + len(expired_keys)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using simple heuristic."""
        return len(text) // 3

    async def _save_to_db(self, entry: ContextEntry) -> None:
        """Save context entry to PostgreSQL."""
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO task_contexts
                        (context_id, thread_id, content, summary, key_data,
                         output_types, expected_output, token_count,
                         created_at, last_accessed_at, expires_at, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (context_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        summary = EXCLUDED.summary,
                        key_data = EXCLUDED.key_data,
                        output_types = EXCLUDED.output_types,
                        expected_output = EXCLUDED.expected_output,
                        token_count = EXCLUDED.token_count,
                        last_accessed_at = EXCLUDED.last_accessed_at,
                        expires_at = EXCLUDED.expires_at,
                        metadata = EXCLUDED.metadata
                    """,
                    entry.context_id,
                    entry.thread_id,
                    entry.content,
                    entry.summary,
                    json.dumps(entry.key_data) if entry.key_data else None,
                    entry.output_types,
                    entry.expected_output,
                    entry.token_count,
                    entry.created_at,
                    entry.last_accessed_at,
                    entry.expires_at,
                    json.dumps(entry.metadata),
                )
        except Exception as e:
            # Graceful degradation: log error but don't block
            logger.error(f"[ContextManager] _save_to_db failed: {e}")

    async def _load_from_db(self, context_id: str) -> ContextEntry | None:
        """Load context entry from PostgreSQL."""
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT context_id, thread_id, content, summary, key_data,
                           output_types, expected_output, token_count,
                           created_at, last_accessed_at, expires_at, metadata
                    FROM task_contexts
                    WHERE context_id = $1
                    """,
                    context_id,
                )
                if row is None:
                    return None

                return ContextEntry(
                    context_id=row["context_id"],
                    thread_id=str(row["thread_id"]),
                    content=row["content"],
                    summary=row["summary"],
                    key_data=json.loads(row["key_data"]) if row["key_data"] else None,
                    output_types=list(row["output_types"]) if row["output_types"] else [],
                    expected_output=list(row["expected_output"]) if row["expected_output"] else [],
                    token_count=row["token_count"],
                    created_at=row["created_at"],
                    last_accessed_at=row["last_accessed_at"],
                    expires_at=row["expires_at"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
        except Exception as e:
            logger.error(f"[ContextManager] _load_from_db failed: {e}")
            return None

    async def _touch_in_db(self, context_id: str) -> None:
        """Update access time in database for sliding expiration."""
        new_expires = datetime.now() + timedelta(days=CONTEXT_EXPIRATION_DAYS)
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE task_contexts
                    SET last_accessed_at = NOW(), expires_at = $1
                    WHERE context_id = $2
                    """,
                    new_expires,
                    context_id,
                )
        except Exception as e:
            logger.error(f"[ContextManager] _touch_in_db failed: {e}")

    async def _generate_summary(self, content: str) -> str:
        """Generate summary using LLM with fallback."""
        prompt = f"""\
请为以下内容生成简洁摘要，保留关键信息和数据。最多300字。

## 原文
{content[:3000]}
"""
        # Create Langfuse span for summary generation
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span_context = None

        if langfuse_client:
            try:
                span_context = langfuse_client.start_as_current_observation(
                    as_type="generation",
                    name="context-summary-generation",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={"content_length": len(content)},
                )
                span_context.__enter__()
            except Exception:
                pass

        try:
            response = await self._model.ainvoke([SystemMessage(content=prompt)])
            summary = str(response.content)

            # Update Langfuse span with output
            if span_context and langfuse_client:
                try:
                    langfuse_client.update_current_observation(output={"summary": summary[:300]})
                except Exception:
                    pass

            return summary
        except Exception as e:
            logger.error(f"[ContextManager] _generate_summary failed: {e}")
            # Update Langfuse span with error
            if span_context and langfuse_client:
                try:
                    langfuse_client.update_current_observation(output={"error": str(e)})
                except Exception:
                    pass
            # Fallback: truncate
            return content[:500]
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    async def _extract_key_data(self, content: str) -> dict[str, Any]:
        """Extract structured key data using LLM with fallback."""
        prompt = f"""\
从以下内容提取关键数据，返回 JSON：
- numbers: 关键数字 [{{"label": "xxx", "value": "xxx"}}]
- findings: 关键发现 ["xxx"]

## 原文
{content[:2000]}

直接返回 JSON，不要其他文字。
"""
        # Create Langfuse span for key data extraction
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span_context = None

        if langfuse_client:
            try:
                span_context = langfuse_client.start_as_current_observation(
                    as_type="generation",
                    name="context-extract-key-data",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={"content_length": len(content)},
                )
                span_context.__enter__()
            except Exception:
                pass

        try:
            response = await self._model.ainvoke([SystemMessage(content=prompt)])
            text = str(response.content)
            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            key_data = json.loads(text.strip())

            # Update Langfuse span with output
            if span_context and langfuse_client:
                try:
                    langfuse_client.update_current_observation(output=key_data)
                except Exception:
                    pass

            return key_data
        except Exception as e:
            logger.debug(f"[ContextManager] _extract_key_data failed: {e}")
            # Update Langfuse span with error
            if span_context and langfuse_client:
                try:
                    langfuse_client.update_current_observation(output={"error": str(e)})
                except Exception:
                    pass
            return {}
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    async def _classify_output_types(self, content: str) -> list[str]:
        """Classify output types using LLM with fallback."""
        prompt = f"""\
分析以下内容，判断它包含哪些类型的数据。

## 可选类型
- financial_report: 财务报告、财报数据
- revenue_data: 营收数据、销售数据
- table: 表格数据
- chart: 图表
- code: 代码片段
- analysis_report: 分析报告
- summary: 摘要总结
- file: 生成的文件
- raw_data: 原始数据

## 内容
{content[:2000]}

## 要求
返回 JSON 数组，只包含匹配的类型，如 ["financial_report", "table"]
"""
        # Create Langfuse span for output type classification
        langfuse_service = get_langfuse_service()
        langfuse_client = langfuse_service.get_client() if langfuse_service.enabled else None
        span_context = None

        if langfuse_client:
            try:
                span_context = langfuse_client.start_as_current_observation(
                    as_type="generation",
                    name="context-classify-output-types",
                    model=getattr(self._model, "model", None) or getattr(self._model, "model_name", "unknown"),
                    input={"content_length": len(content)},
                )
                span_context.__enter__()
            except Exception:
                pass

        try:
            response = await self._model.ainvoke([SystemMessage(content=prompt)])
            text = str(response.content)
            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            types = json.loads(text.strip())
            # Filter valid types
            valid_types = [t for t in types if t in OUTPUT_TYPES]
            result = valid_types if valid_types else ["raw_data"]

            # Update Langfuse span with output
            if span_context and langfuse_client:
                try:
                    langfuse_client.update_current_observation(output={"output_types": result})
                except Exception:
                    pass

            return result
        except Exception as e:
            logger.debug(f"[ContextManager] _classify_output_types failed: {e}")
            # Update Langfuse span with error
            if span_context and langfuse_client:
                try:
                    langfuse_client.update_current_observation(output={"error": str(e)})
                except Exception:
                    pass
            return ["raw_data"]
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    def _extract_file_references(self, content: str) -> list[dict[str, str]]:
        """Extract file references from content.

        Supports multiple formats:
        - [📥 点击下载 filename](/api/files/id/filename)
        - [下载 filename](/api/files/id/filename)
        - [filename](/api/files/id/filename)

        Args:
            content: Task output content

        Returns:
            List of file references: [{"file_id": "xxx", "filename": "xxx", "url": "/api/files/xxx/xxx"}]
        """
        import re

        # Match /api/files/{file_id}/{filename} pattern
        pattern = r'\[.*?\]\(/api/files/([^/]+)/([^)]+)\)'
        matches = re.findall(pattern, content)

        file_refs = []
        seen_ids: set[str] = set()
        for file_id, filename in matches:
            if file_id not in seen_ids:
                seen_ids.add(file_id)
                file_refs.append({
                    "file_id": file_id,
                    "filename": filename,
                    "url": f"/api/files/{file_id}/{filename}"
                })

        return file_refs
