# Research: AIME Agent Core & Supervisor Optimization

**Branch**: `005-aime-supervisor` | **Date**: 2026-02-15 | **Plan**: [plan.md](./plan.md)

## Overview

本文档记录 AIME 架构实现前的技术研究，解答 plan.md 中提出的关键问题。

---

## 0.1 LangGraph StateGraph 集成模式

### Q1: Planner 作为 StateGraph 节点还是独立组件？

**分析现有实现** (`supervisor.py`):
- Supervisor 使用 `langchain.agents.create_agent()` 创建一个 agent 节点
- 通过 `route` tool 返回 `Command(goto=...)` 跳转到专业 Agent 节点
- 所有专业 Agent 作为 StateGraph 的独立节点

**推荐方案**: **Planner 作为 StateGraph 节点**

理由：
1. 保持与现有架构的一致性
2. 可以复用 LangGraph 的状态管理和消息传递
3. Command 机制已证明可行（route tool 使用）
4. stream_handler.py 已经适配了多节点流式输出

**实现方式**:
```python
# 新 supervisor.py
builder = StateGraph(MessagesState)

# Planner 节点 - 替代原有 supervisor 节点
builder.add_node("planner", planner_agent)

# 专业 Agent 节点 - 保持不变
for name, entry in AGENT_REGISTRY.items():
    builder.add_node(name, entry.graph)
    builder.add_edge(name, END)

# Generic Actor 节点 - 新增
builder.add_node("generic", generic_actor)
builder.add_edge("generic", END)

builder.add_edge(START, "planner")
```

### Q2: 子任务并行执行如何映射到 StateGraph 分支？

**现有机制**:
- `create_deep_agent()` 的 `subagents` 参数支持 `task()` 工具调用
- SubAgentMiddleware 处理子任务执行，支持并行调用
- stream_handler.py 通过 `task_spawned`/`task_completed` 事件追踪

**推荐方案**: **复用 SubAgentMiddleware 并行执行机制**

理由：
1. SubAgentMiddleware 已实现并行子任务执行
2. stream_handler.py 已适配 task 生命周期事件
3. 无需修改 LangGraph 图结构

**实现细节**:
- Planner 创建 SubtaskSpec[] 后，按 DAG 顺序分发
- 无依赖的子任务可以并行执行（利用 SubAgentMiddleware）
- 有依赖的子任务等待前置完成后再分发
- 最大并行数 = 3（通过 semaphore 控制）

### Q3: 动态重规划如何实现状态回溯？

**分析需求**:
- 子任务失败时，Planner 需要调整后续计划
- 可能需要创建替代任务或修改依赖

**推荐方案**: **Planner 内部状态管理，无需 StateGraph 回溯**

理由：
1. Planner 维护 ProgressList 状态
2. 失败时 Planner 重新规划，生成新的 SubtaskSpec
3. 不需要 LangGraph 级别的状态回溯
4. 保持简单，避免复杂的图操作

**实现细节**:
```python
class AIMEPlanner:
    async def handle_task_result(self, task_id: str, result: TaskResult):
        if result.status == "error" and self.retry_count < 3:
            # 重规划：创建替代任务或修改策略
            new_subtasks = await self._replan(task_id, result.error)
            self.progress_list.add_subtasks(new_subtasks)
        else:
            # 正常流程：更新进度，检查下一个任务
            self.progress_list.mark_completed(task_id)
            await self._dispatch_next_tasks()
```

---

## 0.2 deepagents 中间件栈

### Q1: Generic Actor 是否使用 create_deep_agent()？

**分析现有实现** (`general.py`):
- 使用 `create_deep_agent()` 创建，获得完整中间件支持
- 包含 TodoListMiddleware（write_todos）和 SubAgentMiddleware（task）
- 支持工具调用、子 Agent 委派

**推荐方案**: **是，Generic Actor 使用 create_deep_agent()**

理由：
1. 复用现有中间件栈（thinking、todos、子任务）
2. 保持与 Research/SQL Agent 的一致性
3. stream_handler.py 已适配 deepagents 输出格式

**实现细节**:
```python
# backend/aime/actors/generic.py
def build_generic_actor():
    return create_deep_agent(
        model=get_model("generic"),
        tools=[
            execute_python,
            execute_python_with_file,
            read_uploaded_file,
            activate_skill,
        ],
        # 不包含 subagents - Generic Actor 不委派子任务
        system_prompt=GENERIC_ACTOR_PROMPT,
        name="generic",
    )
```

### Q2: Skill Instructions 注入点在中间件栈的哪一层？

**分析需求**:
- Skill 任务需要将 Instructions 注入 Actor prompt
- Actor Factory 负责 Actor 配置

**推荐方案**: **在 Actor 实例化时注入，不修改中间件栈**

理由：
1. Skill Instructions 是静态配置，不需要运行时中间件
2. 直接修改 system_prompt 最简单
3. 保持中间件栈不变，减少复杂性

**实现细节**:
```python
# backend/aime/actor_factory.py
class ActorFactory:
    def create_actor(self, spec: SubtaskSpec) -> Actor:
        base_prompt = self._get_base_prompt(spec)

        # 如果是 Skill 任务，注入 Instructions
        if spec.skill_name:
            skill = SKILL_REGISTRY.get(spec.skill_name)
            if skill:
                instructions = skill.load_instructions()
                # 注入 step 上下文（如果是 Workflow Skill）
                if spec.skill_step_id:
                    instructions += f"\n\n## Current Step: {spec.skill_step_id}"
                base_prompt = f"{base_prompt}\n\n## Skill Instructions\n{instructions}"

        return create_deep_agent(
            model=get_model("actor"),
            tools=self._select_tools(spec),
            system_prompt=base_prompt,
        )
```

### Q3: Progress 上报是否需要新的中间件？

**分析现有机制**:
- TodoListMiddleware 通过 `write_todos` tool 更新任务列表
- stream_handler.py 监听 `todos` 状态变化，发送 `todos_updated` 事件

**推荐方案**: **不需要新中间件，复用现有 todos 机制**

理由：
1. AIME 的 Progress Management 等同于现有 todos 功能
2. stream_handler.py 已经处理 `todos_updated` 事件
3. 前端 TaskList 组件已支持渲染

**实现细节**:
- Planner 使用现有 `write_todos` tool 更新 Progress List
- 或者直接修改 State 中的 `todos` 字段（StateGraph 更新流会触发事件）

---

## 0.3 现有 SSE 事件流分析

### Q1: todos_updated 事件的 payload 格式要求？

**现有实现** (`stream_handler.py:200-224`):
```python
yield _format_sse(
    "todos_updated",
    {
        "todos": [
            {
                "content": t.get("content", ""),
                "status": t.get("status", "pending"),
            }
            for t in todos
            if isinstance(t, dict)
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    },
    event_counter,
)
```

**格式要求**:
```typescript
interface TodosUpdatedEvent {
  todos: Array<{
    content: string;    // 任务描述
    status: "pending" | "in_progress" | "completed";
  }>;
  timestamp: string;    // ISO 8601 格式
}
```

**AIME 兼容性**: ✅ 直接复用，SubtaskSpec.description 映射到 content

### Q2: task_spawned/task_completed 事件的触发时机？

**现有实现**:

**task_spawned** (`stream_handler.py:408-415`, `420-433`):
- 触发时机：检测到 `route` tool 或 `task` tool 调用
- 数据来源：tool_call 的 args (agent_name, task_description/prompt)

**task_completed** (`stream_handler.py:254-266`, `269-281`):
- 触发时机：收到对应 tool 的 ToolMessage
- 状态判断：ToolMessage.status == "success" or "error"

**AIME 适配**:
- Planner 分发子任务时发送 `task_spawned`
- Actor 完成执行时发送 `task_completed`
- 需要确保 SubtaskSpec.id 与 SSE task_id 一致

### Q3: displayScenario 状态机的完整转换规则？

**前端实现** (`useChat.ts`):

```typescript
type DisplayScenario = "quick" | "agent" | "planning";

// 状态转换规则（只升级不降级）
const shouldUpgrade = (current: DisplayScenario, next: DisplayScenario) => {
  const order = { quick: 0, agent: 1, planning: 2 };
  return order[next] > order[current];
};

// 触发条件
// quick → agent: 收到 task_spawned 或 thinking 事件
// agent → planning: 收到 todos_updated 事件
```

**AIME Action 映射**:

| Action | 触发的 SSE 事件 | displayScenario |
|--------|----------------|-----------------|
| direct_reply | text_delta | quick (保持) |
| delegate | thinking + task_spawned | quick → agent |
| plan | thinking + todos_updated + task_spawned | quick → planning |
| clarify | text_delta | quick (保持) |

---

## 技术决策总结

| 问题 | 决策 | 理由 |
|------|------|------|
| Planner 集成方式 | StateGraph 节点 | 保持架构一致性，复用 Command 机制 |
| 并行执行机制 | 复用 SubAgentMiddleware | 已有实现，无需重造 |
| 重规划机制 | Planner 内部状态 | 简单有效，避免图操作 |
| Generic Actor 创建 | create_deep_agent() | 复用中间件和 SSE 适配 |
| Skill 注入方式 | system_prompt 拼接 | 最简单，无需改中间件 |
| Progress 上报 | 复用 todos 机制 | 现有 SSE 和前端已支持 |

---

## 待确认事项

1. **LLM 调用策略**: IntentAnalyzer 的 LLMClassifier 使用哪个模型？
   - 建议：使用 "supervisor" 模型配置（速度优先）

2. **capabilities 标准化**: 是否需要预定义能力列表？
   - 建议：先硬编码常用能力，后续支持自定义

3. **错误恢复策略**: 子任务失败后的具体处理逻辑？
   - 建议：v1 简单重试，v2 再实现复杂重规划

---

## 下一步

1. 创建 `data-model.md` - 定义核心数据结构
2. 创建 `contracts/` - 定义模块接口
3. 创建 `quickstart.md` - 开发者指南
