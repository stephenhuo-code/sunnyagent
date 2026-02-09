# Sunny Agent

> Supervisor + Deep Agent 架构

一个基于 FastAPI + React 的聊天界面，使用 **LangGraph Supervisor** 将用户消息路由到专业的 **Deep Agent**：

- **research** — 网络调研、时事新闻、话题对比（Tavily 搜索）
- **sql** — 在 Chinook 音乐数据库上执行 SQL 查询（艺术家、专辑、曲目、客户、发票、员工）
- **general** — 兜底协调器，处理复杂的多步骤或跨领域任务；可通过 `task()` 委派给任意专业 Agent
- **包 Agent（Package Agents）** — 从 `packages/` 目录自动加载的可扩展 Agent（如 content-writer）
- **文件处理** — 支持上传和解析 PDF/Word/Excel/PPT 文件
- **代码执行** — Docker 沙箱环境执行 Python 代码，生成可下载文件

Supervisor 分析每条消息后，要么直接回答（简单问题），要么路由到合适的专业 Agent。跨领域的复杂查询由 general agent 处理，它能协调所有工具并委派给各专业 Agent。

```
                    ┌─────────────────────┐
       用户消息 ──▶ │     Supervisor      │
                    │  (LangGraph 路由器) │
                    └────────┬────────────┘
                             │
                ┌────────────┼────────────┐
                │ 简单问题   │ 专业任务   │ 复杂任务
                ▼            ▼             ▼
          ┌──────────┐ ┌──────────┐ ┌─────────────┐
          │  直接     │ │ Research │ │   General   │
          │  回答     │ │  / SQL   │ │  (兜底)     │
          └──────────┘ └──────────┘ │ 所有工具 +  │
                                    │ task() →    │
                                    │ 专业 Agent  │
                                    └─────────────┘
                                           │
                                    ┌──────┴──────┐
                                    │   Tools     │
                                    ├─────────────┤
                                    │ • Sandbox   │ ← Docker 容器池
                                    │ • File I/O  │ ← 文件解析
                                    │ • Skills    │ ← 技能注入
                                    └─────────────┘
```

## 前置要求

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Docker + Docker Compose（用于 PostgreSQL 和代码执行沙箱）
- API 密钥：`ANTHROPIC_API_KEY` 和 `TAVILY_API_KEY`

## 安装

```bash
# 1. 配置 API 密钥
cp .env.example .env
# 编辑 .env 填入你的密钥

# 2. 安装 Python 依赖
uv sync

# 3. 安装前端依赖
cd frontend
npm install
cd ..
```

Chinook SQLite 数据库会在后端首次启动时自动下载。

## 运行

### 方式一：使用管理脚本（推荐）

```bash
# 一键启动所有服务（PostgreSQL + 数据库迁移 + 后端）
./scripts/sunnyagent.sh start

# 一键停止所有服务
./scripts/sunnyagent.sh stop

# 查看服务状态
./scripts/sunnyagent.sh status
```

**完整命令列表：**

| 命令 | 说明 |
|------|------|
| `start` | 启动所有服务（PostgreSQL + 迁移 + 后端） |
| `stop` | 停止所有服务（清理沙箱 + 停止 PostgreSQL） |
| `restart` | 重启所有服务 |
| `infra` | 仅启动基础设施（PostgreSQL） |
| `infra-stop` | 仅停止基础设施 |
| `status` | 查看服务状态 |
| `logs` | 查看 PostgreSQL 日志 |
| `clean` | 清理所有容器和数据卷（危险操作） |

### 方式二：手动启动

**终端 1 — 启动基础设施：**
```bash
docker-compose up -d postgres
uv run alembic upgrade head
uv run uvicorn backend.main:app --reload --port 8008
```

**终端 2 — 前端（端口 3008）：**
```bash
cd frontend
npm run dev
```

在浏览器中打开 http://localhost:3008。

## 查询示例

| 类型 | 示例 |
|------|------|
| 直接回答 | "你好！" / "2+2 等于多少？" |
| 网络调研 | "AI Agent 领域最新有哪些进展？" |
| SQL 查询 | "有多少客户来自巴西？" |
| SQL 查询 | "哪位艺术家的专辑最多？" |
| 复杂任务（general） | "对比数据库中巴西客户的消费情况和当前巴西的经济研究" |
| 斜杠命令 | `/research AI 趋势` — 跳过 Supervisor 直接路由到指定 Agent |

## 架构

```
backend/
  main.py               FastAPI 应用，SSE 流式响应
  supervisor.py          LangGraph StateGraph 路由器（Supervisor）
  registry.py            Agent 注册系统
  models.py              Pydantic 请求/响应模型
  stream_handler.py      将 LangGraph astream() 转换为 SSE 事件
  agents/
    __init__.py          自动导入触发注册（顺序重要）
    research.py          Research Deep Agent（Tavily + think）
    sql.py               SQL Deep Agent（Chinook 数据库）
    general.py           General 兜底 Deep Agent（所有工具 + task 委派）
    loader.py            包 Agent 加载器（扫描 packages/ 目录）
  tools/
    container_pool.py    Docker 容器池管理（预热 5 个容器，~10-50ms 响应）
    sandbox.py           代码执行工具（execute_python, execute_python_with_file）
    file_tools.py        文件读取工具（read_uploaded_file，支持 PDF/Word/Excel/PPT）
  skills/
    registry.py          技能注册表（SKILL_REGISTRY）
    loader.py            技能加载器（从 skills/ 目录加载）
  prompts.py             SQL 子 Agent 系统提示词
  research_prompts.py    Research 子 Agent 系统提示词
  research_tools.py      Tavily 搜索 + think 工具实现

frontend/
  src/
    api/client.ts        SSE 流式客户端（fetch + ReadableStream）
    hooks/useChat.ts     聊天状态管理，支持 /command 斜杠命令
    components/          React UI 组件
    types/               TypeScript 类型定义

packages/                可扩展的 Agent 包目录
  content-writer/        示例：内容写作 Agent
    AGENTS.md            Agent 系统提示词
    skills/              技能定义
      blog-post/SKILL.md
      social-media/SKILL.md

skills/                  技能定义目录
  anthropic/             Anthropic 官方技能（git submodule）
  custom/                项目自定义技能
```

每个专业 Agent 都是完整的 `create_deep_agent()`，拥有独立的中间件栈（TodoList、Filesystem、Summarization 等）。Supervisor 是一个轻量级的 `create_agent()`，通过 `route` 工具返回 `Command(goto=...)` 给父 StateGraph 实现路由。

## 流式传输（SSE 事件）

后端通过 Server-Sent Events 向前端推送以下事件类型：

| 事件类型 | 说明 |
|----------|------|
| `text_delta` | 流式文本内容片段 |
| `thinking` | 推理过程（`route` 和 `think_tool` 的输出） |
| `tool_call_start` | 工具调用开始（包含工具名和参数） |
| `tool_call_result` | 工具执行结果 |
| `error` | 错误信息 |
| `done` | 流结束 |

## 添加新 Agent

### 代码 Agent

1. 创建 `backend/agents/new_agent.py` — 使用 `create_deep_agent()` + `register_agent()`
2. 在 `backend/agents/__init__.py` 中导入（必须在 `build_general_agent()` **之前**）
3. 重启后端 — Supervisor 和 General Agent 会自动发现新 Agent

### 包 Agent（Package Agent）

1. 创建 `packages/my-agent/AGENTS.md`（系统提示词）
2. 可选：添加 `packages/my-agent/skills/<skill-name>/SKILL.md`（技能定义）
3. 后端启动时自动加载，无需修改代码

## API

### 聊天与会话

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回 SSE 流 |
| `/api/threads` | POST | 创建新会话线程 |
| `/api/threads/{id}/history` | GET | 获取会话历史消息 |
| `/api/agents` | GET | 列出所有已注册的 Agent |

**ChatRequest 字段**：`thread_id`、`message`、`agent`（跳过 Supervisor 直接路由）、`skill`（注入技能指令）、`file_ids`（关联上传的文件）

### 技能

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET | 列出所有技能（名称 + 描述） |
| `/api/skills/{name}` | GET | 获取技能详情和完整指令 |

### 文件

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/files/upload` | POST | 上传文件（最大 10MB） |
| `/api/files/{id}/download` | GET | 下载上传的文件 |
| `/api/files/{id}/content` | GET | 预览文本文件内容 |
| `/api/files/{id}/{filename}` | GET | 下载沙箱生成的文件 |
