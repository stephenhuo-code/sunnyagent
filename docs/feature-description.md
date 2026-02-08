# Sunny Agent 功能规范

> 一个基于 LangGraph 的多 Agent 对话系统，通过 Supervisor 路由将用户请求分发到专业 Deep Agent 处理。

---

## 1. 产品概述

Sunny Agent 是一个全栈 Web 应用（FastAPI + React），核心是一个 LangGraph Supervisor，能将用户消息智能路由到多个专业 Deep Agent，支持网页研究、SQL 数据库查询、文件处理和沙箱代码执行。

**技术栈**：
- 后端：FastAPI, LangGraph, LangChain, deepagents
- 前端：React 19, Vite 7, TypeScript
- LLM：Claude claude-sonnet-4-5-20250929（通过 Anthropic API）
- 数据库：SQLite（对话持久化 + Chinook 示例数据库）
- 容器化：Docker 容器池用于代码沙箱执行

---

## 2. 核心能力

### 2.1 Supervisor 路由系统

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

### 2.2 Agent 注册中心

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

### 2.3 专业 Deep Agent

#### 2.3.1 Research Agent（研究 Agent）

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

#### 2.3.2 SQL Agent（数据库 Agent）

**位置**: `backend/agents/sql.py`

**能力**：
- 查询 Chinook 音乐商店数据库
- 支持表：artists, albums, tracks, customers, invoices, employees

**工具**：SQLDatabaseToolkit 提供的标准 SQL 工具集

#### 2.3.3 General Agent（通用编排 Agent）

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

#### 2.3.4 Package Agent（包 Agent）

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

### 2.4 代码执行沙箱

**位置**: `backend/tools/sandbox.py`, `backend/tools/container_pool.py`

#### 容器池管理

**配置**：
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

#### 沙箱工具

**`execute_python(code: str)`**：
- 在沙箱中执行 Python 代码
- 返回 stdout/stderr 输出

**`execute_python_with_file(code: str, output_filename: str)`**：
- 执行代码并从 `/output/` 目录提取生成的文件
- 返回 Markdown 格式下载链接

### 2.5 文件处理系统

**位置**: `backend/tools/file_tools.py`

#### 上传支持

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

#### 读取工具

**`read_uploaded_file(file_id: str)`**：
- 文本文件：直接读取（超 50KB 截断）
- PDF：使用 pypdf 提取文本
- Word：使用 python-docx 提取段落
- Excel：使用 openpyxl 读取表格
- PowerPoint：使用 python-pptx 提取幻灯片文本

### 2.6 技能系统

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

---

## 3. API 接口清单

### 3.1 对话接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回 SSE 流 |
| `/api/threads` | POST | 创建新对话线程 |
| `/api/threads/{id}/history` | GET | 获取对话历史 |
| `/api/agents` | GET | 列出已注册 Agent |

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

### 3.2 技能接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/skills` | GET | 列出所有技能（name + description）|
| `/api/skills/{name}` | GET | 获取技能详情（含完整指令）|

### 3.3 文件接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/files/upload` | POST | 上传文件（最大 10MB）|
| `/api/files/{id}/download` | GET | 下载上传的文件 |
| `/api/files/{id}/content` | GET | 预览文本文件内容 |
| `/api/files/{id}/{filename}` | GET | 下载沙箱生成的文件 |

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

## 6. 对话持久化

**实现**：LangGraph `AsyncSqliteSaver`

**存储位置**：项目根目录 `threads.db`

**线程 ID**：8 字符十六进制字符串（`uuid4().hex[:8]`）

**状态恢复**：
- 每次 `astream()` 调用自动从 checkpointer 恢复历史
- 只需发送新消息，历史自动关联

---

## 7. 前端架构

### 7.1 组件结构

```
App
└─ ChatContainer
   ├─ MessageList
   │  └─ MessageBubble
   │     ├─ ThinkingBubble    # 思考步骤显示
   │     ├─ ToolCallCard      # 工具调用卡片
   │     └─ FileCard          # 文件附件卡片
   └─ InputBar
      ├─ Agent 选择器
      ├─ 文件上传
      ├─ 技能选择器
      └─ 文本输入框
```

### 7.2 状态管理

**useChat hook**：
```typescript
{
  messages: Message[];      // 消息列表
  isStreaming: boolean;     // 是否正在流式响应
  threadId: string | null;  // 当前对话线程 ID
  sendMessage: (text, agent?, files?) => void;
  cancel: () => void;       // 取消当前请求
  newThread: () => void;    // 开始新对话
}
```

### 7.3 交互功能

- **Agent 选择**：点击芯片直接路由到指定 Agent
- **技能调用**：输入 `/skill-name` 或点击技能选择器
- **文件上传**：点击 + 按钮选择本地文件
- **流式取消**：点击停止按钮中断响应

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
| `OPENAI_API_KEY` | 否 | OpenAI API 密钥（可选）|

### 9.2 开发命令

```bash
# 后端
uv sync
uv run uvicorn backend.main:app --reload --port 8008

# 前端
cd frontend && npm install
cd frontend && npm run dev   # 开发服务器 :3008

# 类型检查
uv run pyright
cd frontend && npx tsc
```

---

## 10. 安全考虑

### 10.1 沙箱安全

- 网络隔离：容器无法访问网络
- 权限最小化：移除所有 Linux capabilities
- 资源限制：内存 512MB，CPU 配额受限
- 使用次数限制：单容器 100 次后销毁重建

### 10.2 文件安全

- 文件大小限制：10MB
- 扩展名白名单
- 临时存储：`/tmp/sunnyagent_files/`

### 10.3 API 安全

- CORS 限制开发服务器来源
- 文件 ID 使用 UUID 前缀，难以猜测
