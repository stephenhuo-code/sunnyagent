# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Research Chat — a full-stack web app (FastAPI + React) with a LangGraph supervisor that routes user messages to specialized deep agents for web research, SQL database queries, and multi-step orchestration.

## Development Commands

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

### Type Checking
```bash
uv run pyright              # Python type checking (pyrightconfig.json)
cd frontend && npx tsc      # TypeScript checking
```

### Required Environment Variables (.env in project root)
- `ANTHROPIC_API_KEY` — required
- `TAVILY_API_KEY` — required for web research
- `OPENAI_API_KEY` — optional

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

### Conversation Persistence

Threads are persisted in `threads.db` (SQLite) via LangGraph's `AsyncSqliteSaver`. Thread IDs are 8-char hex strings from `uuid4`.

### Frontend

React 19 + Vite 7 + TypeScript. Component tree: `App → ChatContainer → {MessageList (→ MessageBubble → ToolCallCard), InputBar}`. The InputBar supports `/command` syntax to route directly to a named agent (bypassing the supervisor).

## Adding a New Agent

1. Create `backend/agents/new_agent.py` — use `create_deep_agent()` + `register_agent()`
2. Import it in `backend/agents/__init__.py` **before** `build_general_agent()`
3. Restart backend — supervisor and general agent auto-discover it

## Adding a Package Agent

1. Create `packages/my-agent/AGENTS.md` (system prompt)
2. Optionally add `packages/my-agent/skills/<skill-name>/SKILL.md`
3. Auto-loaded by the package loader on startup

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message, returns SSE stream |
| `/api/threads` | POST | Create new thread (returns `thread_id`) |
| `/api/threads/{id}/history` | GET | Get thread message history |
| `/api/agents` | GET | List registered agents |

## Key Dependencies

- **deepagents** (>=0.2.6) — deep agent framework with middleware
- **langgraph** / **langchain** — agent orchestration and LLM integration
- **tavily-python** — web search API
- **sse-starlette** — server-sent events for FastAPI
