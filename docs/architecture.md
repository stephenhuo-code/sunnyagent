# 系统架构

> 本文档定义项目的架构规范和系统设计，**所有开发者必读**，无论使用何种 AI 工具。

## 项目概述

SunnyAgent — 一个全栈 Web 应用（FastAPI + React），使用 LangGraph Supervisor 将用户消息路由到专业 Agent，支持网络研究、SQL 查询、多步骤编排、文件处理和沙箱代码执行。包含用户认证、对话管理和管理员用户管理功能。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+, FastAPI, LangGraph, asyncpg |
| 前端 | React 19, TypeScript 5.7, Vite 7 |
| 数据库 | PostgreSQL 15 |
| 容器 | Docker (沙箱执行) |
| 认证 | JWT + HTTP-only Cookies |

---

## 核心架构模式

### Supervisor + Deep Agents 模式

核心模式是一个 **LangGraph StateGraph**，Supervisor 节点路由到专业子图节点：

```
User → Supervisor (LLM router with route() tool)
         ├─ Direct answer (简单问题直接回答)
         ├─ → "research" agent (Tavily 网络搜索)
         ├─ → "sql" agent (SQL 数据库查询)
         └─ → "general" agent (编排器，通过 task() 委托给专家)
```

**关键组件：**

| 组件 | 文件 | 说明 |
|------|------|------|
| Supervisor | `backend/supervisor.py` | 使用 `route` 工具返回 `Command(goto=agent_name)` 跳转到专业子图 |
| Agent Registry | `backend/registry.py` | 中央 `AGENT_REGISTRY` 字典，Agent 通过 `register_agent()` 自注册 |
| Deep Agents | `backend/agents/` | 每个专家使用 `create_deep_agent()` 创建，有独立的中间件栈 |
| Package Agents | `backend/agents/loader.py` | 扫描 `packages/` 目录加载 Agent 包 |

### Streaming Pipeline

后端通过 SSE 事件流式输出 LangGraph 结果：

```
LangGraph astream()          → 产生 3 元组 (namespace, stream_mode, data)
       ↓
stream_handler.py            → 转换为 SSE 事件: text_delta, tool_call_start,
                               tool_call_result, error, done
       ↓
frontend/api/client.ts       → 通过 fetch() + ReadableStream 解析 SSE
       ↓
frontend/hooks/useChat.ts    → 消费事件并更新 React 状态
```

### 数据库与持久化

PostgreSQL 作为主数据库，通过 asyncpg 连接池管理：

| 表 | 说明 |
|----|------|
| `users` | 用户账户（角色：admin/user，状态：active/disabled） |
| `conversations` | 用户对话，thread_id 映射到 LangGraph checkpoints |
| `files` | 上传文件元数据，关联用户和对话 |
| `langgraph_checkpoints` | LangGraph 状态持久化（自动管理） |

- **连接池**: `backend/db.py` - 全局 asyncpg 池，2-10 连接
- **Thread ID**: 8 字符十六进制字符串（`uuid4().hex[:8]`）
- **迁移**: `infra/migrations/` 由 Alembic 管理

### 容器池与沙箱

Docker 容器执行代码，预热容器实现快速响应（~10-50ms）：

| 组件 | 文件 | 说明 |
|------|------|------|
| Container Pool | `backend/tools/container_pool.py` | 管理 5 个预热容器，100 次使用后自动回收 |
| Sandbox | `backend/tools/sandbox.py` | `execute_python()` 和 `execute_python_with_file()` |
| File Tools | `backend/tools/file_tools.py` | `read_uploaded_file()` 解析 PDF/Word/Excel/PPT |

**安全措施**: 禁用网络、移除所有 capabilities、禁止权限提升。

**预装包**: `python-pptx`, `python-docx`, `openpyxl`, `pandas`, `numpy`, `Pillow`, `matplotlib`, `pypdf`, `pdfplumber`, `reportlab`

### Skills 系统

Skills 提供可注入 Agent Prompt 的领域特定指令：

| 组件 | 文件 | 说明 |
|------|------|------|
| Registry | `backend/skills/registry.py` | `SKILL_REGISTRY` 全局字典 |
| Loader | `backend/skills/loader.py` | 从 `skills/anthropic/skills/` 和 `skills/custom/` 自动加载 |

**格式**: 每个 Skill 是一个目录，包含 `SKILL.md`（YAML frontmatter + markdown 指令）

### 认证与授权

基于 JWT 的认证，使用 HTTP-only Cookies：

| 组件 | 文件 | 说明 |
|------|------|------|
| Security | `backend/auth/security.py` | bcrypt 密码哈希，JWT 创建/验证 |
| Dependencies | `backend/auth/dependencies.py` | `get_current_user()` 和 `require_admin()` |
| Router | `backend/auth/router.py` | 登录、登出、用户管理端点 |

**用户角色**:
- `admin` — 完全访问权限，包括用户管理
- `user` — 标准用户，只能访问自己的对话

**认证流程**:
1. 用户提交凭据到 `/api/auth/login`
2. 服务器验证并返回 JWT（HTTP-only cookie，24h 过期）
3. 受保护端点通过 `get_current_user()` 读取 cookie
4. 管理端点额外通过 `require_admin()` 检查角色

### 对话管理

用户范围的对话与 LangGraph thread 映射：

| 组件 | 文件 | 说明 |
|------|------|------|
| Models | `backend/conversations/models.py` | API 用 Pydantic 模型 |
| Database | `backend/conversations/database.py` | CRUD 操作 |
| Router | `backend/conversations/router.py` | REST 端点 |

每个对话链接到一个 LangGraph `thread_id` 用于消息历史。

### 前端架构

React 19 + Vite 7 + TypeScript，左侧边栏布局：

```
App
├── LoginPage (未认证)
└── MainLayout (已认证)
    ├── Sidebar
    │   ├── SidebarHeader (新建对话按钮)
    │   ├── ConversationList (历史记录)
    │   └── Navigation (管理菜单, 登出)
    └── ChatContainer
        ├── MessageList → MessageBubble → ToolCallCard
        └── InputBar
```

InputBar 支持 `/command` 语法直接路由到指定 Agent（绕过 Supervisor）。

---

## 分层架构

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

### 依赖规则

**只允许向下依赖，禁止反向依赖：**

```
API → Agent → Service → Repository → Database
```

---

## API 端点概览

### 认证

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/auth/login` | POST | - | 登录，返回 JWT cookie |
| `/api/auth/logout` | POST | - | 清除认证 cookie |
| `/api/auth/me` | GET | User | 获取当前用户信息 |

### 用户管理（仅管理员）

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/users` | GET | Admin | 列出所有用户 |
| `/api/users` | POST | Admin | 创建新用户 |
| `/api/users/{id}` | DELETE | Admin | 删除用户 |
| `/api/users/{id}/status` | PATCH | Admin | 启用/禁用用户 |

### 对话

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/conversations` | GET | User | 列出用户对话 |
| `/api/conversations` | POST | User | 创建新对话 |
| `/api/conversations/{id}` | GET | User | 获取对话详情 |
| `/api/conversations/{id}` | PATCH | User | 更新标题 |
| `/api/conversations/{id}` | DELETE | User | 删除对话 |

### 聊天

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/chat` | POST | User | 发送消息，返回 SSE 流 |
| `/api/threads/{id}/history` | GET | User | 获取线程消息历史 |
| `/api/agents` | GET | - | 列出已注册 Agent |

**ChatRequest 字段**: `thread_id`, `message`, `agent`（跳过 supervisor）, `skill`（注入技能指令）, `file_ids`（上传文件）

### 文件

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/files/upload` | POST | User | 上传文件（最大 10MB） |
| `/api/files/{id}/download` | GET | User | 下载上传的文件 |
| `/api/files/{id}/content` | GET | User | 预览文本文件内容 |

---

## 添加新 Agent

1. 创建 `backend/agents/new_agent.py` — 使用 `create_deep_agent()` + `register_agent()`
2. 在 `backend/agents/__init__.py` 中导入，**必须在 `build_general_agent()` 之前**
3. 重启后端 — Supervisor 和 general agent 自动发现

## 添加 Package Agent

1. 创建 `packages/my-agent/AGENTS.md`（系统提示）
2. 可选添加 `packages/my-agent/skills/<skill-name>/SKILL.md`
3. 启动时由 package loader 自动加载

---

## 禁止模式

| 模式 | 原因 | 正确做法 |
|------|------|----------|
| Agent 直接导入 `asyncpg` 或 `db.py` | 绕过 Service 层 | Agent → Service → Repository → db |
| 在 Agent 中硬编码 SQL | 违反关注点分离 | 使用 Repository 或 Service 方法 |
| 跳过 `registry.py` 注册 Agent | 无法被 Supervisor 发现 | 使用 `register_agent()` |
| 在多处重复定义相同工具函数 | 代码重复 | 放入 `shared/utils.py` |
| 直接在 Agent 中操作文件系统 | 安全风险 | 使用 `file_service` |

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Agent 文件 | `<name>_agent.py` | `knowledge_agent.py` |
| Service 类 | `<Name>Service` | `KnowledgeService` |
| Repository 类 | `<Name>Repository` | `FileRepository` |
| API Router | `<name>_router.py` | `files_router.py` |
| Pydantic Model | `<Name>Request/Response` | `SearchRequest` |

## 共享资源

| 文件/目录 | 维护者 | 修改规则 |
|-----------|--------|----------|
| `db.py` | 基础设施负责人 | 需团队评审 |
| `registry.py` | 架构负责人 | 需团队评审 |
| `shared/` | 团队 | 需 2 人审批 |
| `contracts/` | 架构负责人 | 需架构评审 |

## 接口定义

所有跨模块的共享接口必须定义在 `contracts/` 目录：

```
contracts/
├── knowledge.py      # 知识库相关接口
├── datasource.py     # 数据源相关接口
└── file.py           # 文件管理相关接口
```

新增接口需经架构师审批后方可使用。

---

## 目录结构

```
sunnyagent/
├── backend/
│   ├── main.py              # FastAPI 应用入口
│   ├── db.py                # PostgreSQL 连接池
│   ├── supervisor.py        # LangGraph supervisor 路由
│   ├── registry.py          # Agent 注册表
│   ├── stream_handler.py    # LangGraph → SSE 转换
│   ├── auth/                # 认证模块
│   │   ├── models.py        # User, Login 等 Pydantic 模型
│   │   ├── security.py      # 密码哈希, JWT
│   │   ├── dependencies.py  # get_current_user, require_admin
│   │   ├── database.py      # User CRUD 操作
│   │   └── router.py        # Auth API 端点
│   ├── conversations/       # 对话管理
│   │   ├── models.py        # Conversation Pydantic 模型
│   │   ├── database.py      # Conversation CRUD
│   │   └── router.py        # Conversation API 端点
│   ├── agents/              # Deep agents
│   │   ├── research.py      # 网络研究 agent
│   │   ├── sql.py           # SQL 数据库 agent
│   │   ├── general.py       # 通用编排器
│   │   └── loader.py        # Package agent 加载器
│   ├── services/            # 业务逻辑层
│   ├── repositories/        # 数据访问层
│   ├── contracts/           # 接口定义
│   ├── shared/              # 共享工具
│   ├── tools/               # Agent 工具
│   │   ├── container_pool.py # Docker 容器池
│   │   ├── sandbox.py       # 代码执行
│   │   └── file_tools.py    # 文件解析
│   └── skills/              # 技能系统
│       ├── registry.py      # 技能注册表
│       └── loader.py        # 技能加载器
├── frontend/src/
│   ├── api/                 # API 客户端
│   │   ├── client.ts        # SSE 聊天客户端
│   │   ├── auth.ts          # Auth API
│   │   ├── conversations.ts # Conversations API
│   │   └── users.ts         # 用户管理 API
│   ├── hooks/               # React hooks
│   │   ├── useChat.ts       # 聊天状态管理
│   │   ├── useAuth.ts       # Auth context
│   │   └── useConversations.ts
│   └── components/
│       ├── Auth/            # 登录页面
│       ├── Layout/          # MainLayout, Sidebar
│       ├── Conversations/   # 对话列表/项
│       ├── Admin/           # 用户管理 (admin)
│       ├── ChatContainer.tsx
│       ├── MessageList.tsx
│       ├── InputBar.tsx
│       └── ToolCallCard.tsx
├── infra/
│   ├── alembic.ini          # Alembic 配置
│   └── migrations/          # 数据库迁移
├── docker-compose.yml       # PostgreSQL 服务
├── packages/                # Package agents (AGENTS.md)
└── skills/                  # 全局 skills (SKILL.md)
```

---

## 开发检查清单

### 开始编码前

- [ ] 阅读本文档了解架构约束
- [ ] 阅读相关的 `contracts/` 接口定义
- [ ] 确认新代码属于哪一层

### 编码时

- [ ] 遵循分层架构，只向下依赖
- [ ] 使用正确的命名规范
- [ ] 新接口提交到 `contracts/`

### 提交前

- [ ] 运行 `uv run pyright` 类型检查
- [ ] 运行 `uv run pytest` 测试
- [ ] 检查依赖方向是否正确

---

## 相关文档

- `CLAUDE.md` — Claude Code 用户指南（包含开发命令）
- `docs/ai-dev-best-practices.md` — AI 协作开发最佳实践
