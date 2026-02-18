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
│ │ sql       │ sql_db_query, sql_db_schema, sql_db_list_tables    ││
│ │ research  │ tavily_search                                       ││
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
│  ├─ 构建上下文提示词并注入消息 (368-371行) ⚠️ 问题点                         │
│  │   context_prompt = context.build_context_prompt()                        │
│  │   message = f"{context_prompt}\n\n---\n\n{user_message}"                 │
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
│  ├─ 从 AgentContext 提取 context_dict (136-144行)                           │
│  │   context_dict = {                                                       │
│  │       "explicit_agent": context.explicit_agent,                         │
│  │       "skill": context.skill,                                           │
│  │       "user_id": context.session.user_id,                               │
│  │       "project_id": context.session.project_id,                         │
│  │   }                                                                      │
│  │   ⚠️ 问题：没有传递 files 元数据到 context_dict                          │
│  │                                                                          │
│  ├─ 意图分析 (160行)                                                        │
│  │   intent = await self.intent_analyzer.analyze(message, context_dict)    │
│  │   ⚠️ 问题：message 是扩展后的消息，包含会污染意图分析的上下文            │
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
│  │ Priority 10: KeywordClassifier                                      │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │ 在 message 中搜索关键词模式：                                        │   │
│  │                                                                     │   │
│  │ 直接回复模式：                                                       │   │
│  │   (你好|hello|hi|谢谢|再见|...)                                     │   │
│  │                                                                     │   │
│  │ 研究模式：                                                           │   │
│  │   (搜索|查找|最新|比较|怎么样|...)                                   │   │
│  │                                                                     │   │
│  │ 数据库模式：⚠️ 可能误匹配上下文中的 file_id, project_id              │   │
│  │   (数据库|database|sql|表|table|记录|record|...)                    │   │
│  │                                                                     │   │
│  │ 复杂任务模式：                                                       │   │
│  │   (并且|然后|第一|第二|报告|...)                                     │   │
│  │                                                                     │   │
│  │ 返回：IntentResult(action=xxx, capabilities=[...])                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                           │ (如果不匹配，继续)                              │
│                           ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Priority 20: LLMClassifier                                          │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │ 使用 LLM 进行语义分析                                                │   │
│  │                                                                     │   │
│  │ 系统提示定义可用动作：                                               │   │
│  │ - direct_reply: 简单问题直接回答                                    │   │
│  │ - delegate: 路由到专业 Agent                                        │   │
│  │ - plan: 复杂任务分解                                                │   │
│  │ - clarify: 需要澄清                                                 │   │
│  │                                                                     │   │
│  │ ⚠️ LLM 看到完整的扩展消息，可能误判意图                              │   │
│  │   例如看到 file_id, project_id 误以为是数据库相关                    │   │
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
│     │ ["database", "sql_query"] │ sql      │ SQLDatabaseToolkit    │      │
│     │ ["web_search"]            │ research │ tavily_search         │      │
│     │ ["code_execution"]        │ general  │ task, execute_python  │      │
│     └───────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  3. Generic fallback                                                        │
│     无匹配时创建 generic actor (有 read_file 工具)                          │
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
│  ⚠️ 但如果路由到错误的 Agent（如 SQL），该 Agent 可能没有 read_file 工具    │
│     导致 LLM 幻觉出工具调用                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 当前问题：意图污染

### 问题场景

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

### 误判过程

```
LLMClassifier 分析过程：
├─ 看到: file_id, project_id, read_file
├─ 推断: 涉及数据存取操作
├─ 返回: capabilities=["database", "sql_query"]
└─ 路由: SQL Agent

后果：
├─ SQL Agent 只有 SQLDatabaseToolkit 工具
├─ 没有 read_file 工具
├─ LLM 看到消息中的 read_file 指令
├─ 尝试调用不存在的工具（幻觉）
└─ 参数格式错误（file_path 而非 file_id）
```

### 问题根源

1. **意图分析输入污染**：`message` 包含了不应该用于意图判断的上下文信息
2. **context_dict 信息缺失**：没有传递结构化的文件元数据供意图分析使用
3. **上下文注入时机错误**：在意图分析之前就注入了执行阶段才需要的信息

## 组件文件位置

| 组件 | 文件 | 说明 |
|------|------|------|
| Context 模型 | `backend/aime/context.py` | AgentContext, FileContext, SessionMetadata |
| Context 管理 | `backend/aime/context_manager.py` | 任务间上下文存储和检索 (Layer 4) |
| 意图分析器 | `backend/aime/intent/analyzer.py` | IntentAnalyzer 分类器链协调 |
| 规则分类器 | `backend/aime/intent/classifiers/rule_based.py` | 显式路由检测 |
| 关键词分类器 | `backend/aime/intent/classifiers/keyword_based.py` | 快速模式匹配 |
| LLM 分类器 | `backend/aime/intent/classifiers/llm_based.py` | 语义分析 |
| Planner | `backend/aime/planner.py` | 任务规划和执行协调 |
| Actor 工厂 | `backend/aime/actor_factory.py` | Agent 选择和实例化 |
| Generic Actor | `backend/aime/actors/generic.py` | 通用 Actor（有 read_file） |
| API 入口 | `backend/main.py` | 请求处理和 AgentContext 创建 |
