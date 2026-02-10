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

> **完整系统架构见 `docs/architecture.md`**，包含：
> - Supervisor + Deep Agents 模式
> - Streaming Pipeline
> - 数据库设计
> - 认证授权
> - 前端架构
> - API 端点
> - 禁止模式和命名规范

### 快速概览

```
User → Supervisor (LLM router)
         ├─ Direct answer
         ├─ → "research" agent (Tavily)
         ├─ → "sql" agent (SQL queries)
         └─ → "general" agent (orchestrator)
```

**核心组件：**
- `backend/supervisor.py` — 路由到专业 Agent
- `backend/registry.py` — Agent 自注册中心
- `backend/stream_handler.py` — LangGraph → SSE 转换
- `backend/db.py` — PostgreSQL 连接池

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

## Architecture Constraints (MUST FOLLOW)

> **完整架构规范见 `docs/architecture.md`**，以下为关键约束摘要。
>
> 其他 AI 工具用户请参考：
> - Cursor: `.cursorrules`
> - GitHub Copilot: `.github/copilot-instructions.md`

### Dependency Rules

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (main.py)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Layer (agents/)                    │
│   supervisor.py → [research, analysis, quality, general]    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer (services/)                 │
│   knowledge_service, datasource_service, file_service       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Repository Layer (repositories/)            │
│   file_repository, document_repository                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database (db.py)                         │
└─────────────────────────────────────────────────────────────┘
```

### Prohibited Patterns

| Pattern | Reason | Correct Approach |
|---------|--------|------------------|
| Agent 直接导入 `asyncpg` 或 `db.py` | 绕过 Service 层 | Agent → Service → Repository → db |
| 在 Agent 中硬编码 SQL | 违反关注点分离 | 使用 Repository 或 Service 方法 |
| 跳过 `registry.py` 注册 Agent | 无法被 Supervisor 发现 | 使用 `register_agent()` |
| 在多处重复定义相同工具函数 | 代码重复 | 放入 `shared/utils.py` |
| 直接在 Agent 中操作文件系统 | 安全风险 | 使用 `file_service` |

### Naming Conventions

| 类型 | 规范 | 示例 |
|------|------|------|
| Agent 文件 | `<name>_agent.py` | `knowledge_agent.py` |
| Service 类 | `<Name>Service` | `KnowledgeService` |
| Repository 类 | `<Name>Repository` | `FileRepository` |
| API Router | `<name>_router.py` | `files_router.py` |
| Pydantic Model | `<Name>Request/Response` | `SearchRequest` |

### Shared Resources (Modify with Caution)

| File | Owner | Modification Rule |
|------|-------|-------------------|
| `db.py` | Infra Lead | Requires team review |
| `registry.py` | Arch Lead | Requires team review |
| `shared/` | Team | Requires 2 approvals |
| `contracts/` | Arch Lead | Requires arch review |

## Team Collaboration

See `docs/ai-dev-best-practices.md` for full AI-assisted development guidelines.

### Quick Rules

1. **Before coding**: Read CLAUDE.md + relevant contracts
2. **AI prompts**: Always provide architecture context
3. **Generate code**: Step by step, review each step
4. **Before PR**: Run `uv run pyright` and `uv run pytest`
5. **Code review**: Check dependency direction and interface compliance
