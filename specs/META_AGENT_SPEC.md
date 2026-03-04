# META_AGENT_SPEC.md — Skill Auto-Optimization System

> **本文档是 Claude Code 的操作规范。**
> 当被要求实现 "Meta-Agent" 或 "Skill 自动优化" 时，请严格按照本文档执行。

---

## 1. 项目背景

### 1.1 现有系统概述

SunnyAgent 是一个基于 **LangGraph Supervisor + Deep Agent** 架构的多 Agent 系统：

- **语言**：Python（后端）+ TypeScript（前端）
- **架构**：Supervisor 路由 → 专业 Deep Agent（research / sql / general / package agents）
- **可扩展性**：支持通过 `packages/` 目录自动加载 Agent，每个 Package Agent 包含 `AGENTS.md`（系统提示词）和 `skills/` 目录
- **技能系统**：`backend/skills/` 下的 registry + loader，以及 `skills/` 顶层目录存放技能定义（SKILL.md 格式）
- **监控**：已集成 Langfuse，记录所有 Agent 对话的 traces 和 scores
- **代码执行**：Docker 沙箱环境执行 Python 代码

### 1.2 目标

构建一个 **Meta-Agent System**（元智能体系统），它能够：

1. 读取用户提供的**测试数据集**（输入 + 期望输出）
2. 分析当前 Skills 在测试集上的表现
3. **自动生成、修改、优化 Skills**（包括 SKILL.md 和 Package Agent 的 skills）
4. 反复迭代直到达到目标分数或最大迭代次数
5. 全程通过 Langfuse 记录优化过程

### 1.3 操作环境

- **开发工具**：VSCode + Claude Code
- **Claude Code 的角色**：作为 Meta-Agent 的 Orchestrator，直接在仓库中读写文件、执行命令、驱动优化循环

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code（Meta-Agent Orchestrator）                      │
│  - 读取本文档，理解优化规范                                    │
│  - 驱动整个 generate → evaluate → analyze → iterate 循环      │
│  - 直接操作仓库文件系统                                       │
└──────────┬──────────────────┬───────────────────┬───────────┘
           │                  │                   │
           ▼                  ▼                   ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │   Skill       │   │  Evaluator   │   │  Analyzer    │
   │   Generator   │   │  Module      │   │  Module      │
   │              │   │              │   │              │
   │ 生成/修改     │   │ 调用现有框架  │   │ 分析失败案例  │
   │ SKILL.md     │   │ 跑测试集     │   │ 输出改进建议  │
   │ AGENTS.md    │   │ 收集结果     │   │              │
   └──────────────┘   └──────────────┘   └──────────────┘
           │                  │                   │
           ▼                  ▼                   ▼
   ┌─────────────────────────────────────────────────────┐
   │                  SunnyAgent 现有框架                  │
   │  ├── backend/skills/ (registry + loader)             │
   │  ├── packages/*/AGENTS.md + skills/*/SKILL.md        │
   │  ├── skills/ (顶层技能目录)                           │
   │  └── Langfuse (traces, scores, datasets)             │
   └─────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 实现方式 |
|------|------|---------|
| **Orchestrator** | 管理迭代循环、判断收敛/终止、协调各模块 | Claude Code 自身（读取本文档后按流程执行） |
| **Skill Generator** | 生成新 Skill 或修改现有 Skill | Claude Code 直接写入文件（遵循 Skill Schema） |
| **Evaluator** | 用测试集评估当前 Skill 表现 | 调用 `meta_agent/eval_runner.py`（需创建） |
| **Analyzer** | 对失败 case 做根因分析，输出改进建议 | Claude Code 分析评估结果后推理 |

---

## 3. 需要创建的文件

### 3.1 目录结构

在仓库中创建以下结构：

```
meta_agent/                          # Meta-Agent 系统根目录
├── README.md                        # Meta-Agent 使用说明
├── config.yaml                      # 优化配置（目标分数、最大迭代等）
├── eval_runner.py                   # 评估入口脚本
├── eval_metrics.py                  # 评估指标计算
├── langfuse_integration.py          # Langfuse 查询 & 写入工具
├── datasets/                        # 测试数据集目录
│   ├── README.md                    # 数据集格式说明
│   └── example_dataset.jsonl        # 示例数据集
├── results/                         # 评估结果输出目录
│   └── .gitkeep
└── history/                         # 优化历史记录
    └── .gitkeep
```

### 3.2 配置文件 — `meta_agent/config.yaml`

```yaml
# Meta-Agent 优化配置
optimization:
  target_score: 0.90            # 目标通过率
  max_iterations: 10            # 最大迭代轮数
  regression_threshold: 0.05    # 回归检测阈值：新版本分数下降超过此值则回滚
  patience: 3                   # 连续 N 轮无提升则提前终止

evaluation:
  dataset_path: "meta_agent/datasets/"  # 测试数据集目录
  results_path: "meta_agent/results/"   # 结果输出目录
  timeout_seconds: 60                   # 单个 case 超时时间

  # 评估维度权重
  weights:
    correctness: 0.5            # 输出正确性
    skill_trigger: 0.2          # Skill 是否正确触发
    response_quality: 0.2       # 回复质量（LLM-as-judge）
    efficiency: 0.1             # 执行效率（步骤数/token 消耗）

langfuse:
  enabled: true
  session_prefix: "meta-agent-opt"     # Langfuse session 命名前缀
  log_every_iteration: true

strategy:
  # 每次迭代最多修改的 Skill 数量（便于归因）
  max_skills_per_iteration: 1
  # 是否允许创建全新 Skill
  allow_new_skills: true
  # 是否在修改前 git commit（便于回滚）
  git_commit_per_iteration: true
```

### 3.3 测试数据集格式 — `meta_agent/datasets/README.md`

每个数据集是一个 `.jsonl` 文件，每行一个 JSON 对象：

```jsonl
{"case_id": "001", "input": "用户消息内容", "expected_agent": "research", "expected_skill": "web-search", "expected_output_contains": ["关键词1", "关键词2"], "expected_behavior": "应调用 Tavily 搜索并返回近期 AI 新闻摘要", "tags": ["search", "news"]}
{"case_id": "002", "input": "数据库中有多少巴西客户？", "expected_agent": "sql", "expected_skill": null, "expected_output_contains": ["5", "巴西"], "expected_behavior": "生成正确 SQL 查询并返回数量", "tags": ["sql", "chinook"]}
{"case_id": "003", "input": "/content-writer 写一篇关于 AI 的博客", "expected_agent": "content-writer", "expected_skill": "blog-post", "expected_output_contains": [], "expected_behavior": "使用 blog-post skill 生成结构完整的博客文章", "tags": ["package-agent", "content"]}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `case_id` | string | 是 | 唯一标识 |
| `input` | string | 是 | 用户输入消息 |
| `expected_agent` | string | 否 | 期望路由到的 Agent |
| `expected_skill` | string \| null | 否 | 期望触发的 Skill |
| `expected_output_contains` | string[] | 否 | 输出中应包含的关键词 |
| `expected_behavior` | string | 是 | 人类可读的期望行为描述（供 LLM-as-judge 使用） |
| `tags` | string[] | 否 | 标签，用于分类分析 |
| `files` | string[] | 否 | 需要附带的文件路径（如有上传文件场景） |

### 3.4 评估入口 — `meta_agent/eval_runner.py`

此脚本是整个优化循环的核心闭环。

**功能要求**：

1. 读取 `datasets/` 目录下指定的 `.jsonl` 数据集
2. 对每个 case，通过 SunnyAgent 的 API 接口（`POST /api/chat`）发送请求
3. 收集响应结果（完整的 SSE 流）
4. 将实际输出与期望输出对比，计算各维度分数
5. 输出结构化的评估结果到 `results/` 目录
6. 将评估数据写入 Langfuse

**输出格式**（`results/eval_{timestamp}.json`）：

```json
{
  "meta": {
    "timestamp": "2025-06-01T10:30:00Z",
    "dataset": "test_v1.jsonl",
    "total_cases": 50,
    "iteration": 3,
    "skills_version": "v3"
  },
  "summary": {
    "overall_score": 0.78,
    "scores_by_dimension": {
      "correctness": 0.82,
      "skill_trigger": 0.75,
      "response_quality": 0.80,
      "efficiency": 0.70
    },
    "pass_rate": 0.76,
    "passed": 38,
    "failed": 12
  },
  "failed_cases": [
    {
      "case_id": "test_023",
      "input": "...",
      "expected_agent": "research",
      "actual_agent": "general",
      "expected_skill": "web-search",
      "actual_skill": null,
      "expected_behavior": "...",
      "actual_output": "...",
      "scores": {
        "correctness": 0.3,
        "skill_trigger": 0.0,
        "response_quality": 0.5,
        "efficiency": 0.6
      },
      "failure_category": "skill_not_triggered",
      "langfuse_trace_url": "https://langfuse.xxx/trace/abc123"
    }
  ],
  "passed_cases_summary": [
    {
      "case_id": "test_001",
      "scores": { "correctness": 1.0, "skill_trigger": 1.0, "response_quality": 0.9, "efficiency": 0.8 }
    }
  ]
}
```

**失败分类**（`failure_category`）：

| 分类 | 含义 | 典型修复方向 |
|------|------|-------------|
| `skill_not_triggered` | Skill 应该触发但没有 | 优化 Skill 的 trigger/description |
| `wrong_skill_triggered` | 触发了错误的 Skill | 调整 Skill 的 description 区分度 |
| `wrong_agent_routed` | 路由到了错误的 Agent | 调整 Supervisor prompt 或 Agent description |
| `output_incorrect` | Agent/Skill 触发正确但输出错误 | 优化 Skill 的 prompt_template |
| `output_incomplete` | 输出不完整 | 补充 Skill 的 instructions |
| `execution_error` | 执行过程出错 | 检查 Skill 依赖或代码 |
| `timeout` | 超时 | 优化执行效率 |

**调用方式**：

```bash
# 跑完整测试集
cd <project_root>
python meta_agent/eval_runner.py --dataset meta_agent/datasets/test_v1.jsonl --output meta_agent/results/

# 跑单个 case（调试用）
python meta_agent/eval_runner.py --dataset meta_agent/datasets/test_v1.jsonl --case-id test_023

# 跑指定 tag 的 case 子集
python meta_agent/eval_runner.py --dataset meta_agent/datasets/test_v1.jsonl --tags search,content
```

---

## 4. Skill Schema 规范

### 4.1 Package Agent Skill（`packages/*/skills/*/SKILL.md`）

这是 SunnyAgent 中 Package Agent 使用的 Skill 格式。Claude Code 在生成或修改 Skill 时必须遵循此格式：

```markdown
# {Skill 名称}

{Skill 的详细指令内容，告诉 Agent 在执行此 Skill 时应该怎么做}

## 输入要求
{描述此 Skill 期望的输入格式和内容}

## 输出要求
{描述此 Skill 应该产出的输出格式和内容}

## 执行步骤
1. {步骤1}
2. {步骤2}
...

## 示例
{给出 1-3 个输入输出示例}

## 注意事项
- {约束条件}
- {边界情况处理}
```

### 4.2 Package Agent 定义（`packages/*/AGENTS.md`）

每个 Package Agent 的系统提示词文件：

```markdown
# {Agent 名称}

{Agent 的角色描述和核心能力}

## 职责范围
{明确此 Agent 负责处理什么类型的任务}

## 可用 Skills
{列出此 Agent 下的所有 Skills 及其用途}

## 工作流程
{描述 Agent 处理任务的标准流程}

## 约束
{不应该做什么，边界在哪里}
```

### 4.3 顶层 Skill（`skills/*/SKILL.md`）

遵循标准 Agent Skills 规范（YAML frontmatter + Markdown body）：

```markdown
---
name: skill-name
description: 清晰描述此 Skill 的用途和触发时机
---

# Skill 名称

{详细指令内容}
```

### 4.4 Skill 注册（`backend/skills/`）

`backend/skills/registry.py` 中的 `SKILL_REGISTRY` 管理所有 Skill 的注册。新 Skill 创建后需确保能被 `backend/skills/loader.py` 正确加载。

**创建新 Skill 的 Checklist**：

1. ✅ 创建 `skills/<name>/SKILL.md` 或 `packages/<agent>/skills/<name>/SKILL.md`
2. ✅ 确认 SKILL.md 遵循上述格式
3. ✅ 确认 loader 能扫描到（检查目录位置是否正确）
4. ✅ 通过 `GET /api/skills` 验证 Skill 已被注册
5. ✅ 运行测试集验证 Skill 效果

---

## 5. 优化循环规范

### 5.1 完整流程

```
Claude Code 执行以下步骤：

STEP 0: 准备
  - 读取本文档（META_AGENT_SPEC.md）
  - 读取 meta_agent/config.yaml
  - 确认 SunnyAgent 服务正在运行（检查 localhost:8008）
  - 确认测试数据集存在且格式正确

STEP 1: Baseline 评估
  - 运行: python meta_agent/eval_runner.py --dataset <指定数据集>
  - 记录 baseline 分数
  - git commit: "meta-agent: baseline evaluation - score {X}"

STEP 2: 分析失败案例（Analyzer）
  - 读取 results/eval_{latest}.json
  - 按 failure_category 分组统计
  - 确定优先修复方向（按以下优先级）：
    1. skill_not_triggered（最多的先修）
    2. wrong_skill_triggered
    3. wrong_agent_routed
    4. output_incorrect
    5. output_incomplete
    6. execution_error / timeout

STEP 3: 生成/修改 Skill（Generator）
  - 根据分析结果，每次只改一个 Skill（便于归因）
  - 修改前先备份：复制到 history/ 目录
  - 修改内容记录在 commit message 中
  - git commit: "meta-agent: iter-{N} - optimize {skill_name} for {reason}"

STEP 4: 重新评估
  - 运行 eval_runner.py
  - 对比上一轮分数

STEP 5: 决策
  - IF 分数 >= target_score:
      → 输出 "✅ 优化完成！" + 最终报告
      → 结束
  - IF 分数下降超过 regression_threshold:
      → 回滚到上一版本（git revert）
      → 换一个修复策略
      → 回到 STEP 3
  - IF 连续 patience 轮无提升:
      → 输出 "⚠️ 优化收敛，建议人工介入" + 当前最佳结果
      → 结束
  - IF 达到 max_iterations:
      → 输出 "⚠️ 达到最大迭代次数" + 当前最佳结果
      → 结束
  - ELSE:
      → 回到 STEP 2 继续
```

### 5.2 每轮迭代的输出

每轮迭代后，Claude Code 应输出以下摘要：

```
═══════════════════════════════════════════════════
  Meta-Agent 迭代报告 — 第 {N} 轮
═══════════════════════════════════════════════════
  数据集: {dataset_name}
  分数:   {current_score} (上一轮: {prev_score}, 变化: {delta})
  通过:   {passed}/{total}
  
  本轮操作:
    - 修改: {skill_name} — {修改说明}
  
  失败分布:
    - skill_not_triggered:    {count}
    - wrong_skill_triggered:  {count}
    - output_incorrect:       {count}
    - ...
  
  下一步: {继续优化 / 回滚 / 结束}
═══════════════════════════════════════════════════
```

### 5.3 回归检测

每次 Skill 修改后，不仅检查失败 case 是否修复，还要检查：

- **之前通过的 case 是否仍然通过**（回归检测）
- 如果出现回归，记录具体哪些 case 被影响
- 回归 case 数量 > 修复 case 数量时，自动回滚

---

## 6. 与 Langfuse 的集成

### 6.1 数据写入

每次评估运行写入 Langfuse 的数据：

| 数据类型 | 内容 | 用途 |
|---------|------|------|
| **Trace** | 每个 test case 的完整执行记录 | 追溯问题 |
| **Score** | correctness, skill_trigger, response_quality, efficiency | 量化表现 |
| **Session** | 以 `meta-agent-opt-{iteration}` 为 session 名 | 按迭代分组 |
| **Dataset** | 测试数据集版本 | 支持 A/B 对比 |

### 6.2 数据读取

从 Langfuse 读取的数据：

- 历史 traces 中的失败模式（用于丰富 Analyzer 的分析）
- 用户真实对话中的低分 case（用于扩充测试数据集）
- 各 Skill 的历史表现趋势

### 6.3 Langfuse 查询脚本

`meta_agent/langfuse_integration.py` 应提供以下功能：

```python
# 查询最近一次评估的结果
get_latest_eval_results(session_prefix="meta-agent-opt") -> dict

# 查询某个 Skill 的历史表现
get_skill_performance_history(skill_name: str, limit: int = 20) -> list

# 从生产 traces 中提取低分 case 作为新的测试数据
extract_hard_cases(min_date: str, max_score: float = 0.5) -> list

# 将评估结果写入 Langfuse
log_evaluation(iteration: int, results: dict) -> None
```

---

## 7. 优化策略库

### 7.1 针对不同失败类型的修复策略

**`skill_not_triggered`**：
- 扩展 Skill 的 description，增加更多触发关键词
- 在 SKILL.md 开头增加 "何时使用此 Skill" 的明确说明
- 检查 Skill 的 name 是否足够直观

**`wrong_skill_triggered`**：
- 增强 Skill description 的区分度，明确 "不应该处理" 的场景
- 添加 negative examples（反例）
- 考虑拆分过于宽泛的 Skill

**`wrong_agent_routed`**：
- 检查 Package Agent 的 AGENTS.md，调整职责描述
- 检查 Supervisor 的 routing 逻辑
- 在 AGENTS.md 中添加 "不处理" 的声明

**`output_incorrect`**：
- 优化 SKILL.md 中的 prompt_template / 执行步骤
- 增加更多 examples
- 添加输出格式约束

**`output_incomplete`**：
- 在 SKILL.md 中增加 completeness checklist
- 添加 "回复必须包含" 的约束

**`execution_error`**：
- 检查 Skill 依赖的工具是否可用
- 添加错误处理指令
- 简化执行步骤

### 7.2 创建新 Skill 的判断标准

当以下条件满足时，应创建新 Skill 而非修改现有 Skill：

1. 测试集中有一类 case 不属于任何现有 Skill 的职责范围
2. 现有 Skill 试图覆盖但失败率 > 50%，且失败原因是职责不匹配
3. 某个 Skill 过于宽泛（覆盖 3 种以上不同类型的任务）

---

## 8. 约束与安全

### 8.1 操作约束

- **每次只改一个 Skill**：确保能归因到具体修改
- **每次修改后跑完整测试集**：确保无回归
- **保留所有版本**：通过 git commit 追踪每轮修改
- **不修改框架核心代码**：只修改 SKILL.md、AGENTS.md 和测试相关文件
- **不修改 Supervisor 路由逻辑**：除非明确指示

### 8.2 不应修改的文件

以下文件 Claude Code **不应修改**（除非用户明确要求）：

```
backend/supervisor.py           # Supervisor 路由逻辑
backend/agents/*.py             # 代码 Agent 定义
backend/tools/*.py              # 工具实现
backend/main.py                 # API 入口
frontend/**                     # 前端代码
docker-compose.yml              # 基础设施配置
```

### 8.3 可以修改的文件

```
skills/**/*.md                  # 顶层技能定义
packages/*/AGENTS.md            # Package Agent 系统提示词
packages/*/skills/**/*.md       # Package Agent 技能定义
meta_agent/**                   # Meta-Agent 系统自身
backend/skills/registry.py      # 技能注册表（新增注册项时）
```

---

## 9. 快速启动指南

### 9.1 首次运行

```bash
# 1. 确保 SunnyAgent 正在运行
./scripts/sunnyagent.sh status
# 如果没运行：
./scripts/sunnyagent.sh start

# 2. 准备测试数据集
# 将测试数据放到 meta_agent/datasets/test_v1.jsonl

# 3. 启动优化（在 Claude Code 中）
# 对 Claude Code 说：
# "读取 META_AGENT_SPEC.md，然后用 meta_agent/datasets/test_v1.jsonl 数据集开始优化 Skills，目标分数 0.9"
```

### 9.2 Claude Code 启动命令示例

```
@claude 请按照 META_AGENT_SPEC.md 执行 Skill 优化：
- 数据集：meta_agent/datasets/test_v1.jsonl
- 目标分数：0.9
- 最大迭代：10 轮
先运行 baseline 评估，然后开始迭代优化。
```

```
@claude 继续上次的优化任务：
- 读取 meta_agent/results/ 下最新的评估结果
- 分析失败 case
- 执行下一轮迭代
```

```
@claude 基于 Langfuse 中最近 7 天的低分 traces，生成一个新的测试数据集到 meta_agent/datasets/hard_cases.jsonl
```

---

## 10. 优化完成的输出

当优化完成（达标或终止）时，Claude Code 应生成以下报告：

```
meta_agent/results/final_report_{timestamp}.md
```

内容包含：

1. **优化摘要**：起始分数 → 最终分数，总迭代次数
2. **Skills 变更清单**：每个被修改/创建的 Skill 及变更内容
3. **关键发现**：优化过程中发现的模式和洞察
4. **剩余问题**：仍未通过的 case 及原因分析
5. **建议**：后续人工可以做的改进

---

## 附录 A：现有仓库关键路径速查

```
sunnyagent/
├── backend/
│   ├── main.py                 # FastAPI 入口，端口 8008
│   ├── supervisor.py           # LangGraph Supervisor 路由器
│   ├── registry.py             # Agent 注册系统
│   ├── agents/
│   │   ├── research.py         # Research Agent（Tavily 搜索）
│   │   ├── sql.py              # SQL Agent（Chinook DB）
│   │   ├── general.py          # General 兜底 Agent
│   │   └── loader.py           # Package Agent 加载器（扫描 packages/）
│   ├── skills/
│   │   ├── registry.py         # SKILL_REGISTRY
│   │   └── loader.py           # Skill 加载器（从 skills/ 加载）
│   └── tools/
│       ├── sandbox.py          # Docker 沙箱代码执行
│       └── file_tools.py       # 文件读取工具
├── packages/                   # 可扩展 Agent 包
│   └── content-writer/         # 示例 Package Agent
│       ├── AGENTS.md           # Agent 系统提示词
│       └── skills/
│           ├── blog-post/SKILL.md
│           └── social-media/SKILL.md
├── skills/                     # 顶层技能目录
│   ├── anthropic/              # Anthropic 官方技能（git submodule）
│   └── custom/                 # 自定义技能
├── meta_agent/                 # ← 需要创建
├── CLAUDE.md                   # Claude Code 项目级指令
└── META_AGENT_SPEC.md          # ← 本文档
```

## 附录 B：API 接口速查

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回 SSE 流 |
| `/api/threads` | POST | 创建新会话线程 |
| `/api/threads/{id}/history` | GET | 获取会话历史 |
| `/api/agents` | GET | 列出所有 Agent |
| `/api/skills` | GET | 列出所有 Skill |
| `/api/skills/{name}` | GET | 获取 Skill 详情 |
| `/api/files/upload` | POST | 上传文件 |

**ChatRequest 字段**：

```json
{
  "thread_id": "uuid",
  "message": "用户消息",
  "agent": "research",        // 可选，跳过 Supervisor 直接路由
  "skill": "web-search",      // 可选，注入技能指令
  "file_ids": ["uuid"]        // 可选，关联文件
}
```
