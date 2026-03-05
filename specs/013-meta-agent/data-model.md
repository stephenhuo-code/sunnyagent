# Data Model: Meta-Agent Plugin Optimization System

**Feature**: 013-meta-agent
**Date**: 2026-03-04
**Status**: Complete

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Data Model Overview                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │  TestDataset    │────▶│    TestCase     │     │   TestFile      │   │
│  │  (数据集)        │ 1:N │  (测试用例)      │◀───▶│  (测试文件)      │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│          │                       │                                       │
│          │ sync                  │ execute                              │
│          ▼                       ▼                                       │
│  ┌─────────────────┐     ┌─────────────────┐                           │
│  │ LangfuseDataset │     │ EvaluationResult│                           │
│  │  (Langfuse)     │     │  (评估结果)      │                           │
│  └─────────────────┘     └─────────────────┘                           │
│                                  │                                       │
│                                  │ contains                             │
│                                  ▼                                       │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │OptimizationConfig│    │   FailedCase    │     │  IterationReport│   │
│  │  (优化配置)      │     │  (失败详情)      │     │  (迭代报告)      │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│          │                                                               │
│          │ tracks                                                        │
│          ▼                                                               │
│  ┌─────────────────┐     ┌─────────────────┐                           │
│  │  Checkpoint     │     │  FileVersion    │                           │
│  │  (检查点)        │     │  (文件版本)      │                           │
│  └─────────────────┘     └─────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Entities

### TestDataset

测试数据集，包含多个测试用例。

```python
class TestDataset(BaseModel):
    """测试数据集"""

    # Identity
    name: str                           # 数据集名称，如 "qc-plugin-v1"
    version: str                        # 版本号，自动递增 "v1", "v2"
    plugin_name: str                    # 目标 Plugin 名称

    # Content
    cases: list[TestCase]               # 测试用例列表

    # Metadata
    created_at: datetime
    updated_at: datetime
    source_file: str                    # 原始文件路径（CSV/JSONL）

    # Langfuse sync
    langfuse_dataset_id: str | None     # Langfuse Dataset ID
    last_synced_at: datetime | None

    class Config:
        # 唯一性约束: (name, version) 组合唯一
        pass
```

**Validation Rules**:
- `name` 必须符合 kebab-case 格式
- `cases` 至少包含 1 个用例
- `case_id` 在数据集内唯一

**State Transitions**:
```
[创建] → pending → [验证] → validated → [同步] → synced
                         ↓
                    validation_failed
```

---

### TestCase

单个测试用例。

```python
class TestCase(BaseModel):
    """单个测试用例"""

    # Identity
    case_id: str                        # 唯一标识，如 "qc_001"

    # Input
    input: str                          # 用户输入消息
    context_files: list[str] = []       # 测试时选中的文件路径
    conversation_history: list[Message] = []  # 多轮对话历史

    # Expected
    command: str | None = None          # Command 名称（元数据）
    expected_skill: str | None = None   # 期望触发的 Skill
    expected_output_contains: list[str] = []  # 期望包含的关键词
    expected_behavior: str              # 期望行为描述（用于 LLM 评估）

    # Metadata
    tags: list[str] = []                # 标签
    project_config: ProjectConfig | None = None

class Message(BaseModel):
    """对话消息"""
    role: Literal["user", "assistant"]
    content: str

class ProjectConfig(BaseModel):
    """测试项目配置"""
    name: str = "meta-agent-test"
    reuse: bool = True
    cleanup: bool = False
```

**Validation Rules**:
- `case_id` 必须唯一，推荐格式 `{plugin}_{number}`
- `input` 非空
- `expected_behavior` 非空
- `context_files` 中的文件路径相对于 `test-resources/files/`

---

### TestFile

测试所需的上下文文件。

```python
class TestFile(BaseModel):
    """测试文件"""

    # Identity
    relative_path: str                  # 相对路径（相对于 test-resources/files/）

    # Content
    file_size: int                      # 文件大小（字节）
    file_type: str                      # 文件类型（csv, xlsx, pdf 等）

    # Upload tracking
    uploaded_to_project: str | None     # 已上传到的项目名称
    sunnyagent_file_id: str | None      # SunnyAgent 中的文件 ID

    def absolute_path(self, base_dir: str) -> str:
        """获取绝对路径"""
        return os.path.join(base_dir, "test-resources/files", self.relative_path)
```

**Validation Rules**:
- 文件必须存在
- 文件大小 ≤ 10MB（SunnyAgent 限制）

---

### EvaluationResult

评估结果摘要。

```python
class EvaluationResult(BaseModel):
    """评估结果"""

    # Identity
    evaluation_id: str                  # UUID
    dataset_name: str
    dataset_version: str
    iteration: int                      # 迭代轮数

    # Summary
    total_cases: int
    passed_cases: int
    failed_cases: int
    overall_score: float                # 加权总分 [0, 1]

    # Dimension scores
    scores_by_dimension: dict[str, float]  # correctness, skill_trigger, etc.

    # Details
    failed_case_details: list[FailedCase]
    passed_case_ids: list[str]

    # Langfuse
    langfuse_session_id: str | None
    langfuse_dashboard_url: str | None

    # Timing
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
```

**Computed Properties**:
```python
@property
def pass_rate(self) -> float:
    return self.passed_cases / self.total_cases if self.total_cases > 0 else 0
```

---

### FailedCase

失败用例详情。

```python
class FailureCategory(str, Enum):
    """失败分类"""
    SKILL_NOT_TRIGGERED = "skill_not_triggered"
    WRONG_SKILL_TRIGGERED = "wrong_skill_triggered"
    OUTPUT_INCORRECT = "output_incorrect"
    OUTPUT_INCOMPLETE = "output_incomplete"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    FILE_CONTEXT_ERROR = "file_context_error"

class FailedCase(BaseModel):
    """失败用例详情"""

    # Identity
    case_id: str

    # Execution details
    actual_output: str
    actual_skill: str | None

    # Scores
    scores: dict[str, float]            # 各维度分数

    # Classification
    failure_category: FailureCategory
    failure_reason: str                 # 详细失败原因
    file_related: bool = False          # 是否与文件上下文相关

    # Tracing
    langfuse_trace_id: str | None
    langfuse_trace_url: str | None
```

---

### OptimizationConfig

优化配置。

```python
class OptimizationConfig(BaseModel):
    """优化配置"""

    # Target
    target_plugin: str                  # 目标 Plugin 名称
    dataset_path: str                   # 数据集文件路径

    # Completion criteria (with defaults)
    target_score: float = 0.8           # 目标分数
    max_iterations: int = 5             # 最大迭代次数
    regression_threshold: float = 0.05  # 回归阈值
    patience: int = 2                   # 耐心值
    min_improvement: float = 0.02       # 最小有效提升

    # Execution
    test_project_name: str = "meta-agent-test"
    cleanup_on_complete: bool = False

    # Git
    auto_commit: bool = True
    commit_prefix: str = "meta-agent:"

    @validator('target_score')
    def validate_target_score(cls, v):
        if not 0 < v <= 1:
            raise ValueError('target_score must be between 0 and 1')
        return v
```

**Termination Conditions**:
1. `current_score >= target_score` → 达标
2. `iteration >= max_iterations` → 超限
3. 连续 `patience` 轮提升 < `min_improvement` → 耐心耗尽

---

### Checkpoint

优化检查点，用于断点续跑。

```python
class OptimizationState(str, Enum):
    """优化状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class Checkpoint(BaseModel):
    """优化检查点"""

    # Identity
    optimization_id: str                # UUID

    # Config snapshot
    config: OptimizationConfig

    # Progress
    current_iteration: int = 0
    best_score: float = 0.0
    best_iteration: int = 0
    last_evaluation_id: str | None = None

    # File tracking
    modified_files: list[FileModification] = []

    # State
    state: OptimizationState = OptimizationState.PENDING
    error_message: str | None = None

    # Timing
    created_at: datetime
    updated_at: datetime

class FileModification(BaseModel):
    """文件修改记录"""
    file_path: str
    modification_type: Literal["create", "update"]
    git_commit_hash: str
    iteration: int
    timestamp: datetime
```

**Persistence**:
- 保存位置: `meta_agent/.checkpoints/{optimization_id}.json`
- 每轮迭代后更新
- 恢复时验证 git 状态一致性

---

### IterationReport

单轮迭代报告。

```python
class IterationReport(BaseModel):
    """迭代报告"""

    # Identity
    iteration: int
    optimization_id: str

    # Scores
    score_before: float
    score_after: float
    score_delta: float

    # Actions taken
    modifications: list[FileModification]
    analysis_summary: str               # Analyzer 的分析摘要

    # Evaluation
    evaluation_id: str
    langfuse_evaluation_url: str | None

    # Decision
    decision: Literal["continue", "rollback", "terminate"]
    decision_reason: str

    # Timing
    started_at: datetime
    completed_at: datetime
```

---

## Plugin Schema Models

### Command

Command 文件结构模型。

```python
class CommandFrontmatter(BaseModel):
    """Command 文件的 YAML frontmatter"""
    description: str
    allowed_tools: str | None = None
    argument_hint: str | None = None
    skills: list[str] = []

class Command(BaseModel):
    """Command 定义"""

    # Identity
    name: str                           # 从文件名推断
    plugin_name: str                    # 所属 Plugin

    # Content
    frontmatter: CommandFrontmatter
    content: str                        # Markdown 正文

    # File info
    file_path: str                      # 相对于 packages/

    def to_markdown(self) -> str:
        """生成 Markdown 文件内容"""
        yaml_content = yaml.dump(self.frontmatter.model_dump(exclude_none=True))
        return f"---\n{yaml_content}---\n\n{self.content}"
```

---

### Skill

Skill 文件结构模型。

```python
class SkillFrontmatter(BaseModel):
    """Skill 文件的 YAML frontmatter"""
    name: str
    description: str

class Skill(BaseModel):
    """Skill 定义"""

    # Identity
    name: str
    plugin_name: str

    # Content
    frontmatter: SkillFrontmatter
    content: str                        # Markdown 正文

    # File info
    file_path: str                      # 相对于 packages/
    references_dir: str | None = None   # references/ 目录路径

    def to_markdown(self) -> str:
        """生成 Markdown 文件内容"""
        yaml_content = yaml.dump(self.frontmatter.model_dump())
        return f"---\n{yaml_content}---\n\n{self.content}"
```

---

## Relationships

```
TestDataset 1:N TestCase
    - 一个数据集包含多个测试用例

TestCase N:M TestFile
    - 一个用例可以关联多个文件
    - 一个文件可以被多个用例使用

OptimizationConfig 1:1 Checkpoint
    - 一个优化配置对应一个检查点

Checkpoint 1:N IterationReport
    - 一个优化过程产生多个迭代报告

Checkpoint 1:N FileModification
    - 一个优化过程产生多个文件修改

EvaluationResult 1:N FailedCase
    - 一次评估包含多个失败用例
```

---

## Storage Strategy

| Entity | Storage | Location |
|--------|---------|----------|
| TestDataset | JSONL/CSV 文件 | `meta_agent/test-resources/datasets/` |
| TestFile | 文件系统 | `meta_agent/test-resources/files/` |
| Checkpoint | JSON 文件 | `meta_agent/.checkpoints/` |
| Command/Skill | Markdown 文件 | `packages/{plugin}/` |
| EvaluationResult | 内存 + Langfuse | 运行时计算，结果同步到 Langfuse |
| IterationReport | 内存 + 最终报告 | 运行时记录，最终输出到 Markdown |
