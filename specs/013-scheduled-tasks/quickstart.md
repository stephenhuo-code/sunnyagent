# Quickstart: 定时任务功能 (Scheduled Tasks)

**Feature**: 013-scheduled-tasks
**Date**: 2026-02-22

## Prerequisites

- PostgreSQL running (`docker compose up -d`)
- Backend dependencies installed (`uv sync`)
- Frontend dependencies installed (`cd frontend && npm install`)

## Dependencies

### Backend (add to pyproject.toml)

```toml
[project.dependencies]
# Add these dependencies
apscheduler = ">=4.0.0"
```

**Note**: `sqlalchemy[asyncio]` and `asyncpg` are already in the project.

### Frontend

No additional dependencies required. Uses existing React, TypeScript, and Tailwind CSS.

## Database Migration

```bash
# Create migration
cd infra && uv run alembic revision -m "create_scheduled_tasks_tables"

# Apply migration
cd infra && uv run alembic upgrade head
```

## Configuration

### Environment Variables

No new environment variables required. Scheduled tasks use existing:
- `DATABASE_URL` - PostgreSQL connection
- `LANGFUSE_*` - Tracing configuration

### Data Directory

Create the data directory structure:

```bash
mkdir -p data/scheduled_tasks
```

The user directories are created automatically when users create tasks.

## Development Workflow

### 1. Start Infrastructure

```bash
docker compose up -d  # PostgreSQL + Langfuse
```

### 2. Apply Migration

```bash
cd infra && uv run alembic upgrade head
```

### 3. Start Backend

```bash
uv run uvicorn backend.main:app --reload --port 8008
```

### 4. Start Frontend

```bash
cd frontend && npm run dev
```

### 5. Test Scheduled Tasks

Access the Admin Panel → Scheduled Tasks to create and manage tasks.

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scheduled-tasks` | List user's tasks |
| POST | `/api/scheduled-tasks` | Create a task |
| GET | `/api/scheduled-tasks/{id}` | Get task details |
| PATCH | `/api/scheduled-tasks/{id}` | Update a task |
| DELETE | `/api/scheduled-tasks/{id}` | Delete a task |
| POST | `/api/scheduled-tasks/{id}/enable` | Enable a task |
| POST | `/api/scheduled-tasks/{id}/disable` | Disable a task |
| POST | `/api/scheduled-tasks/{id}/run` | Run task now |
| GET | `/api/scheduled-tasks/{id}/executions` | List executions |
| GET | `/api/scheduled-tasks/{id}/executions/{eid}` | Get execution detail |
| GET | `/api/admin/scheduled-tasks` | Admin: list all tasks |
| GET | `/api/admin/scheduled-tasks/settings` | Get global settings |
| PATCH | `/api/admin/scheduled-tasks/settings` | Update global settings |

## Testing

### Run Backend Tests

```bash
uv run pytest backend/tests/scheduled_tasks/ -v
```

### Run Frontend Tests

```bash
cd frontend && npm run test
```

## File Structure

```
backend/
├── scheduled_tasks/
│   ├── __init__.py
│   ├── models.py           # Pydantic models
│   ├── database.py         # Repository layer
│   ├── service.py          # Business logic
│   ├── scheduler.py        # APScheduler setup
│   ├── executor.py         # Task execution
│   └── router.py           # API endpoints

frontend/src/
├── api/
│   └── scheduledTasks.ts
├── components/Admin/
│   └── ScheduledTasks/
│       ├── index.tsx
│       ├── TaskList.tsx
│       └── TaskForm.tsx
└── hooks/
    └── useScheduledTasks.ts

data/
└── scheduled_tasks/        # Runtime data (gitignored)

infra/migrations/versions/
└── xxx_create_scheduled_tasks_tables.py
```

## Smoke Test Checklist

- [ ] Create a "once" scheduled task → Task appears in list
- [ ] Create a "daily" task → APScheduler job registered
- [ ] Toggle task enable/disable → APScheduler job paused/resumed
- [ ] Click "Run Now" → Task executes immediately
- [ ] View execution history → Shows execution records
- [ ] Delete task → Task removed, script file deleted
- [ ] Admin view → Can see all users' tasks
