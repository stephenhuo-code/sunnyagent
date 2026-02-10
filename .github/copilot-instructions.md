# GitHub Copilot Instructions for SunnyAgent

## Required Reading

Before writing any code, **MUST READ**:

1. `docs/architecture.md` — Complete system architecture and constraints

This document contains:
- System overview and tech stack
- Supervisor + Deep Agents pattern
- Streaming pipeline
- Database schema
- Authentication flow
- Layer dependencies and prohibited patterns
- Naming conventions
- API endpoints

## Quick Reference

### Layer Dependencies (Top to Bottom Only)

```
API → Agent → Service → Repository → Database
```

NEVER import upward.

### Prohibited Patterns

- Do NOT import `asyncpg` or `db.py` directly in Agent files
- Do NOT hardcode SQL in Agent files
- Do NOT skip `register_agent()` when creating new agents
- Do NOT duplicate utility functions (use `shared/utils.py`)

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Agent file | `<name>_agent.py` | `knowledge_agent.py` |
| Service class | `<Name>Service` | `KnowledgeService` |
| Repository class | `<Name>Repository` | `FileRepository` |

### Tech Stack

- Backend: Python 3.11+, FastAPI, LangGraph, asyncpg
- Frontend: React 19, TypeScript 5.7, Vite 7
- Database: PostgreSQL 15

### Before Submitting Code

1. Run `uv run pyright` for type checking
2. Run `uv run pytest` for tests
3. Verify dependency direction is correct

### Shared Resources (Modify with Caution)

- `db.py` — Requires team review
- `registry.py` — Requires team review
- `shared/` — Requires 2 approvals
- `contracts/` — Requires architecture review

## Development Commands

```bash
# Backend
uv sync
uv run uvicorn backend.main:app --reload --port 8008

# Frontend
cd frontend && npm install
cd frontend && npm run dev

# Database
docker compose up -d
cd infra && uv run alembic upgrade head
```
