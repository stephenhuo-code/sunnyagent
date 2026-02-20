"""FastAPI application for the deep research chat interface."""

import asyncio
import atexit
import logging
import os
import signal
from contextlib import asynccontextmanager
from pathlib import Path

# Configure logging early - before any module imports
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Load environment variables early
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.supervisor import build_supervisor
from backend.tools.container_pool import get_pool, shutdown_pool, cleanup_all_sunnyagent_containers
from backend.auth.database import init_default_admin
from backend.db import init_pool, close_pool, init_tables
from backend.llm import validate_config, get_current_provider
from backend.aime.context_manager import ContextManager, CONTEXT_CLEANUP_INTERVAL
from backend.api import register_routers
from backend.core.chat import set_agent
from backend.services.langfuse_service import get_langfuse_service, reset_langfuse_service
from backend.checkpointer_store import set_checkpointer, clear_checkpointer

# Global state
_agent = None
_checkpointer = None
_context_manager = None
_cleanup_task = None
_langfuse_service = None


def _sync_cleanup():
    """Synchronous cleanup for atexit and signal handlers."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(cleanup_all_sunnyagent_containers())
        loop.close()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


def _signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, cleaning up...")
    _sync_cleanup()
    raise SystemExit(0)


# Register handlers
atexit.register(_sync_cleanup)
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


async def _context_cleanup_task(context_manager: ContextManager):
    """Background task for periodic context cleanup."""
    while True:
        await asyncio.sleep(CONTEXT_CLEANUP_INTERVAL)
        try:
            deleted = await context_manager.cleanup_expired()
            if deleted > 0:
                logger.info(f"Context cleanup: deleted {deleted} expired entries")
        except Exception as e:
            logger.error(f"Context cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage agent and checkpointer lifecycle."""
    global _agent, _checkpointer, _context_manager, _cleanup_task, _langfuse_service

    # Validate LLM configuration early (fail fast)
    try:
        validate_config()
        provider = get_current_provider()
        logger.info(f"Using LLM provider: {provider.value}")
    except (ValueError, EnvironmentError) as e:
        logger.error(f"LLM configuration error: {e}")
        raise

    # Initialize Langfuse observability (graceful degradation if unavailable)
    try:
        _langfuse_service = get_langfuse_service()
        if _langfuse_service.enabled:
            logger.info(f"Langfuse observability enabled at {_langfuse_service.base_url}")
        else:
            logger.info("Langfuse observability disabled (not configured or unavailable)")
    except Exception as e:
        logger.warning(f"Langfuse initialization failed: {e}, continuing without observability")

    # Log AIME architecture status
    logger.info("AIME architecture enabled - intent-driven multi-agent execution")

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

        # Initialize context manager and start background cleanup task (T036)
        _context_manager = ContextManager()
        _cleanup_task = asyncio.create_task(_context_cleanup_task(_context_manager))
        logger.info(
            f"Context cleanup task started (interval: {CONTEXT_CLEANUP_INTERVAL}s)"
        )

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

                # Set shared checkpointer for all agents
                set_checkpointer(_checkpointer)

                _agent = build_supervisor(checkpointer=_checkpointer)
                # Set agent reference for chat router
                set_agent(_agent)
                yield
                _agent = None
                _checkpointer = None

                # Clear shared checkpointer
                clear_checkpointer()
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
            raise
    else:
        # Fall back to SQLite for development
        logger.info("Using SQLite checkpointer (no DATABASE_URL set)")
        db_path = Path(__file__).resolve().parent.parent / "threads.db"
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
            _checkpointer = saver

            # Set shared checkpointer for all agents
            set_checkpointer(_checkpointer)

            _agent = build_supervisor(checkpointer=_checkpointer)
            # Set agent reference for chat router
            set_agent(_agent)
            yield
            _agent = None
            _checkpointer = None

            # Clear shared checkpointer
            clear_checkpointer()

    # Cleanup
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Context cleanup task stopped")

    # Flush Langfuse traces before shutdown
    if _langfuse_service and _langfuse_service.enabled:
        _langfuse_service.flush()
        logger.info("Langfuse traces flushed")
    reset_langfuse_service()

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

# Register all API routers
register_routers(app)

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
