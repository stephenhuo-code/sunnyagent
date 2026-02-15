# Architecture: AIME Agent Core

**Branch**: `005-aime-supervisor` | **Date**: 2026-02-15 | **Plan**: [plan.md](./plan.md)

## Overview

本文档描述 AIME 架构的核心组件及其交互关系。

---

## 1. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AIME Architecture                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  User Request                                                                   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         AIME Planner                                     │   │
│  │                    (替换 Supervisor + General)                           │   │
│  │                                                                          │   │
│  │  ┌─────────────────────┐      ┌─────────────────────────────────────┐   │   │
│  │  │   IntentAnalyzer    │      │        Task Decomposer              │   │   │
│  │  │  ┌───────────────┐  │      │                                     │   │   │
│  │  │  │ RuleClassifier│──┼──┐   │  action=plan 时分解为 SubtaskSpec[] │   │   │
│  │  │  │ KeywordClass. │  │  │   │                                     │   │   │
│  │  │  │ LLMClassifier │  │  │   └─────────────────────────────────────┘   │   │
│  │  │  └───────────────┘  │  │                                              │   │
│  │  │                     │  │   输出: IntentResult                         │   │
│  │  │  输出:              │  │   ├─ action: direct_reply|delegate|plan|clarify│  │
│  │  │  IntentResult       │  │   ├─ confidence: 0.0-1.0                     │   │
│  │  └─────────────────────┘  │   └─ capabilities: ["web_search", ...]       │   │
│  │                           │                                              │   │
│  └───────────────────────────┼──────────────────────────────────────────────┘   │
│                              │                                                   │
│          ┌───────────────────┴───────────────────┐                              │
│          │                                       │                              │
│          ▼                                       ▼                              │
│  ┌───────────────┐                      ┌─────────────────┐                     │
│  │ direct_reply  │                      │ delegate / plan │                     │
│  │ 直接回复文本   │                      │  生成 SubtaskSpec[]                  │
│  └───────┬───────┘                      └────────┬────────┘                     │
│          │                                       │                              │
│          │                                       ▼                              │
│          │              ┌────────────────────────────────────────────────┐      │
│          │              │              Actor Factory                      │      │
│          │              │                                                 │      │
│          │              │  选择优先级:                                    │      │
│          │              │  1. explicit_agent (用户指定) → 必须使用        │      │
│          │              │  2. capability matching → 自动选择              │      │
│          │              │     ├─ preset agents (research, sql)           │      │
│          │              │     └─ package agents (从 packages/ 加载)       │      │
│          │              │  3. generic fallback → Generic Actor           │      │
│          │              │                                                 │      │
│          │              │  Skill 任务: 注入 SKILL.md Instructions        │      │
│          │              └────────────────┬───────────────────────────────┘      │
│          │                               │                                       │
│          │                               ▼                                       │
│          │              ┌────────────────────────────────────────────────┐      │
│          │              │              Dynamic Actors                     │      │
│          │              │  ┌──────────────┐  ┌──────────────┐            │      │
│          │              │  │Research Actor│  │  SQL Actor   │            │      │
│          │              │  │ web_search   │  │ sql_query    │            │      │
│          │              │  │ tavily       │  │ db_connect   │            │      │
│          │              │  └──────┬───────┘  └──────┬───────┘            │      │
│          │              │         │                 │                    │      │
│          │              │  ┌──────────────────────────────────────────┐  │      │
│          │              │  │           Generic Actor                  │  │      │
│          │              │  │  sandbox | file_tools | activate_skill  │  │      │
│          │              │  └──────────────────────────────────────────┘  │      │
│          │              └────────────────┬───────────────────────────────┘      │
│          │                               │                                       │
│          │                               ▼                                       │
│          │              ┌────────────────────────────────────────────────┐      │
│          │              │           Progress Manager                      │      │
│          │              │                                                 │      │
│          │              │  • 跟踪 SubtaskSpec 状态 (pending → completed) │      │
│          │              │  • 管理依赖关系 (DAG 执行顺序)                  │      │
│          │              │  • 控制并行上限 (max 3 parallel)               │      │
│          │              │  • 发送 SSE 事件 (todos_updated, task_*)       │      │
│          │              └────────────────┬───────────────────────────────┘      │
│          │                               │                                       │
│          └───────────────────────────────┤                                       │
│                                          ▼                                       │
│                              ┌───────────────────┐                              │
│                              │   Stream Handler   │                              │
│                              │   (保持不变)        │                              │
│                              └─────────┬─────────┘                              │
│                                        │                                         │
│                                        ▼                                         │
│                              ┌───────────────────┐                              │
│                              │    SSE Events     │                              │
│                              │  text_delta       │                              │
│                              │  thinking         │                              │
│                              │  todos_updated    │                              │
│                              │  task_spawned     │                              │
│                              │  task_completed   │                              │
│                              │  tool_call_*      │                              │
│                              │  done             │                              │
│                              └─────────┬─────────┘                              │
│                                        │                                         │
│                                        ▼                                         │
│                                   Frontend                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据流简图

```
User Message
     │
     ▼
┌─────────────┐    IntentResult     ┌─────────────┐    SubtaskSpec[]    ┌─────────────┐
│   Intent    │ ─────────────────▶  │   Planner   │ ─────────────────▶  │   Actor     │
│  Analyzer   │   action/caps       │  (决定做什么) │   任务规格          │  Factory    │
└─────────────┘                     └─────────────┘                     └──────┬──────┘
                                           ▲                                   │
                                           │ TaskResult                        │ Actor
                                           │ (成功/失败)                        ▼
                                    ┌──────┴──────┐                     ┌─────────────┐
                                    │  Progress   │ ◀───────────────── │  Dynamic    │
                                    │  Manager    │   执行结果          │   Actor     │
                                    └─────────────┘                     └─────────────┘
```

---

## 3. 核心组件职责

| 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **IntentAnalyzer** | 意图识别 | User Message | IntentResult (action, capabilities) |
| **Planner** | 任务拆解、重规划 | IntentResult | SubtaskSpec[] |
| **Actor Factory** | Agent 选择、配置 | SubtaskSpec | Actor (graph, tools) |
| **Dynamic Actor** | 具体执行 | Actor + context | TaskResult |
| **Progress Manager** | 状态跟踪、SSE 发送 | TaskResult | SSE Events |

---

## 4. Action 类型与处理流程

### 4.1 Action 决策树

```
                         ┌─────────────────┐
                         │  User Message   │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ IntentAnalyzer  │
                         └────────┬────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           │                      │                      │
           ▼                      ▼                      ▼
   ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
   │ confidence    │      │ confidence    │      │ confidence    │
   │   >= 0.8      │      │  0.5 - 0.8    │      │   < 0.5       │
   └───────┬───────┘      └───────┬───────┘      └───────┬───────┘
           │                      │                      │
           ▼                      ▼                      ▼
   ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
   │ direct_reply  │      │   delegate    │      │    clarify    │
   │ 或 delegate   │      │   或 plan     │      │   追问用户     │
   └───────────────┘      └───────────────┘      └───────────────┘
```

### 4.2 四种 Action 处理流程

| Action | 触发条件 | 处理流程 | SSE 事件 |
|--------|----------|----------|----------|
| `direct_reply` | 简单问候、知识问答 | Planner 直接生成回复 | `text_delta` → `done` |
| `delegate` | 单一专业任务 | 创建 1 个 SubtaskSpec → Actor Factory → Actor 执行 | `thinking` → `task_spawned` → `tool_call_*` → `task_completed` → `text_delta` → `done` |
| `plan` | 复杂多步任务 | 创建 N 个 SubtaskSpec → 按 DAG 顺序执行 | `thinking` → `todos_updated` → `task_spawned` × N → ... → `done` |
| `clarify` | 意图不清 (confidence < 0.5) | 返回追问问题 | `text_delta` (追问) → `done` |

---

## 5. Agent 选择策略

### 5.1 选择优先级

```
┌─────────────────────────────────────────────────────────────────┐
│                     Actor Factory 选择逻辑                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SubtaskSpec                                                    │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 优先级 1: explicit_agent 有值?                          │   │
│  │           ├─ YES → 直接使用指定 Agent (不存在则报错)     │   │
│  │           └─ NO  → 继续                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 优先级 2: capabilities 匹配                              │   │
│  │           遍历 AGENT_REGISTRY (preset + package)         │   │
│  │           计算匹配分数 = |required ∩ agent.capabilities| │   │
│  │           ├─ 有匹配 → 选择最高分 (分数相同时 preset 优先) │   │
│  │           └─ 无匹配 → 继续                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 优先级 3: 默认 Generic Actor                             │   │
│  │           包含: sandbox, file_tools, activate_skill     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 预设 Agent 能力声明

| Agent | capabilities | source |
|-------|-------------|--------|
| research | `["web_search", "news_search", "academic_search"]` | preset |
| sql | `["database", "sql_query"]` | preset |
| generic | `["code_execution", "file_processing", "document_generation"]` | preset |

### 5.3 自定义 Agent 能力声明

```yaml
# packages/my-agent/AGENTS.md
---
name: my-agent
description: Custom agent for specific tasks
capabilities:
  - my_capability
  - another_capability
---
```

---

## 6. Intent Analyzer 分类器链

```
┌─────────────────────────────────────────────────────────────────┐
│                    IntentAnalyzer 分类器链                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User Message                                                   │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. RuleBasedClassifier (priority: 0)                    │   │
│  │    • 检测 [ROUTE_TO: agent] 显式路由                     │   │
│  │    • 检测 [SKILL: name] 技能请求                         │   │
│  │    • 匹配 → 返回 IntentResult (confidence: 1.0)         │   │
│  │    • 不匹配 → 传递给下一个                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 2. KeywordClassifier (priority: 10)                     │   │
│  │    • 关键词匹配: "搜索" → web_search                     │   │
│  │    • 关键词匹配: "查询数据库" → database                  │   │
│  │    • 高置信度匹配 → 返回 IntentResult                    │   │
│  │    • 低置信度 → 传递给下一个                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 3. LLMClassifier (priority: 100)                        │   │
│  │    • 深度语义分析                                        │   │
│  │    • 复杂意图识别                                        │   │
│  │    • 返回最终 IntentResult                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Progress Manager 状态机

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │ dispatch
                           ▼
                    ┌─────────────┐
             ┌──────│ in_progress │──────┐
             │      └──────┬──────┘      │
             │             │             │
        error│             │success      │timeout
             │             │             │
             ▼             ▼             ▼
      ┌──────────┐  ┌───────────┐  ┌───────────┐
      │  error   │  │ completed │  │ cancelled │
      └────┬─────┘  └───────────┘  └───────────┘
           │
           │ retry (< 3)
           ▼
    ┌─────────────┐
    │   pending   │ (重新排队)
    └─────────────┘
```

### 约束条件

- **并行上限**: 最多 3 个任务同时执行
- **重试上限**: 单个任务最多重试 3 次
- **依赖管理**: 按 DAG 顺序执行，前置任务完成后才执行后续

---

## 8. Skills 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Skills 集成架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  skills/ 或 packages/xxx/skills/                                │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Skill Loader                          │   │
│  │  解析 SKILL.md → 注册到 SKILL_REGISTRY                   │   │
│  │  如果 type=workflow → 额外注册到 WORKFLOW_SKILLS         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│         ┌───────────────┴───────────────┐                       │
│         │                               │                       │
│         ▼                               ▼                       │
│  ┌─────────────────┐           ┌─────────────────┐              │
│  │ SKILL_REGISTRY  │           │ WORKFLOW_SKILLS │              │
│  │ (所有 Skills)    │           │ (仅 Workflow)   │              │
│  └────────┬────────┘           └────────┬────────┘              │
│           │                             │                       │
│           │                             │                       │
│           ▼                             ▼                       │
│  ┌─────────────────┐           ┌─────────────────┐              │
│  │  Actor Factory  │           │    Planner      │              │
│  │  注入 Instructions         │  展开为多个      │              │
│  │  到 Actor prompt│           │  SubtaskSpec   │              │
│  └─────────────────┘           └─────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Skill 类型对比

| 类型 | 定义 | Planner 处理 | 示例 |
|------|------|-------------|------|
| **Atomic Skill** | 单 Agent 完成 | 创建 1 个 SubtaskSpec | pdf, docx |
| **Workflow Skill** | 多步骤，跨 Agent | 展开为 N 个 SubtaskSpec | research-report |

---

## 9. SSE 事件与前端 displayScenario 映射

```
┌─────────────────────────────────────────────────────────────────┐
│              SSE Events → displayScenario 映射                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  displayScenario 状态转换 (只升级不降级):                        │
│                                                                 │
│      quick ────────────▶ agent ────────────▶ planning          │
│        │                   │                    │               │
│        │ thinking          │ todos_updated      │               │
│        │ task_spawned      │                    │               │
│        ▼                   ▼                    ▼               │
│  ┌──────────┐       ┌──────────┐        ┌──────────┐           │
│  │ 仅显示    │       │ 显示      │        │ 显示      │           │
│  │ 消息内容  │       │ Thinking  │        │ TaskList │           │
│  │          │       │ + Tasks   │        │ (Todos   │           │
│  │          │       │           │        │ + Tasks) │           │
│  └──────────┘       └──────────┘        └──────────┘           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Action 与 displayScenario 对应:                                 │
│                                                                 │
│  ┌─────────────┬───────────────────┬─────────────────────────┐ │
│  │   Action    │ SSE Events        │ Final displayScenario   │ │
│  ├─────────────┼───────────────────┼─────────────────────────┤ │
│  │direct_reply │ text_delta        │ quick                   │ │
│  │delegate     │ thinking +        │ agent                   │ │
│  │             │ task_spawned      │                         │ │
│  │plan         │ thinking +        │ planning                │ │
│  │             │ todos_updated +   │                         │ │
│  │             │ task_spawned      │                         │ │
│  │clarify      │ text_delta        │ quick                   │ │
│  └─────────────┴───────────────────┴─────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. 文件结构

```
backend/
├── aime/                        # AIME 模块
│   ├── __init__.py
│   ├── planner.py               # AIME Dynamic Planner
│   ├── actor_factory.py         # Actor Factory
│   ├── progress_manager.py      # Progress Manager
│   ├── models.py                # SubtaskSpec, ProgressItem, etc.
│   ├── intent/                  # 意图识别模块
│   │   ├── __init__.py
│   │   ├── analyzer.py          # IntentAnalyzer
│   │   ├── models.py            # IntentResult, Action
│   │   └── classifiers/
│   │       ├── base.py          # ClassifierBase
│   │       ├── rule_based.py
│   │       ├── keyword_based.py
│   │       └── llm_based.py
│   └── actors/
│       ├── __init__.py
│       └── generic.py           # Generic Actor
├── agents/
│   ├── research.py              # 添加 capabilities
│   ├── sql.py                   # 添加 capabilities
│   ├── general.py               # 废弃
│   └── loader.py                # 解析 capabilities
├── skills/
│   ├── registry.py              # 添加 WORKFLOW_SKILLS
│   └── loader.py                # 解析 type/steps
├── registry.py                  # AgentEntry 扩展
├── supervisor.py                # 重写为调用 Planner
├── stream_handler.py            # 保持不变
└── main.py                      # 更新 import
```

---

## 11. 与现有架构对比

### 替换前 (Current)

```
User Request → Supervisor (路由)
                   ├─ Direct Response
                   ├─ → Research Agent
                   ├─ → SQL Agent
                   └─ → General Agent (编排) → [Research, SQL, ...]
```

### 替换后 (AIME)

```
User Request → AIME Planner (意图识别 + 动态规划)
                   │
                   ├─ [简单] Direct Response
                   │
                   ├─ [专业] → Actor Factory → Dynamic Actor (Research/SQL)
                   │                              ↓
                   │                         Progress Manager
                   │
                   └─ [复杂] → Task Decomposition
                                   ├─ Subtask 1 → Actor Factory → Actor
                                   ├─ Subtask 2 → Actor Factory → Actor
                                   └─ ...
                                         ↓
                                    Progress Manager
```

---

## 参考文档

- [spec.md](./spec.md) - 完整功能规格
- [plan.md](./plan.md) - 实现计划
- [data-model.md](./data-model.md) - 数据结构定义
- [contracts/](./contracts/) - 接口契约
- [research.md](./research.md) - 技术研究
- [quickstart.md](./quickstart.md) - 开发者指南
