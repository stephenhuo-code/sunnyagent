"""History optimization utilities for AIME.

This module provides utilities for optimizing conversation history to reduce
token usage while maintaining context quality. It implements:

1. Full retention of recent N rounds (configurable)
2. Sparse summary of older messages
3. Caching of summaries to avoid redundant LLM calls

Strategy:
    Conversation History:
    ├── [Summary] Compressed summary of rounds 1-10
    ├── [Full] Round 11 (user + assistant)
    ├── [Full] Round 12
    ├── [Full] Round 13
    ├── [Full] Round 14
    └── [Full] Round 15 (latest)
"""

import logging
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

# History optimization configuration
HISTORY_FULL_ROUNDS = 5  # Keep last N rounds fully
HISTORY_SUMMARY_INTERVAL = 5  # Update summary every N new rounds
HISTORY_SUMMARY_MAX_TOKENS = 500  # Max tokens for summary


async def prepare_history_messages(
    thread_id: str,
    full_rounds: int = HISTORY_FULL_ROUNDS,
) -> tuple[list[BaseMessage], str | None]:
    """Prepare optimized history messages for context.

    Retrieves conversation history and optimizes it by:
    1. Keeping the last N rounds of messages fully
    2. Summarizing older messages to reduce token count

    Args:
        thread_id: The thread ID to fetch history for
        full_rounds: Number of recent rounds to keep fully (default: 5)

    Returns:
        Tuple of (recent_messages, summary_text):
        - recent_messages: List of recent messages to include fully
        - summary_text: Optional summary of older messages
    """
    from backend.checkpointer_store import get_history_graph

    history_graph = get_history_graph()
    if not history_graph:
        return [], None

    try:
        # Get full history from checkpointer
        state = await history_graph.aget_state(
            {"configurable": {"thread_id": thread_id}}
        )
        all_messages = state.values.get("messages", []) if state.values else []

        if not all_messages:
            return [], None

        # Calculate split point: N rounds = 2N messages (user + assistant pairs)
        messages_to_keep = full_rounds * 2
        split_point = len(all_messages) - messages_to_keep

        if split_point <= 0:
            # Not enough messages for optimization, return all
            return all_messages, None

        # Split messages
        older_messages = all_messages[:split_point]
        recent_messages = all_messages[split_point:]

        # Get or generate summary for older messages
        summary = await _get_or_generate_summary(thread_id, older_messages)

        logger.info(
            f"[prepare_history_messages] thread_id={thread_id}, "
            f"total={len(all_messages)}, recent={len(recent_messages)}, "
            f"summarized={len(older_messages)}"
        )

        return recent_messages, summary

    except Exception as e:
        logger.warning(f"[prepare_history_messages] Failed to prepare history: {e}")
        return [], None


async def _get_or_generate_summary(
    thread_id: str,
    older_messages: list[BaseMessage],
) -> str | None:
    """Get cached summary or generate a new one for older messages.

    Uses sparse update strategy: only regenerates summary when message
    count exceeds threshold.

    Args:
        thread_id: Thread ID for caching
        older_messages: List of older messages to summarize

    Returns:
        Summary text or None if no summary needed
    """
    if not older_messages:
        return None

    # TODO: Implement summary caching in database or memory
    # For now, generate summary on demand
    # Future optimization: cache summaries and update sparingly

    return await _generate_summary(older_messages)


async def _generate_summary(
    messages: list[BaseMessage],
    max_tokens: int = HISTORY_SUMMARY_MAX_TOKENS,
) -> str | None:
    """Generate a summary of messages using LLM.

    Args:
        messages: List of messages to summarize
        max_tokens: Maximum tokens for the summary

    Returns:
        Summary text or None if generation fails
    """
    if not messages:
        return None

    try:
        from backend.llm import get_model

        # Build conversation text for summarization
        conversation_parts = []
        for msg in messages:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            conversation_parts.append(f"{role}: {content}")

        conversation_text = "\n".join(conversation_parts)

        # Use a fast model for summarization (use "general" agent which typically uses faster model)
        llm = get_model("general")

        summary_prompt = f"""请简洁总结以下对话的关键信息（不超过{max_tokens}字）：

{conversation_text}

总结要点：
- 用户的主要问题或需求
- 助手提供的关键信息或结论
- 任何重要的上下文（如数据源、时间范围等）"""

        response = await llm.ainvoke([HumanMessage(content=summary_prompt)])

        summary = response.content if isinstance(response.content, str) else str(response.content)

        logger.info(
            f"[_generate_summary] Generated summary for {len(messages)} messages, "
            f"length={len(summary)}"
        )

        return summary

    except Exception as e:
        logger.warning(f"[_generate_summary] Failed to generate summary: {e}")
        return None


def build_optimized_messages(
    recent_messages: list[BaseMessage],
    summary: str | None,
    current_message: str,
    system_context: str | None = None,
) -> list[BaseMessage]:
    """Build optimized message list for LLM input.

    Combines summary, recent messages, and current input into
    a token-efficient message list.

    Args:
        recent_messages: Recent messages to include fully
        summary: Optional summary of older messages
        current_message: Current user message
        system_context: Optional system context to include

    Returns:
        List of messages ready for LLM input
    """
    messages: list[BaseMessage] = []

    # Add summary as system message if available
    if summary:
        messages.append(SystemMessage(content=f"对话历史摘要:\n{summary}"))

    # Add recent messages
    messages.extend(recent_messages)

    # Add system context if available
    if system_context:
        messages.append(SystemMessage(content=f"当前上下文:\n{system_context}"))

    # Add current message
    messages.append(HumanMessage(content=current_message))

    return messages
