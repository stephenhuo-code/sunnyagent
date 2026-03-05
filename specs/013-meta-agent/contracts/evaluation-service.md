# Contract: Evaluation Service

**Module**: `meta_agent/services/evaluation_service.py`
**Version**: 1.0.0
**Date**: 2026-03-04

## Overview

评估服务，负责执行测试用例并计算分数。

## Dependencies

- `SunnyAgentClient` - 执行测试
- `LangfuseClient` - 读取 trace、写入 score
- `ScoreCalculator` - 计算分数

## Interface

### Evaluation Execution

```python
class EvaluationService:
    """评估服务"""

    def __init__(
        self,
        sunnyagent_client: SunnyAgentClient,
        langfuse_client: LangfuseClient,
        score_calculator: ScoreCalculator
    ):
        pass

    async def run_evaluation(
        self,
        dataset: TestDataset,
        project_name: str,
        iteration: int = 0
    ) -> EvaluationResult:
        """
        运行完整评估

        Args:
            dataset: 测试数据集
            project_name: 测试项目名称
            iteration: 迭代轮数

        Returns:
            result: 评估结果

        Process:
            1. 确保测试项目存在
            2. 上传所需文件
            3. 对每个 case 执行测试
            4. 从 Langfuse 读取 trace
            5. 计算各维度分数
            6. 将 score 写入 Langfuse
            7. 汇总结果
        """

    async def run_single_case(
        self,
        case: TestCase,
        project_id: str,
        file_id_map: dict[str, str]
    ) -> CaseResult:
        """
        运行单个测试用例

        Args:
            case: 测试用例
            project_id: 项目 ID
            file_id_map: 文件路径到 ID 的映射

        Returns:
            result: 用例结果
        """
```

### Score Calculation

```python
    async def calculate_case_score(
        self,
        case: TestCase,
        response: ChatResponse,
        trace: TraceDetail
    ) -> CaseScore:
        """
        计算单个用例的分数

        Args:
            case: 测试用例
            response: 聊天响应
            trace: Langfuse trace 详情

        Returns:
            score: 各维度分数
        """
```

### Environment Setup

```python
    async def setup_test_environment(
        self,
        project_name: str,
        files: list[TestFile]
    ) -> tuple[str, dict[str, str]]:
        """
        准备测试环境

        Args:
            project_name: 项目名称
            files: 需要上传的文件

        Returns:
            project_id: 项目 ID
            file_id_map: {relative_path: file_id}
        """

    async def cleanup_test_environment(
        self,
        project_id: str,
        delete_project: bool = False
    ) -> None:
        """清理测试环境"""
```

## Data Types

```python
@dataclass
class CaseResult:
    """单个用例结果"""
    case_id: str
    passed: bool
    response: ChatResponse
    scores: CaseScore
    error: str | None = None
    execution_time: float = 0.0

@dataclass
class CaseScore:
    """用例分数"""
    correctness: float          # [0, 1]
    skill_trigger: float        # [0, 1]
    response_quality: float     # [0, 1]
    file_context_usage: float   # [0, 1]
    overall: float              # 加权平均

    def to_dict(self) -> dict[str, float]:
        return {
            "correctness": self.correctness,
            "skill_trigger": self.skill_trigger,
            "response_quality": self.response_quality,
            "file_context_usage": self.file_context_usage,
            "overall": self.overall
        }
```

## Score Calculation Logic

### Correctness (50%)

```python
def calculate_correctness(
    response: str,
    expected_contains: list[str]
) -> float:
    """
    计算输出正确性

    Logic:
        - 如果 expected_contains 为空，返回 1.0
        - 否则计算包含的关键词比例
    """
    if not expected_contains:
        return 1.0

    matched = sum(1 for kw in expected_contains if kw in response)
    return matched / len(expected_contains)
```

### Skill Trigger (16.7%)

```python
def calculate_skill_trigger(
    actual_skill: str | None,
    expected_skill: str | None
) -> float:
    """
    计算 Skill 触发正确性

    Logic:
        - 如果 expected_skill 为空，返回 1.0
        - 如果匹配，返回 1.0
        - 否则返回 0.0
    """
    if not expected_skill:
        return 1.0
    return 1.0 if actual_skill == expected_skill else 0.0
```

### Response Quality (16.7%)

```python
async def calculate_response_quality(
    response: str,
    expected_behavior: str,
    llm_client: Any
) -> float:
    """
    使用 LLM 评估回复质量

    Prompt:
        评估以下回复是否符合期望行为。
        期望行为: {expected_behavior}
        实际回复: {response}

        评分 (0-10):
    """
    # 调用 LLM 评估
    score = await llm_evaluate(response, expected_behavior)
    return score / 10.0  # 归一化到 [0, 1]
```

### File Context Usage (16.7%)

```python
def calculate_file_context_usage(
    trace: TraceDetail,
    expected_files: list[str]
) -> float:
    """
    计算文件上下文使用正确性

    Logic:
        - 如果 expected_files 为空，返回 1.0
        - 检查 trace 中是否有文件读取操作
        - 检查是否使用了期望的文件
    """
    if not expected_files:
        return 1.0

    # 从 trace spans 中提取文件操作
    used_files = extract_file_operations(trace)
    matched = sum(1 for f in expected_files if f in used_files)
    return matched / len(expected_files)
```

### Overall Score

```python
def calculate_overall(scores: CaseScore) -> float:
    """
    计算加权总分

    Weights:
        - correctness: 50%
        - skill_trigger: 16.7%
        - response_quality: 16.7%
        - file_context_usage: 16.7%
    """
    return (
        0.50 * scores.correctness +
        0.167 * scores.skill_trigger +
        0.167 * scores.response_quality +
        0.167 * scores.file_context_usage
    )
```

## Error Handling

```python
class EvaluationError(Exception):
    """评估错误"""
    pass

class CaseExecutionError(EvaluationError):
    """用例执行错误"""
    def __init__(self, case_id: str, reason: str):
        self.case_id = case_id
        super().__init__(f"Case {case_id} failed: {reason}")

class CaseTimeoutError(CaseExecutionError):
    """用例超时"""
    pass
```

## Retry Logic

```python
# 单个 case 执行的重试策略
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # 指数退避（秒）

async def execute_with_retry(case: TestCase) -> CaseResult:
    for attempt in range(MAX_RETRIES):
        try:
            return await run_single_case(case)
        except (TimeoutError, RateLimitError) as e:
            if attempt == MAX_RETRIES - 1:
                return CaseResult(
                    case_id=case.case_id,
                    passed=False,
                    error=str(e)
                )
            await asyncio.sleep(RETRY_DELAYS[attempt])
```

## Usage Example

```python
service = EvaluationService(
    sunnyagent_client=sunnyagent,
    langfuse_client=langfuse,
    score_calculator=calculator
)

# 运行评估
result = await service.run_evaluation(
    dataset=dataset,
    project_name="meta-agent-test",
    iteration=1
)

print(f"Overall score: {result.overall_score:.2f}")
print(f"Pass rate: {result.pass_rate:.1%}")
print(f"Failed cases: {len(result.failed_case_details)}")

# 查看 Langfuse
print(f"Dashboard: {result.langfuse_dashboard_url}")
```
