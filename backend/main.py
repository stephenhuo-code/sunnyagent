"""FastAPI application for the deep research chat interface."""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sse_starlette.sse import EventSourceResponse

from backend.supervisor import build_supervisor
from backend.registry import AGENT_REGISTRY
from backend.models import ChatRequest, ThreadCreate
from backend.stream_handler import stream_agent_response

# Load environment variables from .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Global state
_agent = None
_checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage agent and checkpointer lifecycle."""
    global _agent, _checkpointer

    db_path = Path(__file__).resolve().parent.parent / "threads.db"
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        _checkpointer = saver
        _agent = build_supervisor(checkpointer=_checkpointer)

        yield

        # Cleanup
        _agent = None
        _checkpointer = None


app = FastAPI(title="Deep Research Chat", lifespan=lifespan)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3008", "http://127.0.0.1:3008"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/agents")
async def list_agents():
    """Return all registered agents (name + description)."""
    return [
        {"name": entry.name, "description": entry.description}
        for entry in AGENT_REGISTRY.values()
    ]


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a message and stream the agent's response as SSE events.

    When request.agent is set, route directly to that agent (skip supervisor).
    Otherwise, use the supervisor for intent-based routing.
    """
    # Direct routing: /command → specific agent
    if request.agent and request.agent in AGENT_REGISTRY:
        target = AGENT_REGISTRY[request.agent].graph
    else:
        target = _agent  # Supervisor handles routing

    async def event_generator():
        try:
            async for event in stream_agent_response(
                target, request.thread_id, request.message
            ):
                yield event
        except Exception:
            logger.exception("Error streaming agent response")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        ping=15,  # Keepalive every 15 seconds
    )


@app.post("/api/threads")
async def create_thread() -> ThreadCreate:
    """Create a new thread and return its ID."""
    thread_id = uuid.uuid4().hex[:8]
    return ThreadCreate(thread_id=thread_id)


@app.get("/api/threads/{thread_id}/history")
async def get_thread_history(thread_id: str):
    """Get message history for a thread."""
    if _agent is None:
        return {"messages": []}

    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await _agent.aget_state(config)
        if state and state.values:
            messages = []
            for msg in state.values.get("messages", []):
                role = "user" if msg.type == "human" else "assistant"
                if msg.type in ("human", "ai"):
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    messages.append({"role": role, "content": content})
            return {"messages": messages}
    except Exception:
        pass
    return {"messages": []}


# Serve frontend static files in production
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve the React frontend for non-API routes."""
        file_path = _frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_frontend_dist / "index.html"))
