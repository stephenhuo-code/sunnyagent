# Quickstart: Context Manager

**Date**: 2026-02-16
**Feature**: ContextManager for AIME task context management

## Prerequisites

- Python 3.11+
- PostgreSQL running (via docker compose)
- Database migrations applied

## Quick Setup

### 1. Apply Database Migration

```bash
cd infra
uv run alembic upgrade head
```

### 2. Environment Variables (Optional)

```bash
# Add to .env if you want to customize defaults
CONTEXT_EXPIRATION_DAYS=7       # Default: 7
CONTEXT_CACHE_SIZE=100          # Default: 100
CONTEXT_CLEANUP_INTERVAL=3600   # Default: 3600 (1 hour)
```

## Usage

### Basic Usage

```python
from backend.aime.context_manager import ContextManager

# Initialize
context_manager = ContextManager()

# Store task output
entry = await context_manager.store(
    context_id="task-001",
    thread_id="550e8400-e29b-41d4-a716-446655440000",
    content="Tesla Q3 2025 revenue: $25.2B, up 12% YoY...",
    expected_output=["financial_report", "revenue_data"],
)

print(f"Stored: tokens={entry.token_count}, types={entry.output_types}")
# Output: Stored: tokens=1234, types=['financial_report', 'revenue_data', 'table']

# Retrieve context
entry = await context_manager.get(
    context_id="task-001",
    thread_id="550e8400-e29b-41d4-a716-446655440000",
)

# Prepare context for dependent task
context_str = await context_manager.prepare_for_task(
    task_description="分析营收趋势",
    depends_on=["task-001"],
    thread_id="550e8400-e29b-41d4-a716-446655440000",
    expected_input=["financial_report"],
)

print(context_str)
# Output:
# ### 前置任务输出 (全文) [类型: financial_report, revenue_data]
# Tesla Q3 2025 revenue: $25.2B, up 12% YoY...
```

### Integration with Planner

```python
# backend/aime/planner.py

class AIMEPlanner:
    def __init__(self, ...):
        self.context_manager = ContextManager()

    async def _handle_plan(self, message, thread_id, ...):
        # ... task decomposition ...

        for spec in subtasks:
            # 1. Prepare context for dependent task
            if spec.depends_on:
                context_str = await self.context_manager.prepare_for_task(
                    task_description=spec.description,
                    depends_on=spec.depends_on,
                    thread_id=thread_id,
                    expected_input=spec.expected_input,
                )
                task_message = f"{spec.description}\n\n## 上下文\n{context_str}"
            else:
                task_message = spec.description

            # 2. Execute task
            result = await self._execute_actor(actor, task_message)

            # 3. Store result
            await self.context_manager.store(
                context_id=spec.id,
                thread_id=thread_id,
                content=result,
                expected_output=spec.expected_output,
            )
```

### SubtaskSpec with I/O Declaration

```python
from backend.aime.models import SubtaskSpec

# Task decomposition with I/O declaration
tasks = [
    SubtaskSpec(
        id="task-001",
        description="搜索特斯拉最新财报",
        capabilities=["web_search"],
        depends_on=[],
        expected_input=[],
        expected_output=["financial_report", "revenue_data"],
    ),
    SubtaskSpec(
        id="task-002",
        description="分析营收趋势",
        capabilities=["general"],
        depends_on=["task-001"],
        expected_input=["financial_report", "revenue_data"],
        expected_output=["analysis_report"],
    ),
]
```

## Testing

### Run Unit Tests

```bash
uv run pytest tests/aime/test_context_manager.py -v
```

### Run Integration Tests

```bash
# Requires PostgreSQL running
uv run pytest tests/aime/test_context_manager_integration.py -v
```

### Manual Testing

```python
# Test sliding expiration
entry = await context_manager.get("task-001", thread_id)
print(f"Expires at: {entry.expires_at}")  # Extended by 7 days

# Test cleanup
deleted = await context_manager.cleanup_expired()
print(f"Deleted {deleted} expired contexts")
```

## Troubleshooting

### Context Not Found

1. Check if context_id is correct
2. Check if thread_id matches (security isolation)
3. Check if context has expired (7 days no access)

### I/O Type Mismatch Warning

```
[ContextManager] I/O mismatch: expected_input=['chart'], output_types=['table']
```

This is a warning only. The system will still pass the context but logs the mismatch.

### PostgreSQL Connection Failed

The system will gracefully degrade:
- Continue using in-memory cache
- Log error for debugging
- Session recovery unavailable until DB is restored

### LLM Summarization Failed

The system will fall back to:
- Truncate content to first 500 characters
- Use `["raw_data"]` as default output type
