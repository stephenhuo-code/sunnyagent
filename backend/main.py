"""FastAPI application for the deep research chat interface."""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sse_starlette.sse import EventSourceResponse

from backend.supervisor import build_supervisor
from backend.registry import AGENT_REGISTRY
from backend.skills import SKILL_REGISTRY
from backend.models import ChatRequest, ThreadCreate
from backend.stream_handler import stream_agent_response
from backend.tools.container_pool import get_pool, shutdown_pool

# Load environment variables from .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Global state
_agent = None
_checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage agent and checkpointer lifecycle."""
    global _agent, _checkpointer

    # Initialize container pool
    try:
        pool = await get_pool()
        logger.info(f"Container pool initialized: {pool.stats}")
    except Exception as e:
        logger.warning(f"Container pool failed to initialize: {e}")

    db_path = Path(__file__).resolve().parent.parent / "threads.db"
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        _checkpointer = saver
        _agent = build_supervisor(checkpointer=_checkpointer)

        yield

        # Cleanup
        _agent = None
        _checkpointer = None

    # Shutdown container pool
    await shutdown_pool()


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
    """Return agents that should appear in the UI selector."""
    return [
        {"name": entry.name, "description": entry.description, "icon": entry.icon}
        for entry in AGENT_REGISTRY.values()
        if entry.show_in_selector
    ]


@app.get("/api/skills")
async def list_skills():
    """Return all registered skills (name + description only)."""
    return [
        {"name": entry.name, "description": entry.description}
        for entry in SKILL_REGISTRY.values()
    ]


@app.get("/api/skills/{name}")
async def get_skill(name: str):
    """Return full skill details including instructions."""
    if name not in SKILL_REGISTRY:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")
    entry = SKILL_REGISTRY[name]
    return {
        "name": entry.name,
        "description": entry.description,
        "instructions": entry.load_instructions(),
    }


def get_uploaded_file_info(file_id: str) -> dict | None:
    """获取上传文件的元数据"""
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
    if not file_dir.exists():
        return None

    files = list(file_dir.iterdir())
    if not files:
        return None

    file_path = files[0]
    return {
        "file_id": file_id,
        "filename": file_path.name,
        "size": file_path.stat().st_size,
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a message and stream the agent's response as SSE events.

    Routing priority:
    1. If request.skill is set, inject skill instructions and use general agent
    2. If request.agent is set, route directly to that agent (skip supervisor)
    3. Otherwise, use the supervisor for intent-based routing
    """
    message = request.message

    # 如果有上传文件，注入元数据（不是内容）
    if request.file_ids:
        file_info_list = []
        for file_id in request.file_ids:
            info = get_uploaded_file_info(file_id)
            if info:
                file_info_list.append(info)

        if file_info_list:
            files_desc = "\n".join(
                f"- {f['filename']} (ID: {f['file_id']}, 大小: {f['size']} bytes)"
                for f in file_info_list
            )
            message = f"""[用户上传了以下文件]
{files_desc}

你可以使用 read_uploaded_file(file_id) 工具读取文件内容。

---
用户消息: {request.message}"""

    # Skill-based routing: inject skill instructions into the message
    if request.skill and request.skill in SKILL_REGISTRY:
        skill_instructions = SKILL_REGISTRY[request.skill].load_instructions()
        message = f"[SKILL: {request.skill}]\n{skill_instructions}\n---\nUser request: {request.message}"
        target = AGENT_REGISTRY["general"].graph
    # Direct agent routing: /command → specific agent
    elif request.agent and request.agent in AGENT_REGISTRY:
        target = AGENT_REGISTRY[request.agent].graph
    # File upload routing: use general agent (only it has read_uploaded_file tool)
    elif request.file_ids:
        target = AGENT_REGISTRY["general"].graph
    else:
        target = _agent  # Supervisor handles routing

    async def event_generator():
        try:
            async for event in stream_agent_response(
                target, request.thread_id, message
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


# File upload constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv",  # 文本文件
    ".pdf",  # PDF
    ".doc", ".docx",  # Word
    ".ppt", ".pptx",  # PowerPoint
    ".xls", ".xlsx",  # Excel
}


@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and return its metadata."""
    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Generate file ID and save
    file_id = uuid.uuid4().hex[:8]
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / (file.filename or "uploaded_file")

    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "download_url": f"/api/files/{file_id}/{file.filename}",
    }


@app.get("/api/files/{file_id}/download")
async def download_file_by_id(file_id: str):
    """Download a file by its ID."""
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")

    if not file_dir.exists():
        raise HTTPException(status_code=404, detail="File not found")

    files = list(file_dir.iterdir())
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = files[0]
    return FileResponse(
        str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@app.get("/api/files/{file_id}/content")
async def get_file_content(file_id: str):
    """Get file content for preview (text files only)."""
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")

    if not file_dir.exists():
        raise HTTPException(status_code=404, detail="File not found")

    files = list(file_dir.iterdir())
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = files[0]

    # Only support text file preview
    text_extensions = {".txt", ".md", ".json", ".csv"}
    if file_path.suffix.lower() not in text_extensions:
        raise HTTPException(
            status_code=400,
            detail="Preview not supported for this file type"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Cannot read file as text"
        )

    return {"content": content, "filename": file_path.name}


@app.get("/api/files/{file_id}/{filename}")
async def download_file(file_id: str, filename: str):
    """Download a generated file by file_id and filename.

    Note: This route MUST be defined after /api/files/{file_id}/content
    and /api/files/{file_id}/download to avoid path conflicts.
    """
    import os

    file_path = f"/tmp/sunnyagent_files/{file_id}/{filename}"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


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
