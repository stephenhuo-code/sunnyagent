"""FastAPI application for the deep research chat interface."""

import atexit
import logging
import signal
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sse_starlette.sse import EventSourceResponse

# Load environment variables early
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.supervisor import build_supervisor
from backend.registry import AGENT_REGISTRY
from backend.skills import SKILL_REGISTRY
from backend.models import ChatRequest, ThreadCreate
from backend.stream_handler import stream_agent_response
from backend.tools.container_pool import get_pool, shutdown_pool, cleanup_all_sunnyagent_containers
from backend.auth.router import router as auth_router, users_router
from backend.auth.dependencies import get_current_user
from backend.auth.models import UserInfo
from backend.conversations.router import router as conversations_router
from backend.conversations.database import touch_conversation, get_conversation_by_thread, create_conversation
from backend.auth.database import init_default_admin
from backend.db import init_pool, close_pool, init_tables
from backend.files import database as files_db

# Environment variables already loaded above

# Global state
_agent = None
_checkpointer = None


def _sync_cleanup():
    """同步清理，用于 atexit 和信号处理"""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(cleanup_all_sunnyagent_containers())
        loop.close()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


def _signal_handler(signum, frame):
    """处理终止信号"""
    logger.info(f"Received signal {signum}, cleaning up...")
    _sync_cleanup()
    raise SystemExit(0)


# 注册处理器
atexit.register(_sync_cleanup)
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


async def _create_checkpointer():
    """Create the appropriate checkpointer based on environment."""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Use PostgreSQL for production
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        logger.info("Using PostgreSQL checkpointer")
        return await AsyncPostgresSaver.from_conn_string(database_url)
    else:
        # Fall back to SQLite for development
        logger.info("Using SQLite checkpointer (no DATABASE_URL set)")
        db_path = Path(__file__).resolve().parent.parent / "threads.db"
        return await AsyncSqliteSaver.from_conn_string(str(db_path)).__aenter__()


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

    # Initialize database connection pool (for users/conversations)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        await init_pool()
        logger.info("PostgreSQL connection pool initialized")

        # Initialize tables (users, conversations, files)
        try:
            await init_tables()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.warning(f"Could not initialize tables: {e}")

        # Create default admin if no users exist
        try:
            if await init_default_admin():
                logger.info("Default admin user created")
        except Exception as e:
            logger.warning(f"Could not initialize default admin: {e}")

    # Initialize checkpointer based on environment
    if database_url:
        # Use PostgreSQL for production
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            logger.info("Using PostgreSQL checkpointer")
            async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
                # Setup the checkpointer tables
                await saver.setup()
                _checkpointer = saver
                _agent = build_supervisor(checkpointer=_checkpointer)
                yield
                _agent = None
                _checkpointer = None
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
            raise
    else:
        # Fall back to SQLite for development
        logger.info("Using SQLite checkpointer (no DATABASE_URL set)")
        db_path = Path(__file__).resolve().parent.parent / "threads.db"
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
            _checkpointer = saver
            _agent = build_supervisor(checkpointer=_checkpointer)
            yield
            _agent = None
            _checkpointer = None

    # Cleanup
    if database_url:
        await close_pool()
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

# Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(conversations_router)


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
async def chat(request: ChatRequest, current_user: UserInfo = Depends(get_current_user)):
    """Send a message and stream the agent's response as SSE events.

    Routing priority:
    1. If request.skill is set, inject skill instructions and use general agent
    2. If request.agent is set, route directly to that agent (skip supervisor)
    3. Otherwise, use the supervisor for intent-based routing
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
        try:
            await create_conversation(current_user.id, request.thread_id, title)
        except Exception as e:
            logger.warning(f"Failed to create conversation for thread {request.thread_id}: {e}")

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
        message = f"[SKILL: {request.skill}]\n{skill_instructions}\n---\nUser request: {message}"

    # Direct agent routing: /command → inject directive for supervisor to route
    if request.agent and request.agent in AGENT_REGISTRY:
        message = f"[ROUTE_TO: {request.agent}]\n{message}"

    # Always use supervisor to maintain checkpointer consistency
    target = _agent

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
async def create_thread(current_user: UserInfo = Depends(get_current_user)) -> ThreadCreate:
    """Create a new thread and return its ID.

    Note: The thread itself is just an ID. The conversation record
    is created when the first message is sent in /api/chat.
    """
    thread_id = uuid.uuid4().hex[:8]
    return ThreadCreate(thread_id=thread_id)


@app.get("/api/threads/{thread_id}/history")
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
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserInfo = Depends(get_current_user)
):
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

    # Record file in database (if PostgreSQL is available)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            await files_db.create_file(
                user_id=current_user.id,
                file_id=file_id,
                original_name=file.filename or "uploaded_file",
                content_type=file.content_type,
                size_bytes=len(content),
                storage_path=str(file_path)
            )
        except Exception as e:
            logger.warning(f"Failed to record file in database: {e}")

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "download_url": f"/api/files/{file_id}/{file.filename}",
    }


@app.get("/api/files/{file_id}/download")
async def download_file_by_id(
    file_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Download a file by its ID.

    Permission: User must own the file.
    """
    # Check permission via database if PostgreSQL is available
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        file_record = await files_db.get_file(file_id, current_user.id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = Path(file_record["storage_path"])
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(
            str(file_path),
            filename=file_record["original_name"],
            media_type=file_record["content_type"] or "application/octet-stream",
        )

    # Fallback for SQLite mode (no permission check)
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
async def get_file_content(
    file_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Get file content for preview (text files only).

    Permission: User must own the file.
    """
    # Check permission via database if PostgreSQL is available
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        file_record = await files_db.get_file(file_id, current_user.id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = Path(file_record["storage_path"])
    else:
        # Fallback for SQLite mode (no permission check)
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
async def download_file(
    file_id: str,
    filename: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """Download a generated file by file_id and filename.

    Permission: User must own the file.

    Note: This route MUST be defined after /api/files/{file_id}/content
    and /api/files/{file_id}/download to avoid path conflicts.
    """
    # Check permission via database if PostgreSQL is available
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        file_record = await files_db.get_file(file_id, current_user.id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

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
