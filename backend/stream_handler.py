"""Translate LangGraph astream() chunks into SSE events.

This is the core streaming logic that converts the 3-tuple chunks from
agent.astream() into typed SSE event strings for the frontend.

Adapted for the Supervisor architecture where messages come from multiple
subgraph namespaces (supervisor node, specialist agent nodes).

Enhanced with support for:
- todos_updated: Task list changes from TodoListMiddleware
- task_spawned/task_completed: Sub-agent task lifecycle
- Event IDs for SSE reconnection
"""

import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import CompiledStateGraph


# =============================================================================
# Backend State Dataclasses (per data-model.md)
# =============================================================================


@dataclass
class EventCounter:
    """Generate sequential event IDs for SSE reconnection support."""

    _counter: int = 0

    def next_id(self) -> str:
        """Return the next sequential event ID."""
        self._counter += 1
        return str(self._counter)


@dataclass
class TaskTracker:
    """Track sub-agent task lifecycle for task_spawned/task_completed events."""

    task_id: str
    subagent_type: str
    description: str
    start_time: float = field(default_factory=time.time)

    def to_spawned_event(self) -> dict[str, Any]:
        """Generate task_spawned event data."""
        return {
            "task_id": self.task_id,
            "subagent_type": self.subagent_type,
            "description": self.description,
        }

    def to_completed_event(self, status: str) -> dict[str, Any]:
        """Generate task_completed event data with duration."""
        return {
            "task_id": self.task_id,
            "duration_ms": int((time.time() - self.start_time) * 1000),
            "status": status,
        }

# Tools whose output is surfaced as "thinking" SSE events instead of tool_call cards.
# Note: "route" is handled separately to emit both thinking and task_spawned events
_THINKING_TOOLS = {"think_tool"}

# Tool name for sub-agent task delegation (from SubAgentMiddleware)
_TASK_TOOL = "task"

# Tool name for supervisor routing (emits thinking + task_spawned)
_ROUTE_TOOL = "route"

# Tool name for todo list updates (from TodoListMiddleware)
_TODOS_TOOL = "write_todos"


def _get_thinking_type(tool_name: str, args: dict) -> str | None:
    """Determine the thinking type based on tool name and args."""
    if tool_name == "route":
        return "routing"
    if tool_name == "think_tool":
        # Check if this is planning or replanning based on args content
        reflection = args.get("reflection", "")
        if "replan" in reflection.lower() or "调整" in reflection:
            return "replanning"
        if "plan" in reflection.lower() or "规划" in reflection:
            return "planning"
    return None


def _format_thinking_content(tool_name: str, args: dict) -> str:
    """Extract a human-readable thinking step from a thinking tool call."""
    if tool_name == "route":
        agent = args.get("agent_name", "unknown")
        desc = args.get("task_description", "")
        return f"Routing to {agent}: {desc}"
    if tool_name == "think_tool":
        return args.get("reflection", str(args))
    return str(args)


def _format_sse(event: str, data: dict, event_counter: EventCounter | None = None) -> dict:
    """Format a single SSE event dict for sse-starlette EventSourceResponse.

    Args:
        event: Event type name.
        data: Event payload.
        event_counter: Optional counter for generating event IDs (for reconnection support).

    Returns:
        SSE event dict with optional 'id' field for reconnection.
    """
    result: dict[str, Any] = {"event": event, "data": json.dumps(data, ensure_ascii=False)}
    if event_counter is not None:
        result["id"] = event_counter.next_id()
    return result


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
    user_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream agent response as SSE events.

    Processes the LangGraph astream() output and yields SSE-formatted dicts.
    Shows output from the supervisor (direct answers) and specialist subgraph
    agents, filtering out internal routing mechanics.

    Enhanced to emit:
    - todos_updated: When TodoListMiddleware updates task list
    - task_spawned/task_completed: When SubAgentMiddleware delegates tasks
    - thinking events with type field (planning/replanning/routing)
    - tool_call events with task_id for parent task association

    Args:
        agent: The compiled supervisor graph.
        thread_id: Thread ID for conversation persistence.
        message: User message to send.

    Yields:
        SSE-formatted event dicts with sequential IDs for reconnection support.
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    # Checkpointer handles history automatically - just send the new message
    stream_input: dict = {"messages": [HumanMessage(content=message)]}

    # Event counter for SSE reconnection support (T011)
    event_counter = EventCounter()

    # Buffers for tool call streaming (args arrive as JSON fragments)
    tool_call_buffers: dict[str | int, dict] = {}
    displayed_tool_ids: set[str] = set()
    # Track hidden tool call IDs so we can also suppress their ToolMessage results
    hidden_tool_call_ids: set[str] = set()

    # Task tracking for task_spawned/task_completed events (T007, T008)
    active_tasks: dict[str, TaskTracker] = {}
    # Current task context for associating tool calls with tasks (T010)
    current_task_id: str | None = None

    # Previous todos state for change detection (T005, T006)
    previous_todos: list[dict] | None = None

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

            # --- UPDATES stream: process todos state changes (T005, T006) ---
            if current_stream_mode == "updates":
                if isinstance(data, dict):
                    # Check for todos state changes from TodoListMiddleware
                    for node_name, node_output in data.items():
                        if isinstance(node_output, dict):
                            todos = node_output.get("todos")
                            if todos is not None and isinstance(todos, list):
                                # Only emit if todos actually changed
                                if todos != previous_todos:
                                    previous_todos = todos
                                    yield _format_sse(
                                        "todos_updated",
                                        {
                                            "todos": [
                                                {
                                                    "content": t.get("content", ""),
                                                    "status": t.get("status", "pending"),
                                                }
                                                for t in todos
                                                if isinstance(t, dict)
                                            ],
                                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                        },
                                        event_counter,
                                    )
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

                # Skip results for thinking tools (think_tool)
                if tool_name in _THINKING_TOOLS or tool_id in hidden_tool_call_ids:
                    continue

                # Handle route tool completion - emit task_completed
                if tool_name == _ROUTE_TOOL and tool_id in active_tasks:
                    tracker = active_tasks.pop(tool_id)
                    tool_status = getattr(msg, "status", "success")
                    status = "success" if tool_status == "success" else "error"
                    yield _format_sse(
                        "task_completed",
                        tracker.to_completed_event(status),
                        event_counter,
                    )
                    # Clear current task context
                    if current_task_id == tool_id:
                        current_task_id = None
                    continue

                # Handle task tool completion (T008)
                if tool_name == _TASK_TOOL and tool_id in active_tasks:
                    tracker = active_tasks.pop(tool_id)
                    tool_status = getattr(msg, "status", "success")
                    status = "success" if tool_status == "success" else "error"
                    yield _format_sse(
                        "task_completed",
                        tracker.to_completed_event(status),
                        event_counter,
                    )
                    # Clear current task context
                    if current_task_id == tool_id:
                        current_task_id = None
                    continue

                # Skip todos tool results (internal)
                if tool_name == _TODOS_TOOL:
                    continue

                tool_status = getattr(msg, "status", "success")
                tool_content = _format_tool_content(msg.content)

                if tool_id:
                    event_data: dict[str, Any] = {
                        "id": tool_id,
                        "name": tool_name,
                        "status": tool_status,
                        "output": tool_content[:2000],
                    }
                    # Add task_id if within a task context (T010)
                    if current_task_id:
                        event_data["task_id"] = current_task_id
                    yield _format_sse("tool_call_result", event_data, event_counter)
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
                        yield _format_sse("text_delta", {"text": text}, event_counter)

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

                    # Emit thinking tools as "thinking" events with type (T009)
                    if buffer_name in _THINKING_TOOLS:
                        if buffer_id is not None and buffer_id not in displayed_tool_ids:
                            displayed_tool_ids.add(buffer_id)
                            hidden_tool_call_ids.add(buffer_id)
                            thinking_type = _get_thinking_type(buffer_name, parsed_args)
                            thinking_data: dict[str, Any] = {
                                "content": _format_thinking_content(
                                    buffer_name, parsed_args
                                ),
                            }
                            if thinking_type:
                                thinking_data["type"] = thinking_type
                            yield _format_sse("thinking", thinking_data, event_counter)
                        tool_call_buffers.pop(buffer_key, None)
                        continue

                    # Handle route tool call - emit thinking + task_spawned
                    if buffer_name == _ROUTE_TOOL:
                        if buffer_id is not None and buffer_id not in displayed_tool_ids:
                            displayed_tool_ids.add(buffer_id)
                            hidden_tool_call_ids.add(buffer_id)

                            agent_name = parsed_args.get("agent_name", "unknown")
                            task_desc = parsed_args.get("task_description", "")

                            # 1. Emit thinking event (maintain original behavior)
                            thinking_data = {
                                "content": f"Routing to {agent_name}: {task_desc}",
                                "type": "routing",
                            }
                            yield _format_sse("thinking", thinking_data, event_counter)

                            # 2. Emit task_spawned event (new behavior)
                            tracker = TaskTracker(
                                task_id=buffer_id,
                                subagent_type=agent_name,
                                description=task_desc,
                            )
                            active_tasks[buffer_id] = tracker
                            current_task_id = buffer_id
                            yield _format_sse("task_spawned", tracker.to_spawned_event(), event_counter)

                        tool_call_buffers.pop(buffer_key, None)
                        continue

                    # Handle task tool call - emit task_spawned (T007)
                    if buffer_name == _TASK_TOOL:
                        if buffer_id is not None and buffer_id not in displayed_tool_ids:
                            displayed_tool_ids.add(buffer_id)
                            hidden_tool_call_ids.add(buffer_id)
                            # Create task tracker
                            tracker = TaskTracker(
                                task_id=buffer_id,
                                subagent_type=parsed_args.get("subagent_type", "unknown"),
                                description=parsed_args.get("prompt", parsed_args.get("description", "")),
                            )
                            active_tasks[buffer_id] = tracker
                            current_task_id = buffer_id
                            yield _format_sse("task_spawned", tracker.to_spawned_event(), event_counter)
                        tool_call_buffers.pop(buffer_key, None)
                        continue

                    # Skip todos tool calls (internal)
                    if buffer_name == _TODOS_TOOL:
                        if buffer_id is not None:
                            hidden_tool_call_ids.add(buffer_id)
                        tool_call_buffers.pop(buffer_key, None)
                        continue

                    # Emit tool_call_start once per tool call ID (T010: with task_id)
                    if buffer_id is not None and buffer_id not in displayed_tool_ids:
                        displayed_tool_ids.add(buffer_id)
                        tool_event_data: dict[str, Any] = {
                            "id": buffer_id,
                            "name": buffer_name,
                            "args": parsed_args,
                        }
                        # Add task_id if within a task context (T010)
                        if current_task_id:
                            tool_event_data["task_id"] = current_task_id
                        yield _format_sse("tool_call_start", tool_event_data, event_counter)

                    tool_call_buffers.pop(buffer_key, None)

        # Complete any remaining active tasks before done event (route tool fix)
        # The route tool returns a Command object which doesn't generate ToolMessage,
        # so we need to clean up active tasks when the stream ends
        for task_id, tracker in list(active_tasks.items()):
            yield _format_sse(
                "task_completed",
                tracker.to_completed_event("success"),
                event_counter,
            )
        active_tasks.clear()

    except Exception as e:
        yield _format_sse("error", {"message": str(e)}, event_counter)

    yield _format_sse("done", {}, event_counter)
