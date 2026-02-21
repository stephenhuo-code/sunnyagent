"""Chat and thread management API endpoints."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.models import ChatRequest, ThreadCreate
from backend.registry import AGENT_REGISTRY
from backend.skills import SKILL_REGISTRY
from backend.aime import stream_aime_response
from backend.conversations.database import (
    touch_conversation,
    get_conversation_by_thread,
    create_conversation,
)
from backend.aime.context import AgentContext, SessionMetadata, FileContext, FileInfo, get_file_type
from backend.checkpointer_store import get_history_graph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def get_uploaded_file_info(file_id: str) -> FileInfo | None:
    """Get uploaded file metadata (returns FileInfo object)."""
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
    if not file_dir.exists():
        return None

    files = list(file_dir.iterdir())
    if not files:
        return None

    file_path = files[0]
    return FileInfo(
        file_id=file_id,
        filename=file_path.name,
        file_type=get_file_type(file_path.name),
        project_id=None,
    )


async def get_project_file_info(file_id: str, project_id: str) -> FileInfo | None:
    """Get project file metadata (returns FileInfo object)."""
    from backend.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT pf.original_name, pf.file_id
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.file_id = $1
              AND p.id = $2
              AND p.is_deleted = FALSE
            """,
            file_id,
            project_id,
        )
        if not row:
            return None
        return FileInfo(
            file_id=file_id,
            filename=row["original_name"],
            file_type=get_file_type(row["original_name"]),
            project_id=project_id,
        )


@router.post("/api/chat")
async def chat(request: ChatRequest, current_user: UserInfo = Depends(get_current_user)):
    """Send a message and stream the agent's response as SSE events.

    Routing priority:
    1. If request.skill is set, inject skill instructions (handled by AIME)
    2. If request.agent is set, route directly to that agent (skip supervisor)
    3. Otherwise, use the supervisor for intent-based routing

    Context model:
    - Files are passed as metadata only (not content) to avoid intent pollution
    - Agent uses read_file tool to get actual content when needed
    """
    message = request.message

    # Check if this thread has an associated conversation
    # If not, create one (for threads created before conversation management was added)
    existing_conv = await get_conversation_by_thread(request.thread_id, current_user.id)
    if existing_conv:
        # Update the conversation's updated_at timestamp
        await touch_conversation(request.thread_id, current_user.id)
    else:
        # Create a new conversation for this thread (auto-title from first 50 chars of message)
        title = request.message[:50] if request.message else "New Conversation"
        # Parse project_id if provided
        project_uuid = None
        if request.project_id:
            try:
                project_uuid = uuid.UUID(request.project_id)
            except ValueError:
                logger.warning(f"Invalid project_id format: {request.project_id}")
        try:
            await create_conversation(current_user.id, request.thread_id, title, project_uuid)
        except Exception as e:
            logger.warning(f"Failed to create conversation for thread {request.thread_id}: {e}")

    # Build AgentContext with file metadata (NOT content) - Layer 3 & 5
    files: list[FileInfo] = []

    # Collect uploaded file metadata
    if request.file_ids:
        for file_id in request.file_ids:
            info = get_uploaded_file_info(file_id)
            if info:
                files.append(info)

    # Collect project file metadata
    if request.project_file_ids and request.project_id:
        for file_id in request.project_file_ids:
            info = await get_project_file_info(file_id, request.project_id)
            if info:
                files.append(info)

    # Create AgentContext
    context = AgentContext(
        session=SessionMetadata(
            user_id=str(current_user.id),
            thread_id=request.thread_id,
            project_id=request.project_id,
        ),
        files=FileContext(files=files),
        explicit_agent=request.agent if request.agent and request.agent in AGENT_REGISTRY else None,
        skill=request.skill,
    )

    # Note: Context is NOT injected into message here to avoid intent pollution.
    # Context will be injected at execution time in planner.py (_handle_delegate, _handle_plan)
    if files:
        logger.info(f"Context: {len(files)} files (will be injected at execution time)")

    # Skill-based routing: inject skill instructions into the message
    if request.skill and request.skill in SKILL_REGISTRY:
        skill_instructions = SKILL_REGISTRY[request.skill].load_instructions()
        message = f"[SKILL: {request.skill}]\n{skill_instructions}\n---\nUser request: {message}"

    # Direct agent routing: /command → inject directive for supervisor to route
    if request.agent and request.agent in AGENT_REGISTRY:
        message = f"[ROUTE_TO: {request.agent}]\n{message}"

    async def event_generator():
        try:
            # Use AIME architecture for intent-driven routing
            # Pass AgentContext for structured context handling
            async for event in stream_aime_response(
                thread_id=request.thread_id,
                message=message,
                context=context,
            ):
                yield event
        except Exception:
            logger.exception("Error streaming agent response")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        ping=15,  # Keepalive every 15 seconds
    )


@router.post("/api/threads")
async def create_thread(current_user: UserInfo = Depends(get_current_user)) -> ThreadCreate:
    """Create a new thread and return its ID.

    Note: The thread itself is just an ID. The conversation record
    is created when the first message is sent in /api/chat.
    """
    thread_id = uuid.uuid4().hex[:8]
    return ThreadCreate(thread_id=thread_id)


@router.get("/api/threads/{thread_id}/history")
async def get_thread_history(
    thread_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Get message history for a thread.

    Permission: User must own the conversation associated with this thread.
    """
    # Verify that the thread belongs to the current user via conversation
    conversation = await get_conversation_by_thread(thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Thread not found")

    history_graph = get_history_graph()
    if history_graph is None:
        return {"messages": []}

    from langchain_core.runnables.config import RunnableConfig
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    try:
        state = await history_graph.aget_state(config)
        if state and state.values:
            messages = []
            for msg in state.values.get("messages", []):
                role = "user" if msg.type == "human" else "assistant"
                if msg.type in ("human", "ai"):
                    # Extract text from content blocks (Claude returns list of content blocks)
                    if isinstance(msg.content, str):
                        content = msg.content
                    elif isinstance(msg.content, list):
                        parts = []
                        for item in msg.content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                parts.append(item.get("text", ""))
                        content = "".join(parts)
                    else:
                        content = str(msg.content)
                    messages.append({"role": role, "content": content})
            return {"messages": messages}
    except Exception:
        pass
    return {"messages": []}
