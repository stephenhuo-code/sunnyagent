# AIME 架构与 LLM Context 管理

> 本文档详细描述 AIME (Autonomous Intent-driven Multi-agent Executor) 的 LLM Context 管理机制，
> 包括 6 层架构设计、数据流和当前存在的问题。

## 概述

AIME 是 SunnyAgent 的核心决策引擎，负责：
1. **意图分析** - 理解用户请求的意图
2. **任务规划** - 将复杂任务分解为子任务
3. **Agent 路由** - 选择合适的 Agent 执行任务
4. **上下文管理** - 在各组件间传递必要的上下文信息

## 6 层 LLM Context 架构

系统采用分层 Context 架构，每层有明确的职责和生命周期：

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 1: System Prompt (系统提示)                                   │
│ ────────────────────────────────────────────────────────────────── │
│ 定义 Agent 的角色、能力和行为规范                                    │
│ - 生命周期：Agent 创建时固定                                        │
│ - 位置：各 Agent 代码中硬编码                                       │
│ - 示例：SQL Agent 的数据库查询规范、General Agent 的编排指令         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 2: Tool Schemas (工具模式)                                    │
│ ────────────────────────────────────────────────────────────────── │
│ 描述 Agent 可用的工具及其参数                                        │
│ - 生命周期：由 LangChain/LangGraph 自动管理                         │
│ - 位置：从 @tool 装饰器自动生成                                     │
│ - 内容：工具名称、描述、参数 schema、返回值说明                      │
│                                                                     │
│ 各 Agent 的工具配置：                                               │
│ ┌─────────────────────────────────────────────────────────────────┐│
│ │ Agent     │ 工具                                                ││
│ │───────────│─────────────────────────────────────────────────────││
│ │ sql       │ sql_db_query, sql_db_schema, sql_db_list_tables,   ││
│ │           │ read_file                                           ││
│ │ research  │ tavily_search, think_tool, read_file               ││
│ │ general   │ task, read_file, execute_python, activate_skill    ││
│ │ generic   │ read_file, execute_python, activate_skill          ││
│ └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 3: System Metadata (系统元数据) - SessionMetadata             │
│ ────────────────────────────────────────────────────────────────── │
│ 当前会话的上下文信息，用于权限控制和数据隔离                          │
│ - 生命周期：单次请求                                                │
│ - 位置：backend/aime/context.py                                    │
│                                                                     │
│ @dataclass                                                          │
│ class SessionMetadata:                                              │
│     user_id: str          # 当前用户 ID，用于权限验证               │
│     thread_id: str        # 对话线程 ID，用于消息历史               │
│     project_id: str | None # 关联的项目 ID（可选）                  │
│     project_name: str | None # 项目名称（可选，用于显示）           │
│     timestamp: datetime   # 请求时间戳                              │
│                                                                     │
│ 用途：                                                              │
│ - 文件权限验证：确保用户只能访问自己的文件                          │
│ - 对话隔离：thread_id 用于 LangGraph checkpoint 存储                │
│ - 项目关联：project_id 用于项目文件查询                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 4: Memory Blocks (记忆块) - ContextManager                    │
│ ────────────────────────────────────────────────────────────────── │
│ 任务间的上下文传递，支持复杂多步骤工作流                              │
│ - 生命周期：滑动过期（7 天无访问后过期）                             │
│ - 位置：backend/aime/context_manager.py                            │
│ - 存储：LRU 缓存 + PostgreSQL 持久化                                │
│                                                                     │
│ @dataclass                                                          │
│ class ContextEntry:                                                 │
│     context_id: str       # 任务 ID（主键）                         │
│     thread_id: str        # 会话 ID（外键，用于隔离）               │
│     content: str          # 任务输出内容                            │
│     summary: str | None   # LLM 生成的摘要（长内容）                │
│     key_data: dict | None # 提取的关键数据                          │
│     output_types: list[str] # 输出类型分类                          │
│     token_count: int      # Token 估计数                            │
│                                                                     │
│ 核心功能：                                                          │
│ - store(): 存储任务输出，自动分类和摘要                             │
│ - get(): 获取上下文，支持 thread_id 验证                            │
│ - prepare_for_task(): 为依赖任务准备上下文                          │
│                                                                     │
│ I/O 类型分类：                                                      │
│ - financial_report, revenue_data, table, chart                     │
│ - code, analysis_report, summary, file, raw_data                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 5: Files & Artifacts (文件与制品) - FileContext               │
│ ────────────────────────────────────────────────────────────────── │
│ 用户上传的文件和项目文件的元数据                                      │
│ - 生命周期：单次请求                                                │
│ - 位置：backend/aime/context.py                                    │
│                                                                     │
│ **设计原则**：                                                       │
│ > Files are passed as metadata only (not content)                  │
│ > to avoid intent pollution.                                       │
│ > Agent uses read_file tool to get actual content when needed.     │
│                                                                     │
│ @dataclass                                                          │
│ class FileInfo:                                                     │
│     file_id: str          # 文件唯一标识                            │
│     filename: str         # 原始文件名                              │
│     file_type: str        # 类型: pdf, excel, word, markdown...    │
│     project_id: str | None # 项目 ID（项目文件需要）                │
│                                                                     │
│ @dataclass                                                          │
│ class FileContext:                                                  │
│     files: list[FileInfo]                                          │
│                                                                     │
│     def to_prompt(self) -> str:                                    │
│         """生成文件提示词"""                                        │
│         # 输出格式：                                                │
│         # [可用文件]                                                │
│         # - filename (类型: xxx) → read_file(file_id="...", ...)   │
│         # 使用 read_file 工具读取文件内容。                         │
│                                                                     │
│ 支持的文件类型及处理方式：                                          │
│ ┌─────────────────────────────────────────────────────────────────┐│
│ │ 类型       │ 扩展名              │ 处理工具                      ││
│ │────────────│────────────────────│──────────────────────────────││
│ │ PDF        │ .pdf               │ pypdf                        ││
│ │ Word       │ .docx              │ python-docx                  ││
│ │ Excel      │ .xlsx, .xls        │ openpyxl                     ││
│ │ PowerPoint │ .pptx              │ python-pptx                  ││
│ │ 文本/代码  │ .txt, .md, .py...  │ 直接读取                     ││
│ └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 6: Message Buffer (消息缓冲) - LangGraph Checkpoints          │
│ ────────────────────────────────────────────────────────────────── │
│ 对话历史，支持多轮对话和状态恢复                                      │
│ - 生命周期：持久化存储                                              │
│ - 位置：PostgreSQL langgraph_checkpoints 表                        │
│ - 管理：由 LangGraph AsyncPostgresSaver 自动管理                    │
│                                                                     │
│ 存储内容：                                                          │
│ - 用户消息历史                                                      │
│ - Agent 响应历史                                                    │
│ - 工具调用记录                                                      │
│ - 状态快照（用于恢复）                                              │
│                                                                     │
│ 配置位置：backend/supervisor.py                                     │
│ checkpointer = AsyncPostgresSaver(pool)                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Context 聚合：AgentContext

`AgentContext` 是聚合多个 Context 层的主要数据结构：

```python
# backend/aime/context.py

@dataclass
class AgentContext:
    """Agent 执行上下文 - 聚合 Layer 3 和 Layer 5"""

    # Layer 3: 会话元数据
    session: SessionMetadata

    # Layer 5: 文件上下文
    files: FileContext = field(default_factory=FileContext)

    # Layer 4: 记忆块引用（ID 列表，实际内容由 ContextManager 管理）
    memory_ids: list[str] = field(default_factory=list)

    # 路由控制
    explicit_agent: str | None = None  # 强制路由到指定 Agent
    skill: str | None = None           # 注入技能指令

    def build_context_prompt(self) -> str:
        """构建完整的上下文提示词（用于 Agent 执行）

        输出格式：
        [会话信息]
        User: {user_id}
        Project: {project_name}

        [可用文件]
        - filename (类型: xxx) → read_file(file_id="...", project_id="...")

        使用 read_file 工具读取文件内容。
        """
```

## 当前数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           1. API 入口 (main.py)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  POST /api/chat                                                             │
│  ├─ 请求体: { thread_id, message, project_id, project_file_ids, ... }      │
│  │                                                                          │
│  ├─ 创建 AgentContext (356-365行)                                           │
│  │   context = AgentContext(                                                │
│  │       session=SessionMetadata(user_id, thread_id, project_id),          │
│  │       files=FileContext(files=[FileInfo(file_id, filename, type, pid)]) │
│  │   )                                                                      │
│  │                                                                          │
│  ├─ 构建上下文提示词并注入消息 (368-371行)                                   │
│  │   context_prompt = context.build_context_prompt()                        │
│  │   message = f"{context_prompt}\n\n---\n\n{user_message}"                 │
│  │   ✅ 注意：此消息用于 Agent 执行，意图分析使用简化版本                    │
│  │                                                                          │
│  │   扩展后的消息示例：                                                     │
│  │   ┌─────────────────────────────────────────────────────────────────┐   │
│  │   │ [会话信息]                                                       │   │
│  │   │ User: a430058d-d087-432...                                      │   │
│  │   │ Project: xxx                                                    │   │
│  │   │                                                                 │   │
│  │   │ [可用文件]                                                       │   │
│  │   │ - file.md (类型: markdown)                                      │   │
│  │   │   → read_file(file_id="abc", project_id="...")                 │   │
│  │   │                                                                 │   │
│  │   │ 使用 read_file 工具读取文件内容。                                │   │
│  │   │                                                                 │   │
│  │   │ ---                                                             │   │
│  │   │                                                                 │   │
│  │   │ 用户原始消息                                                    │   │
│  │   └─────────────────────────────────────────────────────────────────┘   │
│  │                                                                          │
│  └─ 调用 stream_aime_response(message=扩展消息, context=AgentContext)       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      2. AIMEPlanner.process() (planner.py)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  async def process(message, thread_id, context):                            │
│                                                                             │
│  ├─ 意图分析 (157行) - 直接传递 AgentContext                                │
│  │   intent = await self.intent_analyzer.analyze(message, context)         │
│  │   ✅ IntentAnalyzer 内部提取简化上下文（仅项目名、文件名）               │
│  │   ✅ 不包含 file_id、project_id、read_file 工具提示                      │
│  │                                                                          │
│  └─ 根据 intent.action 路由                                                 │
│      - "direct_reply" → _handle_direct_reply(message, ...)                 │
│      - "delegate"     → _handle_delegate(message, ...)                     │
│      - "plan"         → _handle_plan(message, ...)                         │
│      - "clarify"      → _handle_clarify(...)                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  3. IntentAnalyzer.analyze() (intent/analyzer.py)           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  分类器链（按优先级顺序执行，首个返回非 None 结果的胜出）：                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Priority 0: RuleBasedClassifier                                     │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │ 检测显式路由指令：                                                   │   │
│  │ - [ROUTE_TO: agent_name] 模式                                       │   │
│  │ - context["explicit_agent"] 字段                                    │   │
│  │                                                                     │   │
│  │ 返回：IntentResult(action="delegate", explicit_agent="xxx")         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                           │ (如果不匹配，继续)                              │
│                           ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Priority 10: LLMClassifier                                          │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │ 使用 LLM 进行语义分析                                                │   │
│  │                                                                     │   │
│  │ 系统提示定义可用动作：                                               │   │
│  │ - direct_reply: 简单问题直接回答                                    │   │
│  │ - delegate: 路由到专业 Agent                                        │   │
│  │ - plan: 复杂任务分解                                                │   │
│  │ - clarify: 需要澄清                                                 │   │
│  │                                                                     │   │
│  │ 上下文感知：                                                         │   │
│  │ - 如果用户选择了文件，会提示 LLM 这是文件相关任务                    │   │
│  │ - LLM 根据语义判断任务类型和所需能力                                 │   │
│  │                                                                     │   │
│  │ 返回：IntentResult(action=xxx, confidence=x.x, capabilities=[...]) │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                4. ActorFactory.select_actor() (actor_factory.py)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  根据 IntentResult 选择 Actor，优先级如下：                                  │
│                                                                             │
│  1. explicit_agent 优先                                                     │
│     如果 intent.explicit_agent 指定，直接使用                               │
│                                                                             │
│  2. 能力匹配                                                                │
│     根据 intent.capabilities 在 AGENT_REGISTRY 中匹配：                     │
│     ┌───────────────────────────────────────────────────────────────┐      │
│     │ Capabilities              │ Agent    │ 工具                   │      │
│     │───────────────────────────│──────────│───────────────────────│      │
│     │ ["database", "sql_query"] │ sql      │ SQLDatabaseToolkit +  │      │
│     │                           │          │ read_file             │      │
│     │ ["web_search"]            │ research │ tavily_search +       │      │
│     │                           │          │ read_file             │      │
│     │ ["code_execution"]        │ general  │ task, execute_python, │      │
│     │                           │          │ read_file             │      │
│     └───────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  3. Generic fallback                                                        │
│     无匹配时创建 generic actor (有 read_file 工具)                          │
│                                                                             │
│  **注意**：所有专业 Agent 现在都配置了 read_file 工具，                       │
│  确保在处理文件相关任务时能够正确读取文件内容。                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     5. _execute_actor() (planner.py)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  使用扩展后的 message 调用 Agent 执行：                                      │
│                                                                             │
│  stream_agent_response(                                                     │
│      agent=actor.graph,                                                     │
│      thread_id=thread_id,                                                   │
│      message=message,  # 包含完整上下文的扩展消息                            │
│      task_id=spec.id,                                                       │
│      user_id=user_id,                                                       │
│  )                                                                          │
│                                                                             │
│  Agent 看到完整的上下文，包含 read_file 使用说明                             │
│  ✅ 所有专业 Agent（SQL、Research）现在都配置了 read_file 工具              │
│     可以正确读取用户选择的文件                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 已修复问题

### 问题 1：专业 Agent 文件访问

#### 问题场景（已修复）

用户选择项目文件后问"这两个文件有关系吗"：

```
输入：
├─ 用户消息: "这两个文件有关系吗"
└─ 项目文件: [constitution.md, openclaw_enterprise.md]

实际传给意图分析的消息：
┌────────────────────────────────────────────────────────────────────────────┐
│ [会话信息]                                                                  │
│ User: a430058d-d087-432...                                                 │
│ Project: xxx                                                               │
│                                                                            │
│ [可用文件]                                                                  │
│ - constitution.md (类型: markdown)                                         │
│   → read_file(file_id="abc123", project_id="proj456")                     │
│ - openclaw_enterprise.md (类型: markdown)                                  │
│   → read_file(file_id="def789", project_id="proj456")                     │
│                                                                            │
│ 使用 read_file 工具读取文件内容。                                           │
│                                                                            │
│ ---                                                                        │
│                                                                            │
│ 这两个文件有关系吗                                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 修复方案 ✅

**为所有专业 Agent 添加 `read_file` 工具**

| Agent | 修改前 | 修改后 |
|-------|--------|--------|
| SQL | SQLDatabaseToolkit | SQLDatabaseToolkit + read_file |
| Research | tavily_search, think_tool | tavily_search, think_tool, read_file |
| General | 已有 read_file | 无变化 |
| Generic | 已有 read_file | 无变化 |

**修改文件：**
- `backend/agents/sql.py` - 添加 `read_file` 到工具列表
- `backend/agents/research.py` - 添加 `read_file` 到工具列表

### 问题 2：意图污染

**解决方案**（`backend/aime/intent/analyzer.py`）：

```python
# IntentAnalyzer.analyze() 内部处理
if isinstance(context, AgentContext):
    # Extract semantic information only (no file_id, project_id, tool hints)
    parts = []
    if context.session.project_name:
        parts.append(f"用户在项目「{context.session.project_name}」中工作")
    if context.files.files:
        file_names = [f"「{f.filename}」" for f in context.files.files]
        parts.append(f"用户选择了文件: {', '.join(file_names)}")

    intent_context_str = "。".join(parts) + "。\n\n"

# 构建简化的意图分析消息
intent_message = f"{intent_context_str}{message}"
```

**修复效果**：

| 问题 | 状态 | 解决方式 |
|------|------|---------|
| 意图分析输入污染 | ✅ 已修复 | IntentAnalyzer 构建独立的 `intent_message` |
| context_dict 信息缺失 | ✅ 已修复 | 直接传递 AgentContext，内部提取所需信息 |
| 上下文注入时机错误 | ✅ 已修复 | 意图分析使用简化消息，执行阶段使用完整消息 |

**关键设计**：
- 意图分析：只看项目名和文件名（语义信息）
- Agent 执行：看完整上下文（含 file_id、read_file 工具提示）

## 组件文件位置

| 组件 | 文件 | 说明 |
|------|------|------|
| Context 模型 | `backend/aime/context.py` | AgentContext, FileContext, SessionMetadata |
| Context 管理 | `backend/aime/context_manager.py` | 任务间上下文存储和检索 (Layer 4) |
| 意图分析器 | `backend/aime/intent/analyzer.py` | IntentAnalyzer 分类器链协调 |
| 规则分类器 | `backend/aime/intent/classifiers/rule_based.py` | 显式路由检测 |
| LLM 分类器 | `backend/aime/intent/classifiers/llm_based.py` | 语义分析（主要分类器） |
| Planner | `backend/aime/planner.py` | 任务规划和执行协调 |
| Actor 工厂 | `backend/aime/actor_factory.py` | Agent 选择和实例化 |
| Generic Actor | `backend/aime/actors/generic.py` | 通用 Actor（有 read_file） |
| SQL Agent | `backend/agents/sql.py` | SQL 查询 Agent（有 read_file） |
| Research Agent | `backend/agents/research.py` | 研究 Agent（有 read_file） |
| API 入口 | `backend/main.py` | 请求处理和 AgentContext 创建 |
