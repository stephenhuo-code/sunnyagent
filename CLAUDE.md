# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SunnyAgent — a full-stack web app (FastAPI + React) with a LangGraph supervisor that routes user messages to specialized deep agents for web research, SQL database queries, multi-step orchestration, file processing, and sandboxed code execution. Includes user authentication, conversation management, and admin user management.

## Development Commands

### Prerequisites
```bash
docker compose up -d          # Start PostgreSQL database
```

### Backend (Python, managed with `uv`)
```bash
uv sync                                                  # Install dependencies
uv run uvicorn backend.main:app --reload --port 8008     # Run dev server
```

### Frontend (React + Vite)
```bash
cd frontend && npm install    # Install dependencies
cd frontend && npm run dev    # Dev server on port 3008 (proxies /api → 8008)
cd frontend && npm run build  # Production build to frontend/dist/
```

### Database Migrations (Alembic)
```bash
cd infra && uv run alembic upgrade head    # Apply all migrations
cd infra && uv run alembic downgrade -1    # Rollback last migration
cd infra && uv run alembic revision -m "description"  # Create new migration
```

### Type Checking
```bash
uv run pyright              # Python type checking (pyrightconfig.json)
cd frontend && npx tsc      # TypeScript checking
```

### Environment Variables (.env in project root)

**Required:**
- `ANTHROPIC_API_KEY` — Claude API key
- `TAVILY_API_KEY` — for web research
- `DATABASE_URL` — PostgreSQL connection string (e.g., `postgresql://sunnyagent:sunnyagent123@localhost:5432/sunnyagent`)

**Optional:**
- `OPENAI_API_KEY` — if using GPT models
- `JWT_SECRET_KEY` — for JWT signing (auto-generated if not set)
- `JWT_EXPIRATION` — token expiration in seconds (default: 86400 = 24h)
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — default admin credentials on first startup

## Architecture

### Supervisor + Deep Agents Pattern

The core pattern is a **LangGraph StateGraph** where a supervisor node routes to specialist subgraph nodes:

```
User → Supervisor (LLM router with route() tool)
         ├─ Direct answer (simple questions)
         ├─ → "research" agent (Tavily web search)
         ├─ → "sql" agent (Chinook SQLite database)
         └─ → "general" agent (orchestrator, delegates via task() to specialists)
```

**Supervisor** ([supervisor.py](backend/supervisor.py)): A `create_agent()` with a `route` tool that returns `Command(goto=agent_name)` to jump to specialist subgraph nodes. Uses `init_chat_model("anthropic:claude-sonnet-4-5-20250929")`.

**Agent Registry** ([registry.py](backend/registry.py)): Central `AGENT_REGISTRY` dict. Agents self-register via `register_agent()`. The supervisor and general agent auto-discover all registered agents.

**Deep Agents** ([agents/](backend/agents/)): Each specialist uses `create_deep_agent()` from the `deepagents` library with its own middleware stack. Registration order matters — see [agents/__init__.py](backend/agents/__init__.py), where `build_general_agent()` must be called last (it collects tools from all previously registered agents).

**Package Agents** ([agents/loader.py](backend/agents/loader.py)): Scans `packages/` directory for agent packages. Each package has an `AGENTS.md` (system prompt) and optional `skills/` subdirectories with `SKILL.md` files. Auto-loaded and registered.

### Streaming Pipeline

Backend streams LangGraph output as SSE events through this chain:

1. LangGraph `astream()` produces 3-tuple chunks `(namespace, stream_mode, data)`
2. [stream_handler.py](backend/stream_handler.py) translates these into typed SSE events: `text_delta`, `tool_call_start`, `tool_call_result`, `error`, `done`
3. [api/client.ts](frontend/src/api/client.ts) parses SSE via `fetch()` + `ReadableStream` (not EventSource, to support POST body)
4. [useChat.ts](frontend/src/hooks/useChat.ts) hook consumes events and updates React state

### Database & Persistence

PostgreSQL is the primary database, managed via asyncpg connection pool:

- **Connection Pool** ([backend/db.py](backend/db.py)): Global asyncpg pool with 2-10 connections
- **LangGraph Checkpoints**: Stored in PostgreSQL via `AsyncPostgresSaver`
- **Thread IDs**: 8-char hex strings from `uuid4().hex[:8]`

**Database Schema:**

| Table | Description |
|-------|-------------|
| `users` | User accounts with roles (admin/user) and status (active/disabled) |
| `conversations` | User conversations with thread_id mapping to LangGraph checkpoints |
| `files` | Uploaded file metadata with user/conversation associations |
| `langgraph_checkpoints` | LangGraph state persistence (auto-managed) |

Migrations are in `infra/migrations/` and managed by Alembic.

### Container Pool & Sandbox

Docker-based code execution with pre-warmed containers for fast response (~10-50ms):

- **container_pool.py** ([backend/tools/container_pool.py](backend/tools/container_pool.py)): Manages 5 pre-warmed containers with automatic recycling after 100 uses
- **sandbox.py** ([backend/tools/sandbox.py](backend/tools/sandbox.py)): `execute_python()` and `execute_python_with_file()` tools for code execution
- **file_tools.py** ([backend/tools/file_tools.py](backend/tools/file_tools.py)): `read_uploaded_file()` for parsing PDF/Word/Excel/PPT files

Security: network disabled, all capabilities dropped, no privilege escalation allowed.

Pre-installed packages in sandbox: `python-pptx`, `python-docx`, `openpyxl`, `pandas`, `numpy`, `Pillow`, `matplotlib`, `pypdf`, `pdfplumber`, `reportlab`.

### Skills System

Skills provide domain-specific instructions that can be injected into agent prompts:

- **Registry** ([backend/skills/registry.py](backend/skills/registry.py)): `SKILL_REGISTRY` global dict with `SkillEntry` objects
- **Loader** ([backend/skills/loader.py](backend/skills/loader.py)): Auto-loads from `skills/anthropic/skills/` (git submodule) and `skills/custom/`
- **Format**: Each skill is a directory with `SKILL.md` containing YAML frontmatter (`name`, `description`) + markdown instructions

When a skill is requested via `ChatRequest.skill`, the skill instructions are injected into the user message.

### Authentication & Authorization

JWT-based authentication with HTTP-only cookies:

- **Security** ([backend/auth/security.py](backend/auth/security.py)): bcrypt password hashing, JWT token creation/validation
- **Dependencies** ([backend/auth/dependencies.py](backend/auth/dependencies.py)): `get_current_user()` and `require_admin()` FastAPI dependencies
- **Router** ([backend/auth/router.py](backend/auth/router.py)): Login, logout, and user management endpoints

**User Roles:**
- `admin` — Full access including user management
- `user` — Standard user, can only access own conversations

**Auth Flow:**
1. User submits credentials to `/api/auth/login`
2. Server validates and returns JWT in `access_token` cookie (HTTP-only, 24h expiry)
3. All protected endpoints read cookie via `get_current_user()` dependency
4. Admin endpoints additionally check role via `require_admin()`

### Conversation Management

User-scoped conversations with LangGraph thread mapping:

- **Models** ([backend/conversations/models.py](backend/conversations/models.py)): Pydantic models for API
- **Database** ([backend/conversations/database.py](backend/conversations/database.py)): CRUD operations
- **Router** ([backend/conversations/router.py](backend/conversations/router.py)): REST endpoints

Each conversation links to a LangGraph `thread_id` for message history.

### Frontend

React 19 + Vite 7 + TypeScript with left-sidebar layout:

**Component Tree:**
```
App
├── LoginPage (unauthenticated)
└── MainLayout (authenticated)
    ├── Sidebar
    │   ├── SidebarHeader (new conversation button)
    │   ├── ConversationList (history)
    │   └── Navigation (admin menu, logout)
    └── ChatContainer
        ├── MessageList → MessageBubble → ToolCallCard
        └── InputBar
```

**Key Components:**
- `LoginPage` — Authentication form
- `MainLayout` — Left-sidebar layout with collapsible sidebar
- `Sidebar` — Navigation, conversation list, user menu
- `ConversationList` — Scrollable history with edit/delete
- `UserManagement` — Admin-only user CRUD (Admin/)

The InputBar supports `/command` syntax to route directly to a named agent (bypassing the supervisor).

## Adding a New Agent

1. Create `backend/agents/new_agent.py` — use `create_deep_agent()` + `register_agent()`
2. Import it in `backend/agents/__init__.py` **before** `build_general_agent()`
3. Restart backend — supervisor and general agent auto-discover it

## Adding a Package Agent

1. Create `packages/my-agent/AGENTS.md` (system prompt)
2. Optionally add `packages/my-agent/skills/<skill-name>/SKILL.md`
3. Auto-loaded by the package loader on startup

## API Endpoints

### Authentication

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | - | Login, returns JWT cookie |
| `/api/auth/logout` | POST | - | Clear auth cookie |
| `/api/auth/me` | GET | User | Get current user info |

### User Management (Admin only)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/users` | GET | Admin | List all users |
| `/api/users` | POST | Admin | Create new user |
| `/api/users/{id}` | DELETE | Admin | Delete user |
| `/api/users/{id}/status` | PATCH | Admin | Enable/disable user |

### Conversations

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/conversations` | GET | User | List user's conversations |
| `/api/conversations` | POST | User | Create new conversation |
| `/api/conversations/{id}` | GET | User | Get conversation details |
| `/api/conversations/{id}` | PATCH | User | Update title |
| `/api/conversations/{id}` | DELETE | User | Delete conversation |

### Chat & Threads

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/chat` | POST | User | Send message, returns SSE stream |
| `/api/threads/{id}/history` | GET | User | Get thread message history |
| `/api/agents` | GET | - | List registered agents |

**ChatRequest fields**: `thread_id`, `message`, `agent` (skip supervisor), `skill` (inject skill instructions), `file_ids` (uploaded files)

### Skills

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/skills` | GET | List all skills (name + description) |
| `/api/skills/{name}` | GET | Get skill details with full instructions |

### Files

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/files/upload` | POST | User | Upload file (max 10MB) |
| `/api/files/{id}/download` | GET | User | Download uploaded file |
| `/api/files/{id}/content` | GET | User | Preview text file content |
| `/api/files/{id}/{filename}` | GET | User | Download generated file (from sandbox)

## Key Dependencies

### Backend
- **deepagents** (>=0.2.6) — deep agent framework with middleware
- **langgraph** / **langchain** — agent orchestration and LLM integration
- **asyncpg** — async PostgreSQL driver
- **python-jose** / **bcrypt** — JWT tokens and password hashing
- **alembic** — database migrations
- **tavily-python** — web search API
- **sse-starlette** — server-sent events for FastAPI
- **docker** — container pool for sandboxed code execution
- **pypdf** / **python-docx** / **openpyxl** / **python-pptx** — document parsing

### Infrastructure
- **PostgreSQL 15** — primary database (via docker-compose)
- **Docker** — containerized code execution sandbox

## Project Structure

```
sunnyagent/
├── backend/
│   ├── main.py              # FastAPI application entry
│   ├── db.py                # PostgreSQL connection pool
│   ├── supervisor.py        # LangGraph supervisor router
│   ├── registry.py          # Agent registry
│   ├── stream_handler.py    # LangGraph → SSE translation
│   ├── auth/                # Authentication module
│   │   ├── models.py        # User, Login, etc. Pydantic models
│   │   ├── security.py      # Password hashing, JWT
│   │   ├── dependencies.py  # get_current_user, require_admin
│   │   ├── database.py      # User CRUD operations
│   │   └── router.py        # Auth API endpoints
│   ├── conversations/       # Conversation management
│   │   ├── models.py        # Conversation Pydantic models
│   │   ├── database.py      # Conversation CRUD
│   │   └── router.py        # Conversation API endpoints
│   ├── agents/              # Deep agents
│   │   ├── research.py      # Web research agent
│   │   ├── sql.py           # SQL database agent
│   │   ├── general.py       # General orchestrator
│   │   └── loader.py        # Package agent loader
│   ├── tools/               # Agent tools
│   │   ├── container_pool.py # Docker container pool
│   │   ├── sandbox.py       # Code execution
│   │   └── file_tools.py    # File parsing
│   └── skills/              # Skill system
│       ├── registry.py      # Skill registry
│       └── loader.py        # Skill loader
├── frontend/src/
│   ├── api/                 # API clients
│   │   ├── client.ts        # SSE chat client
│   │   ├── auth.ts          # Auth API
│   │   ├── conversations.ts # Conversations API
│   │   └── users.ts         # User management API
│   ├── hooks/               # React hooks
│   │   ├── useChat.ts       # Chat state management
│   │   ├── useAuth.ts       # Auth context
│   │   └── useConversations.ts
│   └── components/
│       ├── Auth/            # Login page
│       ├── Layout/          # MainLayout, Sidebar
│       ├── Conversations/   # Conversation list/item
│       ├── Admin/           # User management (admin)
│       ├── ChatContainer.tsx
│       ├── MessageList.tsx
│       ├── InputBar.tsx
│       └── ToolCallCard.tsx
├── infra/
│   ├── alembic.ini          # Alembic config
│   └── migrations/          # Database migrations
│       └── versions/
│           ├── 001_create_users_table.py
│           └── 002_create_conversations_table.py
├── docker-compose.yml       # PostgreSQL service
├── packages/                # Package agents (AGENTS.md)
└── skills/                  # Global skills (SKILL.md)
```
