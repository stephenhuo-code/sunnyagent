# SunnyAgent 架构图

## 系统概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React)                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  ChatInput  │  │ MessageList │  │ToolCallCard │  │ ThinkingBubble      │ │
│  └──────┬──────┘  └──────▲──────┘  └──────▲──────┘  └──────────▲──────────┘ │
│         │                │                │                     │           │
│         └────────────────┼────────────────┼─────────────────────┘           │
│                          │                │                                  │
│                    ┌─────┴────────────────┴─────┐                           │
│                    │      useChat Hook          │                           │
│                    │   (SSE Event Consumer)     │                           │
│                    └─────────────┬──────────────┘                           │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │ SSE Stream
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend (main.py)                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────────┐ │
│  │  POST /api/chat  │  │ GET /api/files/* │  │ stream_handler.py          │ │
│  │                  │  │ (File Download)  │  │ (LangGraph → SSE Events)   │ │
│  └────────┬─────────┘  └──────────────────┘  └────────────────────────────┘ │
└───────────┼─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Supervisor (LangGraph StateGraph)                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         supervisor node                               │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  Claude Sonnet 4.5 + route() tool                               │ │   │
│  │  │                                                                  │ │   │
│  │  │  Routing Rules:                                                  │ │   │
│  │  │  • Simple questions → Direct response                           │ │   │
│  │  │  • Research tasks → route("research")                           │ │   │
│  │  │  • Database queries → route("sql")                              │ │   │
│  │  │  • Complex/Multi-step → route("general")                        │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│            ┌───────────────────────┼───────────────────────┐                │
│            │                       │                       │                │
│            ▼                       ▼                       ▼                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  research node  │    │    sql node     │    │  general node   │         │
│  │  (Deep Agent)   │    │  (Deep Agent)   │    │  (Deep Agent)   │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
│           ▼                      ▼                      ▼                   │
│        ┌─END─┐               ┌─END─┐               ┌─END─┐                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Agent 详细架构

### 1. Supervisor (路由器)

```
┌────────────────────────────────────────────────────────────────┐
│                        Supervisor                              │
│  Model: Claude Sonnet 4.5                                      │
│  Tools: route(agent_name, task_description)                    │
├────────────────────────────────────────────────────────────────┤
│  路由决策:                                                      │
│  • "今天天气怎么样" → Direct response (不路由)                  │
│  • "搜索最新的AI新闻" → route("research")                      │
│  • "查询销量最高的专辑" → route("sql")                         │
│  • "生成一个PPT" → route("general")                            │
│  • "研究并生成报告" → route("general")                         │
└────────────────────────────────────────────────────────────────┘
```

### 2. Research Agent (研究专家)

```
┌────────────────────────────────────────────────────────────────┐
│                      Research Agent                            │
│  Model: Claude Sonnet 4.5                                      │
│  Framework: deepagents.create_deep_agent()                     │
├────────────────────────────────────────────────────────────────┤
│  Tools:                                                        │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  tavily_search   │  │   think_tool     │                   │
│  │  (Web Search)    │  │  (Reflection)    │                   │
│  └────────┬─────────┘  └──────────────────┘                   │
│           │                                                    │
│           ▼                                                    │
│  ┌──────────────────────────────────────┐                     │
│  │         Tavily API                    │                     │
│  │    (Search + Full Page Fetch)         │                     │
│  └──────────────────────────────────────┘                     │
├────────────────────────────────────────────────────────────────┤
│  Bound Skills: pdf, web-scraping                               │
└────────────────────────────────────────────────────────────────┘
```

### 3. SQL Agent (数据库专家)

```
┌────────────────────────────────────────────────────────────────┐
│                        SQL Agent                               │
│  Model: Claude Sonnet 4.5                                      │
│  Framework: deepagents.create_deep_agent()                     │
├────────────────────────────────────────────────────────────────┤
│  Tools: SQLDatabaseToolkit                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │sql_db_query  │ │sql_db_schema │ │sql_db_list   │           │
│  │              │ │              │ │_tables       │           │
│  └──────┬───────┘ └──────────────┘ └──────────────┘           │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────────────────────────────┐                     │
│  │         Chinook SQLite DB            │                     │
│  │  (artists, albums, tracks, etc.)     │                     │
│  └──────────────────────────────────────┘                     │
└────────────────────────────────────────────────────────────────┘
```

### 4. General Agent (通用编排器)

```
┌────────────────────────────────────────────────────────────────┐
│                      General Agent                             │
│  Model: Claude Sonnet 4.5                                      │
│  Framework: deepagents.create_deep_agent()                     │
├────────────────────────────────────────────────────────────────┤
│  策略:                                                         │
│  • Direct: 直接使用工具完成简单任务                             │
│  • Delegate: 通过 task() 委托给子 agent                        │
├────────────────────────────────────────────────────────────────┤
│  Tools:                                                        │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  activate_skill  │  │     task()       │                   │
│  │ (Load Skill MD)  │  │ (Delegate Work)  │                   │
│  └──────────────────┘  └────────┬─────────┘                   │
│                                 │                              │
│  ┌──────────────────┐  ┌───────▼─────────┐                    │
│  │ execute_python   │  │   Subagents     │                    │
│  │ (Code Sandbox)   │  │ • research      │                    │
│  └──────────────────┘  │ • sql           │                    │
│                        │ • content-writer│                    │
│  ┌──────────────────┐  └─────────────────┘                    │
│  │execute_python    │                                          │
│  │  _with_file      │──────────┐                              │
│  │(Generate Files)  │          │                              │
│  └──────────────────┘          ▼                              │
│                       ┌─────────────────┐                     │
│                       │  Container Pool │                     │
│                       │ (Docker Sandbox)│                     │
│                       └─────────────────┘                     │
└────────────────────────────────────────────────────────────────┘
```

## Docker 沙箱执行流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Container Pool                                    │
│                                                                             │
│  启动时预热 5 个容器:                                                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │Container│ │Container│ │Container│ │Container│ │Container│              │
│  │   #1    │ │   #2    │ │   #3    │ │   #4    │ │   #5    │              │
│  │  idle   │ │  idle   │ │  idle   │ │  idle   │ │  idle   │              │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
│                                                                             │
│  预装包: python-pptx, python-docx, openpyxl, pandas, numpy,                │
│         Pillow, matplotlib, pypdf, pdfplumber, reportlab                   │
└─────────────────────────────────────────────────────────────────────────────┘

执行流程:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. acquire  │────▶│  2. exec_run │────▶│ 3. get_archive│────▶│  4. release  │
│   container  │     │   python -c  │     │  copy file   │     │   container  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼
                                    ┌──────────────────────┐
                                    │ /tmp/sunnyagent_files│
                                    │    /{file_id}/       │
                                    │     file.pptx        │
                                    └──────────────────────┘
                                                │
                                                ▼
                                    ┌──────────────────────┐
                                    │  GET /api/files/     │
                                    │  {file_id}/{name}    │
                                    │    → Download        │
                                    └──────────────────────┘
```

## SSE 事件流

```
Backend (LangGraph)                              Frontend (React)
       │                                               │
       │  ──────── text_delta ─────────▶              │ 更新消息内容
       │  {"text": "我来帮你..."}                      │
       │                                               │
       │  ──────── thinking ───────────▶              │ 显示思考气泡
       │  {"content": "Routing to research..."}       │
       │                                               │
       │  ──────── tool_call_start ────▶              │ 显示工具卡片 (运行中)
       │  {"id": "xxx", "name": "tavily_search",      │
       │   "args": {"query": "..."}}                   │
       │                                               │
       │  ──────── tool_call_result ───▶              │ 更新工具卡片 (完成)
       │  {"id": "xxx", "output": "..."}              │
       │                                               │
       │  ──────── done ───────────────▶              │ 结束流式响应
       │  {}                                          │
       │                                               │
```

## Agent 注册顺序

```
backend/agents/__init__.py 加载顺序:

1. load_all_skills()          # 加载全局技能 (pdf, web-scraping, etc.)
         │
         ▼
2. import research            # 注册 research agent
         │
         ▼
3. import sql                 # 注册 sql agent
         │
         ▼
4. load_package_agents()      # 扫描 packages/ 目录，注册包 agent
         │                    # (content-writer, etc.)
         ▼
5. build_general_agent()      # 最后注册 general agent
                              # (收集所有已注册 agent 作为 subagents)
```

## 文件结构

```
sunnyagent/
├── backend/
│   ├── main.py                 # FastAPI 应用入口
│   ├── supervisor.py           # Supervisor 路由器
│   ├── registry.py             # Agent 注册表
│   ├── stream_handler.py       # LangGraph → SSE 转换
│   ├── agents/
│   │   ├── __init__.py         # Agent 加载顺序控制
│   │   ├── research.py         # Research Agent
│   │   ├── sql.py              # SQL Agent
│   │   ├── general.py          # General Agent (编排器)
│   │   └── loader.py           # Package Agent 加载器
│   ├── tools/
│   │   ├── container_pool.py   # Docker 容器池
│   │   └── sandbox.py          # 代码执行工具
│   └── skills/
│       ├── registry.py         # Skill 注册表
│       └── loader.py           # Skill 加载器
├── packages/
│   └── content-writer/         # 包 Agent 示例
│       └── AGENTS.md
├── skills/                     # 全局技能定义
│   └── anthropic/              # Git submodule
├── dockerfiles/
│   └── sandbox/
│       ├── Dockerfile
│       └── requirements.txt
└── frontend/
    └── src/
        ├── hooks/useChat.ts    # SSE 消费者
        └── components/
            ├── ToolCallCard.tsx
            └── MessageBubble.tsx
```
