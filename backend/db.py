"""PostgreSQL database connection pool management."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

# Global connection pool
_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool
    if _pool is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    return await init_pool()


async def close_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def execute(query: str, *args) -> str:
    """Execute a query and return status."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args) -> list[asyncpg.Record]:
    """Fetch all rows from a query."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> asyncpg.Record | None:
    """Fetch a single row from a query."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Fetch a single value from a query."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)


async def init_tables() -> None:
    """Initialize database tables if they don't exist."""
    async with get_connection() as conn:
        # Create users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(20) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(10) NOT NULL DEFAULT 'user',
                status VARCHAR(10) NOT NULL DEFAULT 'active',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Create conversations table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                thread_id VARCHAR(8) NOT NULL,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(50) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_thread ON conversations(thread_id)
        """)

        # Create files table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                file_id VARCHAR(8) UNIQUE NOT NULL,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
                original_name VARCHAR(255) NOT NULL,
                content_type VARCHAR(100),
                size_bytes BIGINT NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_conversation ON files(conversation_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_file_id ON files(file_id)
        """)
