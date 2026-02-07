"""Translate LangGraph astream() chunks into SSE events.

This is the core streaming logic that converts the 3-tuple chunks from
agent.astream() into typed SSE event strings for the frontend.

Adapted for the Supervisor architecture where messages come from multiple
subgraph namespaces (supervisor node, specialist agent nodes).
"""

import json
from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

# Tools that are purely internal routing — never shown to the user.
_HIDDEN_TOOLS = {"route"}


def _format_sse(event: str, data: dict) -> dict:
    """Format a single SSE event dict for sse-starlette EventSourceResponse."""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _format_tool_content(content) -> str:
    """Extract displayable string from tool message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", str(item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


async def stream_agent_response(
    agent: CompiledStateGraph,
    thread_id: str,
    message: str,
) -> AsyncGenerator[dict, None]:
    """Stream agent response as SSE events.

    Processes the LangGraph astream() output and yields SSE-formatted dicts.
    Shows output from the supervisor (direct answers) and specialist subgraph
    agents, filtering out internal routing mechanics.

    Args:
        agent: The compiled supervisor graph.
        thread_id: Thread ID for conversation persistence.
        message: User message to send.

    Yields:
        SSE-formatted event dicts.
    """
    config = {"configurable": {"thread_id": thread_id}}
    stream_input: dict = {"messages": [{"role": "user", "content": message}]}

    # Buffers for tool call streaming (args arrive as JSON fragments)
    tool_call_buffers: dict[str | int, dict] = {}
    displayed_tool_ids: set[str] = set()
    # Track hidden tool call IDs so we can also suppress their ToolMessage results
    hidden_tool_call_ids: set[str] = set()

    try:
        async for chunk in agent.astream(
            stream_input,
            stream_mode=["messages", "updates"],
            subgraphs=True,
            config=config,
        ):
            if not isinstance(chunk, tuple) or len(chunk) != 3:
                continue

            namespace, current_stream_mode, data = chunk

            # --- UPDATES stream: skip for now (no HITL in this app) ---
            if current_stream_mode == "updates":
                continue

            # --- MESSAGES stream: text, tool calls, tool results ---
            if current_stream_mode != "messages":
                continue

            if not isinstance(data, tuple) or len(data) != 2:
                continue

            msg, metadata = data

            # Filter summarization output
            if metadata and metadata.get("lc_source") == "summarization":
                continue

            # Skip echoed user messages
            if isinstance(msg, HumanMessage):
                continue

            # --- Tool results ---
            if isinstance(msg, ToolMessage):
                tool_id = getattr(msg, "tool_call_id", None)
                tool_name = getattr(msg, "name", "")

                # Skip results for hidden tools (e.g. route)
                if tool_name in _HIDDEN_TOOLS or tool_id in hidden_tool_call_ids:
                    continue

                tool_status = getattr(msg, "status", "success")
                tool_content = _format_tool_content(msg.content)

                if tool_id:
                    yield _format_sse("tool_call_result", {
                        "id": tool_id,
                        "name": tool_name,
                        "status": tool_status,
                        "output": tool_content[:2000],
                    })
                continue

            # --- AI message chunks (text + tool calls) ---
            if not hasattr(msg, "content_blocks"):
                continue

            for block in msg.content_blocks:
                block_type = block.get("type")

                # Text content
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        yield _format_sse("text_delta", {"text": text})

                # Tool call chunks (may arrive as fragments)
                elif block_type in {"tool_call_chunk", "tool_call"}:
                    chunk_name = block.get("name")
                    chunk_args = block.get("args")
                    chunk_id = block.get("id")
                    chunk_index = block.get("index")

                    # Determine buffer key
                    if chunk_index is not None:
                        buffer_key: str | int = chunk_index
                    elif chunk_id is not None:
                        buffer_key = chunk_id
                    else:
                        buffer_key = f"unknown-{len(tool_call_buffers)}"

                    buffer = tool_call_buffers.setdefault(
                        buffer_key,
                        {"name": None, "id": None, "args": None, "args_parts": []},
                    )

                    if chunk_name:
                        buffer["name"] = chunk_name
                    if chunk_id:
                        buffer["id"] = chunk_id

                    # Accumulate args (may arrive as dict or string fragments)
                    if isinstance(chunk_args, dict):
                        buffer["args"] = chunk_args
                        buffer["args_parts"] = []
                    elif isinstance(chunk_args, str):
                        if chunk_args:
                            parts: list[str] = buffer.setdefault("args_parts", [])
                            if not parts or chunk_args != parts[-1]:
                                parts.append(chunk_args)
                            buffer["args"] = "".join(parts)
                    elif chunk_args is not None:
                        buffer["args"] = chunk_args

                    # Try to emit once we have name + parseable args
                    buffer_name = buffer.get("name")
                    buffer_id = buffer.get("id")
                    if buffer_name is None:
                        continue

                    # Skip hidden tools entirely
                    if buffer_name in _HIDDEN_TOOLS:
                        if buffer_id:
                            hidden_tool_call_ids.add(buffer_id)
                        tool_call_buffers.pop(buffer_key, None)
                        continue

                    parsed_args = buffer.get("args")
                    if isinstance(parsed_args, str):
                        if not parsed_args:
                            continue
                        try:
                            parsed_args = json.loads(parsed_args)
                        except json.JSONDecodeError:
                            continue
                    elif parsed_args is None:
                        continue

                    if not isinstance(parsed_args, dict):
                        parsed_args = {"value": parsed_args}

                    # Emit tool_call_start once per tool call ID
                    if buffer_id is not None and buffer_id not in displayed_tool_ids:
                        displayed_tool_ids.add(buffer_id)
                        yield _format_sse("tool_call_start", {
                            "id": buffer_id,
                            "name": buffer_name,
                            "args": parsed_args,
                        })

                    tool_call_buffers.pop(buffer_key, None)

    except Exception as e:
        yield _format_sse("error", {"message": str(e)})

    yield _format_sse("done", {})
