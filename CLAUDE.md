# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SunnyAgent — a full-stack web app (FastAPI + React) with an AIME (Autonomous Intent-driven Multi-agent Executor) architecture that routes user messages to specialized deep agents for web research, SQL database queries, multi-step orchestration, file processing, and sandboxed code execution. Includes user authentication, conversation management, and admin user management.

## Meta-Agent 优化系统
- 当被要求执行 Skill 优化、自动迭代、或 Meta-Agent 相关任务时，先读取 `specs/META_AGENT_SPEC.md`

## Development Commands



### Quick Start (Recommended)
```bash
./scripts/start.sh infra      # Start PostgreSQL + Langfuse
./scripts/start.sh backend    # Start backend (in new terminal)
./scripts/start.sh frontend   # Start frontend (in new terminal)
```

### Prerequisites
```bash
docker compose up -d          # Start PostgreSQL + Langfuse
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

**LLM Provider Configuration:**
- `LLM_PROVIDER` — Select LLM provider: `anthropic` (default), `openai`, `deepseek`, or `deepseek_gateway`
- `ANTHROPIC_API_KEY` — Required if `LLM_PROVIDER=anthropic`
- `OPENAI_API_KEY` — Required if `LLM_PROVIDER=openai`
- `DEEPSEEK_API_KEY` — Required if `LLM_PROVIDER=deepseek` (Native, api.deepseek.com)
- `DEEPSEEK_GATEWAY_API_KEY` — Required if `LLM_PROVIDER=deepseek_gateway` (Gateway, volceapi.com)

**Other Required:**
- `TAVILY_API_KEY` — for web research
- `DATABASE_URL` — PostgreSQL connection string (e.g., `postgresql://sunnyagent:sunnyagent123@localhost:5432/sunnyagent`)

**Optional:**
- `JWT_SECRET_KEY` — for JWT signing (auto-generated if not set)
- `JWT_EXPIRATION` — token expiration in seconds (default: 86400 = 24h)
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — default admin credentials on first startup

**Langfuse Observability (Optional):**
- `LANGFUSE_TRACING_ENABLED` — Enable/disable tracing (default: `true`, set to `false` to completely disable)
- `LANGFUSE_BASE_URL` — Langfuse server URL (default: `http://localhost:3001`)
- `LANGFUSE_PUBLIC_KEY` — Langfuse public key for tracing
- `LANGFUSE_SECRET_KEY` — Langfuse secret key for tracing
- `LANGFUSE_ORG_PUBLIC_KEY` — Langfuse organization public key for user sync
- `LANGFUSE_ORG_SECRET_KEY` — Langfuse organization secret key for user sync
- `LANGFUSE_SAMPLE_RATE` — Trace sampling rate 0.0-1.0 (default: 1.0)

## Architecture

> **完整系统架构见 `docs/architecture.md`**，包含：
> - AIME + Deep Agents 模式
> - Streaming Pipeline
> - 数据库设计
> - 认证授权
> - 前端架构
> - API 端点
> - 禁止模式和命名规范

### AIME 架构

系统使用 AIME (Autonomous Intent-driven Multi-agent Executor) 架构：

```
User → IntentAnalyzer → AIMEPlanner
                            ├─ direct_reply (简单问题)
                            ├─ delegate → ActorFactory → Agent
                            ├─ plan → 任务分解 → 并行执行
                            └─ clarify (需要澄清)
```

**核心组件：**
- `backend/aime/__init__.py` — AIME 入口 (`stream_aime_response()`, `get_aime_planner()`)
- `backend/aime/intent/` — 意图分析 (Rule → Keyword → LLM 分类器链)
- `backend/aime/planner.py` — 任务规划与执行
- `backend/aime/actor_factory.py` — 动态 Agent 选择
- `backend/aime/progress_manager.py` — 进度追踪与 SSE 事件
- `backend/checkpointer_store.py` — 共享 checkpointer + history_graph
- `backend/registry.py` — Agent 自注册中心
- `backend/stream_handler.py` — LangGraph → SSE 转换
- `backend/db.py` — PostgreSQL 连接池
- `backend/llm/` — LLM 提供商配置和工厂函数

## Adding a New Agent

1. Create `backend/agents/new_agent.py` — use `create_deep_agent()` + `register_agent()`
2. Import it in `backend/agents/__init__.py`
3. Restart backend — AIME planner auto-discovers it via registry

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

**ChatRequest fields**: `thread_id`, `message`, `agent` (direct route to agent), `skill` (inject skill instructions), `file_ids` (uploaded files)

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
- **langfuse** (>=3.0.0) — observability platform for LLM tracing and monitoring

### Infrastructure
- **PostgreSQL 15** — primary database (via docker-compose)
- **Docker** — containerized code execution sandbox
- **Langfuse** (optional) — LLM observability platform for tracing Agent execution

## Project Structure

```
sunnyagent/
├── backend/
│   ├── main.py              # FastAPI application entry
│   ├── db.py                # PostgreSQL connection pool
│   ├── checkpointer_store.py # Shared checkpointer + history_graph
│   ├── registry.py          # Agent registry
│   ├── stream_handler.py    # LangGraph → SSE translation
│   ├── aime/                # AIME core module
│   │   ├── __init__.py      # Public API: stream_aime_response(), get_aime_planner()
│   │   ├── planner.py       # Task planning and execution
│   │   └── ...              # Intent analysis, actor factory, etc.
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
│   AIME Planner → [research, sql] + generic actor            │
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
| 跳过 `registry.py` 注册 Agent | 无法被 AIME 发现 | 使用 `register_agent()` |
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

## Active Technologies
- Python 3.11+ + litellm, langchain, pyyaml, python-dotenv (004-unified-llm-provider)
- config/llm.yaml (YAML 配置文件) (004-unified-llm-provider)
- Python 3.11+ + litellm, langchain-litellm, FastAPI, LangGraph, deepagents (004-unified-llm-provider)
- N/A（配置通过环境变量） (004-unified-llm-provider)
- Python 3.11+ (backend), TypeScript 5.x (frontend) + FastAPI, React 19, LangGraph, asyncpg (006-project-management)
- PostgreSQL (projects, project_files 表), 文件系统 (项目文件永久存储) (006-project-management)
- PostgreSQL (复用 SunnyAgent 现有数据库，Langfuse 独立 schema) (007-langfuse-integration)
- Python 3.11+ (Backend), TypeScript 5.x (Frontend) + FastAPI, React 19, LangGraph, deepagents, asyncpg (012-plugin-management)
- PostgreSQL (插件状态、评分)，文件系统 (上传的插件包) (012-plugin-management)

## Recent Changes
- 004-unified-llm-provider: Added Python 3.11+ + litellm, langchain, pyyaml, python-dotenv
