#!/usr/bin/env python3
"""
Migrate LangGraph checkpoints from SQLite (threads.db) to PostgreSQL.

This script migrates the checkpoints and writes tables from the local SQLite database
to the PostgreSQL database specified by DATABASE_URL environment variable.

Usage:
    python scripts/migrate_sqlite_to_pg.py

Requirements:
    - SQLite database exists at threads.db
    - DATABASE_URL environment variable is set
    - PostgreSQL database is accessible and has the checkpoint tables created
"""

import asyncio
import os
import sqlite3
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def migrate_checkpoints():
    """Migrate checkpoints and writes from SQLite to PostgreSQL."""
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Check SQLite database exists
    sqlite_path = Path(__file__).resolve().parent.parent / "threads.db"
    if not sqlite_path.exists():
        print(f"INFO: No SQLite database found at {sqlite_path}, nothing to migrate")
        return

    # Connect to SQLite
    print(f"Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to PostgreSQL
    print(f"Connecting to PostgreSQL...")
    pg_conn = await asyncpg.connect(database_url)

    try:
        # Check if SQLite has the expected tables
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        if "checkpoints" not in tables:
            print("INFO: No checkpoints table in SQLite, nothing to migrate")
            return

        # Check if langgraph checkpoint tables exist in PostgreSQL
        pg_tables = await pg_conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name IN ('checkpoints', 'checkpoint_writes')
        """)
        pg_table_names = {row["table_name"] for row in pg_tables}

        if not pg_table_names:
            print("INFO: LangGraph checkpoint tables don't exist in PostgreSQL yet.")
            print("      They will be created automatically when the application starts.")
            print("      Run the application first, then run this migration script.")
            return

        # Migrate checkpoints table
        print("Migrating checkpoints...")
        cursor.execute("SELECT * FROM checkpoints")
        checkpoints = cursor.fetchall()

        if checkpoints:
            # Get column names
            columns = [description[0] for description in cursor.description]
            print(f"  Found {len(checkpoints)} checkpoints to migrate")

            migrated = 0
            for row in checkpoints:
                try:
                    # Insert into PostgreSQL
                    values = [row[col] for col in columns]
                    placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
                    column_names = ", ".join(columns)

                    await pg_conn.execute(
                        f"""
                        INSERT INTO checkpoints ({column_names})
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                        """,
                        *values
                    )
                    migrated += 1
                except Exception as e:
                    print(f"  Warning: Failed to migrate checkpoint: {e}")

            print(f"  Migrated {migrated}/{len(checkpoints)} checkpoints")
        else:
            print("  No checkpoints to migrate")

        # Migrate writes table if it exists
        if "writes" in tables and "checkpoint_writes" in pg_table_names:
            print("Migrating checkpoint writes...")
            cursor.execute("SELECT * FROM writes")
            writes = cursor.fetchall()

            if writes:
                columns = [description[0] for description in cursor.description]
                print(f"  Found {len(writes)} writes to migrate")

                migrated = 0
                for row in writes:
                    try:
                        values = [row[col] for col in columns]
                        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
                        column_names = ", ".join(columns)

                        await pg_conn.execute(
                            f"""
                            INSERT INTO checkpoint_writes ({column_names})
                            VALUES ({placeholders})
                            ON CONFLICT DO NOTHING
                            """,
                            *values
                        )
                        migrated += 1
                    except Exception as e:
                        print(f"  Warning: Failed to migrate write: {e}")

                print(f"  Migrated {migrated}/{len(writes)} writes")
            else:
                print("  No writes to migrate")

        print("\nMigration completed successfully!")
        print(f"  You can now safely remove {sqlite_path} (after verifying data)")

    finally:
        sqlite_conn.close()
        await pg_conn.close()


def main():
    """Main entry point."""
    print("=== LangGraph Checkpoint Migration: SQLite → PostgreSQL ===\n")
    asyncio.run(migrate_checkpoints())


if __name__ == "__main__":
    main()
