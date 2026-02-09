# SunnyAgent 功能规范

> 一个基于 LangGraph 的多 Agent 对话系统，通过 Supervisor 路由将用户请求分发到专业 Deep Agent 处理。支持用户认证、对话历史管理和管理员用户管理。

---

## 1. 产品概述

SunnyAgent 是一个全栈 Web 应用（FastAPI + React），核心是一个 LangGraph Supervisor，能将用户消息智能路由到多个专业 Deep Agent，支持网页研究、SQL 数据库查询、文件处理和沙箱代码执行。系统包含完整的用户认证、对话历史管理和管理员功能。

**技术栈**：
- 后端：FastAPI, LangGraph, LangChain, deepagents
- 前端：React 19, Vite 7, TypeScript
- LLM：Claude claude-sonnet-4-5-20250929（通过 Anthropic API）
- 数据库：PostgreSQL（用户、对话、LangGraph checkpoints）+ Chinook SQLite（示例数据）
- 认证：JWT（HTTP-only Cookie）+ bcrypt 密码哈希
- 容器化：Docker（PostgreSQL 服务 + 代码沙箱容器池）

---

## 2. 核心能力

### 2.1 对话管理系统

**位置**: `backend/conversations/`

#### 对话模型

```python
class Conversation:
    id: UUID                  # 对话唯一标识
    thread_id: str            # LangGraph 线程 ID（8字符）
    user_id: UUID             # 所属用户
    title: str                # 对话标题（最长50字符）
    created_at: datetime
    updated_at: datetime
    is_deleted: bool          # 软删除标记
```

#### 用户隔离

- 每个用户只能访问自己的对话
- 所有 CRUD 操作自动过滤 `user_id`
- 对话列表按 `updated_at` 降序排列

#### 与 LangGraph 集成

```
Conversation.thread_id ←→ LangGraph Checkpointer
                              ↓
                        消息历史存储在
                        langgraph_checkpoints 表
```

### 2.2 Agent系统

### 2.2.1 Supervisor 路由系统
**位置**: `backend/supervisor.py`

Supervisor 是顶层路由节点，接收用户消息后决定：
1. **直接回答** — 简单问候、常识问题、数学计算
2. **路由到专业 Agent** — 调用 `route()` 工具跳转到对应子图

**路由规则**（按优先级）：
| 优先级 | 条件 | 动作 |
|--------|------|------|
| 1 | 消息包含 `[ROUTE_TO: agent_name]` | 立即路由到指定 Agent |
| 2 | 消息包含 `[用户上传了以下文件]` | 路由到 "general" |
| 3 | 消息以 `[SKILL:]` 开头 | 路由到 "general" |
| 4 | 简单问题 | Supervisor 直接回答 |
| 5 | 任务明确匹配某个专业 Agent | 路由到该 Agent |
| 6 | 复杂/跨域任务 | 路由到 "general"（编排器）|
| 7 | 模糊请求 | 向用户澄清 |

**实现机制**：
```python
@tool
def route(agent_name: str, task_description: str) -> Command:
    return Command(goto=agent_name, graph=Command.PARENT)
```

### 2.2.2 Agent 注册中心

**位置**: `backend/registry.py`

中央注册表管理所有可用 Agent：

```python
@dataclass
class AgentEntry:
    name: str              # Agent 标识符
    description: str       # 能力描述（用于路由决策）
    graph: CompiledStateGraph  # LangGraph 编译图
    tools: list            # Agent 可用工具列表
    icon: str              # 前端图标
    show_in_selector: bool # 是否在 UI 选择器中显示
```

**注册流程**：
1. 各 Agent 模块导入时调用 `register_agent()`
2. `backend/agents/__init__.py` 控制加载顺序
3. `general` Agent 必须最后构建（收集所有其他 Agent 的工具）

### 2.2.3 General Agent（通用编排 Agent）

**位置**: `backend/agents/general.py`

**能力**：
- 复杂多步骤任务编排
- 可调用所有其他 Agent 的工具
- 可委托子任务给专业 Agent
- 文件读取和处理
- 沙箱代码执行

**工具**：
| 工具 | 功能 |
|------|------|
| `activate_skill` | 激活技能获取详细指令 |
| `execute_python` | 沙箱中执行 Python 代码 |
| `execute_python_with_file` | 执行代码并生成可下载文件 |
| `read_uploaded_file` | 读取用户上传的文件 |
| 所有其他 Agent 的工具 | 通过 `get_all_tools()` 收集 |

**策略**：
1. **直接执行** — 使用工具处理简单子任务
2. **委托执行** — 使用 `task()` 工具委托给专业子 Agent

### 2.2.4 Package Agent（包 Agent）

**位置**: `backend/agents/loader.py`

**能力**：
- 从 `packages/` 目录自动加载 Agent 包
- 每个包包含 `AGENTS.md`（系统提示）和可选的 `skills/` 目录

**包结构**：
```
packages/
  content-writer/
    AGENTS.md          # Agent 记忆/系统提示
    skills/
      blog-post/
        SKILL.md
      social-media/
        SKILL.md
```

#### 2.2.5 专业Agent

##### 2.2.5.1 Research Agent（研究 Agent）

**位置**: `backend/agents/research.py`

**能力**：
- 网页搜索与内容抓取
- 当前事件和主题比较
- 生成带引用的研究报告

**工具**：
| 工具 | 功能 |
|------|------|
| `tavily_search` | Tavily API 搜索 + 网页内容抓取转 Markdown |
| `think_tool` | 研究过程反思工具，用于规划下一步 |

**搜索限制**：
- 简单查询：最多 2-3 次搜索
- 复杂查询：最多 5 次搜索
- 找到 3+ 相关来源后停止

**绑定 Skills**：`pdf`, `web-scraping`

#### 2.2.5.2 SQL Agent（数据库 Agent）

**位置**: `backend/agents/sql.py`

**能力**：
- 查询 Chinook 音乐商店数据库
- 支持表：artists, albums, tracks, customers, invoices, employees

**工具**：SQLDatabaseToolkit 提供的标准 SQL 工具集



### 2.3 技能系统

**位置**: `backend/skills/`

#### 技能注册表

```python
@dataclass
class SkillEntry:
    name: str           # 唯一标识符（小写-连字符）
    description: str    # 触发条件描述
    path: Path          # SKILL.md 所在目录
```

#### 技能加载

**加载源**：
1. `skills/anthropic/skills/` — Anthropic 官方技能（Git 子模块）
2. `skills/custom/` — 项目自定义技能

**SKILL.md 格式**：
```yaml
---
name: skill-name
description: 触发条件描述
---
# 技能指令内容
...
```

#### 技能调用

- 用户发送 `/skill-name 任务描述`
- 技能指令注入到消息中
- 路由到 general Agent 处理

### 2.4 工具系统

**位置**: `backend/tools/`

#### 2.4.1 代码执行沙箱

**位置**: `backend/tools/sandbox.py`, `backend/tools/container_pool.py`

**容器池配置**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `pool_size` | 5 | 预热容器数量 |
| `max_uses_per_container` | 100 | 单容器最大使用次数 |
| `mem_limit` | 512m | 内存限制 |
| `cpu_quota` | 100000 | CPU 配额（1 CPU）|

**安全措施**：
- `network_disabled=True` — 禁用网络访问
- `cap_drop=["ALL"]` — 移除所有 Linux capabilities
- `security_opt=["no-new-privileges"]` — 禁止提权

**预装包**：
- Office 文档：`python-pptx`, `python-docx`, `openpyxl`
- 数据处理：`pandas`, `numpy`
- 图像处理：`Pillow`, `matplotlib`
- PDF：`pypdf`, `pdfplumber`, `reportlab`

**沙箱工具**：

| 工具 | 功能 |
|------|------|
| `execute_python(code)` | 执行 Python 代码，返回 stdout/stderr |
| `execute_python_with_file(code, filename)` | 执行代码并提取生成文件，返回下载链接 |

#### 2.4.2 文件处理系统

**位置**: `backend/tools/file_tools.py`

**允许格式**：
| 类型 | 扩展名 |
|------|--------|
| 文本文件 | `.txt`, `.md`, `.json`, `.csv` |
| PDF | `.pdf` |
| Word | `.doc`, `.docx` |
| PowerPoint | `.ppt`, `.pptx` |
| Excel | `.xls`, `.xlsx` |

**限制**：
| 限制项 | 值 |
|--------|-----|
| 最大文件大小 | 10MB |
| 文本截断 | 50KB |
| PDF 最大页数 | 20 页 |
| Excel 最大行数 | 500 行 |

**读取工具 `read_uploaded_file(file_id)`**：
- 文本文件：直接读取（超 50KB 截断）
- PDF：使用 pypdf 提取文本
- Word：使用 python-docx 提取段落
- Excel：使用 openpyxl 读取表格
- PowerPoint：使用 python-pptx 提取幻灯片文本

### 2.5 系统管理

#### 2.5.1 用户认证

**位置**: `backend/auth/`

**认证流程**：
```
用户登录 → POST /api/auth/login
    ↓
验证用户名 + 密码（bcrypt）
    ↓
检查用户状态（active/disabled）
    ↓
生成 JWT Token（含 user_id, role）
    ↓
Set-Cookie: access_token（HttpOnly, 24h）
    ↓
返回用户信息
```

**用户模型**：
```python
class User:
    id: UUID                  # 唯一标识
    username: str             # 用户名（3-20字符，字母数字下划线）
    password_hash: str        # bcrypt 哈希
    role: UserRole            # admin | user
    status: UserStatus        # active | disabled
    created_at: datetime
```

**权限控制**：
| 依赖函数 | 作用 | 失败响应 |
|----------|------|----------|
| `get_current_user()` | 验证 JWT，获取当前用户 | 401 Unauthorized |
| `require_admin()` | 验证用户为管理员 | 403 Forbidden |

**安全特性**：
- JWT 存储在 HttpOnly Cookie，防止 XSS
- 密码使用 bcrypt 哈希（自动加盐）
- 禁用账户无法登录
- 会话有效期 24 小时（可配置）

#### 2.5.2 管理员功能

**位置**: `backend/auth/router.py` (users_router)

**用户管理操作**：
| 操作 | 端点 | 说明 |
|------|------|------|
| 查看用户列表 | `GET /api/users` | 返回所有用户 |
| 创建用户 | `POST /api/users` | 指定用户名、密码、角色 |
| 禁用/启用用户 | `PATCH /api/users/{id}/status` | 切换用户状态 |
| 删除用户 | `DELETE /api/users/{id}` | 物理删除用户 |

**安全限制**：
- 不能删除自己的账户
- 不能禁用自己的账户
- 不能删除/禁用最后一个活跃管理员
- 密码无强度限制（用户自行管理）

---

## 3. API 接口清单

### 3.1 认证接口

| 端点 | 方法 | 权限 | 描述 |
|------|------|------|------|
| `/api/auth/login` | POST | - | 用户登录，返回 JWT Cookie |
| `/api/auth/logout` | POST | - | 清除认证 Cookie |
| `/api/auth/me` | GET | User | 获取当前用户信息 |

**LoginRequest**：
```typescript
{
  username: string;       // 用户名
  password: string;       // 密码
}
```

### 3.2 用户管理接口（仅管理员）

| 端点 | 方法 | 权限 | 描述 |
|------|------|------|------|
| `/api/users` | GET | Admin | 获取所有用户列表 |
| `/api/users` | POST | Admin | 创建新用户 |
| `/api/users/{id}` | DELETE | Admin | 删除用户 |
| `/api/users/{id}/status` | PATCH | Admin | 更新用户状态 |

**UserCreate**：
```typescript
{
  username: string;       // 用户名（3-20字符）
  password: string;       // 密码
  role: "admin" | "user"; // 角色
}
```

### 3.3 对话管理接口

| 端点 | 方法 | 权限 | 描述 |
|------|------|------|------|
| `/api/conversations` | GET | User | 获取用户对话列表 |
| `/api/conversations` | POST | User | 创建新对话 |
| `/api/conversations/{id}` | GET | User | 获取对话详情 |
| `/api/conversations/{id}` | PATCH | User | 更新对话标题 |
| `/api/conversations/{id}` | DELETE | User | 删除对话 |

**ConversationCreate**：
```typescript
{
  title?: string;         // 对话标题（默认 "New Conversation"）
}
```

### 3.4 聊天接口

| 端点 | 方法 | 权限 | 描述 |
|------|------|------|------|
| `/api/chat` | POST | User | 发送消息，返回 SSE 流 |
| `/api/threads/{id}/history` | GET | User | 获取对话历史 |
| `/api/agents` | GET | - | 列出已注册 Agent |

**ChatRequest 字段**：
```typescript
{
  thread_id: string;      // 对话线程 ID
  message: string;        // 用户消息
  agent?: string;         // 直接路由到指定 Agent（跳过 Supervisor）
  skill?: string;         // 激活技能（使用 general Agent）
  file_ids?: string[];    // 上传文件 ID 列表
}
```

### 3.5 技能接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/skills` | GET | 列出所有技能（name + description）|
| `/api/skills/{name}` | GET | 获取技能详情（含完整指令）|

### 3.6 文件接口

| 端点 | 方法 | 权限 | 描述 |
|------|------|------|------|
| `/api/files/upload` | POST | User | 上传文件（最大 10MB）|
| `/api/files/{id}/download` | GET | User | 下载上传的文件 |
| `/api/files/{id}/content` | GET | User | 预览文本文件内容 |
| `/api/files/{id}/{filename}` | GET | User | 下载沙箱生成的文件 |

---

## 4. SSE 事件流

**位置**: `backend/stream_handler.py`

### 事件类型

| 事件 | 数据 | 描述 |
|------|------|------|
| `text_delta` | `{ text: string }` | AI 回复文本片段 |
| `tool_call_start` | `{ id, name, args }` | 工具调用开始 |
| `tool_call_result` | `{ id, name, status, output }` | 工具调用结果 |
| `thinking` | `{ content: string }` | 路由/思考步骤 |
| `error` | `{ message: string }` | 错误信息 |
| `done` | `{}` | 流结束 |

### 隐藏工具

以下工具的调用显示为 "thinking" 事件而非工具卡片：
- `route` — Supervisor 路由工具
- `think_tool` — 研究反思工具

---

## 5. 数据流

### 5.1 完整消息流程

```
用户输入
    ↓
前端 InputBar 组件
    ↓ POST /api/chat (SSE)
FastAPI chat() 端点
    ↓ 注入文件元数据/技能指令/路由指令
LangGraph Supervisor
    ├─ 直接回答 → 流式文本
    └─ route() → 专业 Agent
                     ↓
               Agent 执行工具
                     ↓
               生成响应
    ↓ SSE 事件流
stream_handler.py
    ↓ 格式化 SSE
前端 streamChat()
    ↓ 解析事件
useChat hook
    ↓ 更新 React 状态
UI 渲染
```

### 5.2 文件处理流程

```
用户选择文件
    ↓
InputBar 文件上传
    ↓ POST /api/files/upload
保存到 /tmp/sunnyagent_files/{file_id}/
    ↓ 返回 file_id
前端保存 file_id
    ↓ 发送消息时附带 file_ids
chat() 注入文件元数据到消息
    ↓
路由到 general Agent
    ↓ 调用 read_uploaded_file(file_id)
读取并解析文件内容
    ↓
Agent 处理文件内容
```

### 5.3 代码执行流程

```
Agent 决定执行代码
    ↓ execute_python_with_file()
从容器池获取容器
    ↓
在容器中执行代码
    ↓ 代码保存文件到 /output/
从容器提取文件
    ↓ tar 包解压到宿主机
生成下载链接
    ↓
返回 Markdown 链接给用户
```

---

## 6. 数据持久化

### 6.1 数据库架构

**实现**：PostgreSQL + asyncpg 连接池

**连接池配置**：
| 参数 | 值 |
|------|-----|
| `min_size` | 2 |
| `max_size` | 10 |

**表结构**：

| 表 | 描述 |
|----|------|
| `users` | 用户账户（id, username, password_hash, role, status, created_at）|
| `conversations` | 对话元数据（id, thread_id, user_id, title, created_at, updated_at, is_deleted）|
| `files` | 上传文件元数据 |
| `langgraph_checkpoints` | LangGraph 状态（自动管理）|

### 6.2 LangGraph 持久化

**实现**：`AsyncPostgresSaver`（替代原 SQLite）

**线程 ID**：8 字符十六进制字符串（`uuid4().hex[:8]`）

**状态恢复**：
- 每次 `astream()` 调用自动从 checkpointer 恢复历史
- 只需发送新消息，历史自动关联

### 6.3 数据库迁移

**工具**：Alembic

**命令**：
```bash
cd infra && uv run alembic upgrade head    # 应用迁移
cd infra && uv run alembic downgrade -1    # 回滚
cd infra && uv run alembic revision -m "description"  # 创建迁移
```

**迁移文件**：
- `001_create_users_table.py` — 用户表 + 角色/状态枚举
- `002_create_conversations_table.py` — 对话表 + 更新触发器

---

## 7. 前端架构

### 7.1 页面布局

```
App
├─ LoginPage (未认证)
│  └─ 登录表单
│
└─ MainLayout (已认证)
   ├─ Sidebar（左侧导航）
   │  ├─ SidebarHeader（新建对话按钮）
   │  ├─ ConversationList（对话历史列表）
   │  │  └─ ConversationItem（单个对话项，支持编辑/删除）
   │  ├─ AdminMenu（仅管理员可见）
   │  │  └─ 用户管理入口
   │  └─ UserMenu（退出登录）
   │
   └─ Content Area（右侧内容）
      ├─ ChatContainer（对话界面）
      │  ├─ MessageList
      │  │  └─ MessageBubble
      │  │     ├─ ThinkingBubble
      │  │     ├─ ToolCallCard
      │  │     └─ FileCard
      │  └─ InputBar
      │
      └─ UserManagement（管理员用户管理页面）
         ├─ 用户列表
         └─ UserForm（创建用户表单）
```

### 7.2 状态管理

**useAuth hook**（认证上下文）：
```typescript
{
  user: UserInfo | null;     // 当前用户
  isLoading: boolean;        // 加载中
  isAuthenticated: boolean;  // 是否已认证
  login: (username, password) => Promise<void>;
  logout: () => Promise<void>;
}
```

**useConversations hook**：
```typescript
{
  conversations: Conversation[];  // 对话列表
  currentId: UUID | null;         // 当前对话 ID
  isLoading: boolean;
  create: (title?) => Promise<Conversation>;
  select: (id) => void;
  update: (id, title) => Promise<void>;
  remove: (id) => Promise<void>;
}
```

**useChat hook**：
```typescript
{
  messages: Message[];      // 消息列表
  isStreaming: boolean;     // 是否正在流式响应
  threadId: string | null;  // 当前对话线程 ID
  sendMessage: (text, agent?, files?) => void;
  cancel: () => void;       // 取消当前请求
  loadHistory: (threadId) => void;  // 加载历史消息
}
```

### 7.3 交互功能

- **登录/登出**：表单登录，Cookie 自动管理
- **对话切换**：点击左侧对话项切换，自动加载历史
- **对话管理**：重命名、删除对话
- **Agent 选择**：点击芯片直接路由到指定 Agent
- **技能调用**：输入 `/skill-name` 或点击技能选择器
- **文件上传**：点击 + 按钮选择本地文件
- **流式取消**：点击停止按钮中断响应
- **管理员功能**：创建/禁用/删除用户（仅管理员可见）

### 7.4 路由保护

```
访问页面
    ↓
检查 useAuth.isAuthenticated
    ├─ false → 重定向到 LoginPage
    └─ true → 渲染 MainLayout
              ↓
          检查管理员权限
              ├─ /admin/* 且非管理员 → 显示无权限
              └─ 其他 → 正常渲染
```

---

## 8. 扩展点

### 8.1 添加新 Agent

1. 创建 `backend/agents/new_agent.py`：
```python
from deepagents import create_deep_agent
from backend.registry import register_agent

_agent = create_deep_agent(
    model=...,
    tools=[...],
    system_prompt="...",
    name="new_agent",
)

register_agent(
    name="new_agent",
    description="Agent 能力描述",
    graph=_agent,
    tools=[...],
    icon="icon_name",
)
```

2. 在 `backend/agents/__init__.py` 中导入（**在 `build_general_agent()` 之前**）

### 8.2 添加 Package Agent

1. 创建 `packages/my-agent/AGENTS.md`
2. 可选添加 `packages/my-agent/skills/<skill>/SKILL.md`
3. 启动时自动加载

### 8.3 添加自定义技能

1. 创建 `skills/custom/my-skill/SKILL.md`：
```yaml
---
name: my-skill
description: 何时使用此技能的描述
---
# 技能指令

详细指令内容...
```

2. 启动时自动加载到 SKILL_REGISTRY

### 8.4 添加新工具

1. 使用 `@tool` 装饰器定义工具
2. 注册 Agent 时添加到 `tools` 列表
3. 如需所有 Agent 共享，添加到 general Agent 的工具列表

---

## 9. 配置项

### 9.1 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 是 | Anthropic API 密钥 |
| `TAVILY_API_KEY` | 是 | Tavily 搜索 API 密钥 |
| `DATABASE_URL` | 是 | PostgreSQL 连接字符串 |
| `JWT_SECRET_KEY` | 否 | JWT 签名密钥（不设置则自动生成）|
| `JWT_EXPIRATION` | 否 | Token 过期时间（秒，默认 86400）|
| `ADMIN_USERNAME` | 否 | 默认管理员用户名（首次启动时创建）|
| `ADMIN_PASSWORD` | 否 | 默认管理员密码 |
| `OPENAI_API_KEY` | 否 | OpenAI API 密钥（可选）|

### 9.2 开发命令

```bash
# 启动 PostgreSQL
docker compose up -d

# 后端
uv sync
uv run uvicorn backend.main:app --reload --port 8008

# 数据库迁移
cd infra && uv run alembic upgrade head

# 前端
cd frontend && npm install
cd frontend && npm run dev   # 开发服务器 :3008

# 类型检查
uv run pyright
cd frontend && npx tsc
```

---

## 10. 安全考虑

### 10.1 认证安全

- **密码存储**：bcrypt 哈希（自动加盐）
- **会话管理**：JWT 存储在 HttpOnly Cookie，防止 XSS
- **Token 有效期**：24 小时，可配置
- **账户状态**：禁用账户无法登录
- **管理员保护**：防止删除/禁用最后一个管理员

### 10.2 权限控制

- **用户隔离**：用户只能访问自己的对话
- **管理员权限**：用户管理仅管理员可访问
- **API 保护**：所有敏感端点需要认证

### 10.3 沙箱安全

- 网络隔离：容器无法访问网络
- 权限最小化：移除所有 Linux capabilities
- 资源限制：内存 512MB，CPU 配额受限
- 使用次数限制：单容器 100 次后销毁重建

### 10.4 文件安全

- 文件大小限制：10MB
- 扩展名白名单
- 临时存储：`/tmp/sunnyagent_files/`
- 用户隔离：文件与用户关联

### 10.5 API 安全

- CORS 限制开发服务器来源
- 文件 ID 使用 UUID 前缀，难以猜测
- JWT Cookie 使用 SameSite=Lax
