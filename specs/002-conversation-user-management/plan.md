# Implementation Plan: 对话历史与用户管理

**Branch**: `002-conversation-user-management` | **Date**: 2026-02-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-conversation-user-management/spec.md`

## Summary

为 Sunny Agent 添加完整的用户认证系统和对话历史管理功能。采用左树右表布局重构主界面，左侧包含可收缩导航栏（新建对话、对话文件夹、系统管理、登录管理），右侧保持现有对话界面。引入用户角色系统（管理员/普通用户），使用 SQLite 统一存储用户、会话和对话数据。

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.7
**Primary Dependencies**: FastAPI, React 19, Vite 7, LangGraph, asyncpg, Alembic
**Storage**: PostgreSQL（替代 threads.db；chinook.db 保留为 SQLite 示例数据）
**Schema Management**: Alembic（管理 users、conversations 表的版本化迁移）
**Testing**: pytest (backend), 手动测试 (frontend)
**Target Platform**: Web (现代浏览器)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: 登录 < 2秒, 对话列表加载 < 1秒, 支持 10 并发用户
**Constraints**: 会话有效期 24 小时，对话标题最长 50 字符
**Scale/Scope**: 1000+ 对话记录，50+ 用户
**Migration**: threads.db → PostgreSQL（chinook.db 保留）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | 用户管理是独立模块，不影响现有 Agent 架构 |
| II. 注册驱动发现 | ✅ PASS | 不涉及 Agent 注册，保持现有机制 |
| III. 流式优先 | ✅ PASS | 对话功能继续使用 SSE 流式传输 |
| IV. 包扩展性 | ✅ PASS | 不影响包 Agent 加载机制 |
| V. 简洁性 | ⚠️ JUSTIFIED | 引入 PostgreSQL 替代 SQLite，增加部署复杂度，但提供生产级可靠性和统一存储 |

**Gate Result**: PASS - 可继续进入 Phase 0（简洁性违规已记录并合理化）

## Project Structure

### Documentation (this feature)

```text
specs/002-conversation-user-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml         # OpenAPI specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── auth/                # 新增：认证模块
│   ├── __init__.py
│   ├── models.py        # User, Session Pydantic models
│   ├── database.py      # PostgreSQL 操作
│   ├── security.py      # 密码哈希、JWT 生成/验证
│   └── router.py        # 认证相关 API 路由
├── conversations/       # 新增：对话管理模块
│   ├── __init__.py
│   ├── models.py        # Conversation Pydantic models
│   ├── database.py      # 对话 CRUD 操作
│   └── router.py        # 对话管理 API 路由
├── migrations/          # 新增：Alembic 迁移
│   ├── versions/
│   │   └── 001_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── db.py                # 新增：PostgreSQL 连接池管理
├── main.py              # 修改：添加路由、认证中间件、PG连接
├── alembic.ini          # 新增：Alembic 配置
└── ...existing files

scripts/
└── migrate_sqlite_to_pg.py  # 新增：数据迁移脚本

frontend/
├── src/
│   ├── components/
│   │   ├── Layout/      # 新增：主布局组件
│   │   │   ├── Sidebar.tsx
│   │   │   ├── SidebarHeader.tsx
│   │   │   └── MainLayout.tsx
│   │   ├── Auth/        # 新增：认证组件
│   │   │   └── LoginPage.tsx
│   │   ├── Conversations/  # 新增：对话管理组件
│   │   │   ├── ConversationList.tsx
│   │   │   └── ConversationItem.tsx
│   │   └── Admin/       # 新增：管理员组件
│   │       ├── UserManagement.tsx
│   │       └── UserForm.tsx
│   ├── hooks/
│   │   ├── useAuth.ts   # 新增：认证状态管理
│   │   └── useConversations.ts  # 新增：对话列表管理
│   ├── api/
│   │   ├── auth.ts      # 新增：认证 API 调用
│   │   └── conversations.ts  # 新增：对话 API 调用
│   └── App.tsx          # 修改：添加路由和布局
└── ...existing files
```

**Structure Decision**: Web application 结构，后端新增 `auth/` 和 `conversations/` 模块，前端新增对应的组件和 hooks。保持现有文件结构，通过新增模块实现功能。

## Constitution Check (Post-Phase 1)

*Re-evaluation after design phase completion.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | auth/ 和 conversations/ 模块独立，不影响 agents/ |
| II. 注册驱动发现 | ✅ PASS | 设计未触及 Agent 注册机制 |
| III. 流式优先 | ✅ PASS | /api/chat 继续使用 SSE，新增 API 使用标准 REST |
| IV. 包扩展性 | ✅ PASS | 设计未影响 packages/ 加载机制 |
| V. 简洁性 | ⚠️ JUSTIFIED | 引入 PostgreSQL + asyncpg + langgraph-checkpoint-postgres，增加依赖但提供生产级能力 |

**Gate Result**: PASS - 设计符合宪法原则（简洁性违规已记录并合理化）

## Complexity Tracking

> 记录偏离简洁性原则的设计决策及其合理性。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| PostgreSQL 替代 SQLite | 生产级可靠性、高并发支持、统一存储所有数据 | SQLite 不适合生产环境，并发受限，LangGraph checkpoints 与业务数据分离增加复杂度 |

## Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| research.md | [research.md](./research.md) | 技术决策研究 |
| data-model.md | [data-model.md](./data-model.md) | 数据模型定义 |
| api.yaml | [contracts/api.yaml](./contracts/api.yaml) | OpenAPI 规范 |
| quickstart.md | [quickstart.md](./quickstart.md) | 快速开始指南 |

## Next Steps

运行 `/speckit.tasks` 生成实施任务列表。
