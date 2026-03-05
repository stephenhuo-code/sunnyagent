# Contract: Langfuse Client

**Module**: `meta_agent/services/langfuse_client.py`
**Version**: 1.0.0
**Date**: 2026-03-04

## Overview

Langfuse 客户端封装，负责与 Langfuse 实例交互。复用 SunnyAgent 的 Langfuse 配置。

## Configuration

```python
# 从环境变量读取（与 SunnyAgent 共享）
LANGFUSE_PUBLIC_KEY: str
LANGFUSE_SECRET_KEY: str
LANGFUSE_BASE_URL: str = "http://localhost:3001"
```

## Interface

### Dataset Operations (Write)

```python
class LangfuseClient:
    """Langfuse 客户端"""

    async def create_dataset(
        self,
        name: str,
        description: str | None = None,
        metadata: dict | None = None
    ) -> str:
        """
        创建数据集

        Args:
            name: 数据集名称，格式 "meta-agent-{plugin}-{version}"
            description: 数据集描述
            metadata: 额外元数据

        Returns:
            dataset_id: Langfuse Dataset ID

        Raises:
            LangfuseError: 创建失败
        """

    async def create_dataset_item(
        self,
        dataset_id: str,
        input_data: dict,
        expected_output: dict | None = None,
        metadata: dict | None = None
    ) -> str:
        """
        创建数据集项

        Args:
            dataset_id: 数据集 ID
            input_data: 输入数据 {"input": "...", "context_files": [...]}
            expected_output: 期望输出 {"skill": "...", "contains": [...]}
            metadata: 元数据 {"case_id": "...", "tags": [...]}

        Returns:
            item_id: Dataset Item ID
        """

    async def update_dataset(
        self,
        dataset_id: str,
        items: list[dict]
    ) -> None:
        """
        增量更新数据集

        Args:
            dataset_id: 数据集 ID
            items: 新增或更新的项
        """
```

### Trace Operations (Read)

```python
    async def get_traces(
        self,
        session_id: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Trace]:
        """
        获取 traces

        Args:
            session_id: 会话 ID 过滤
            limit: 返回数量限制
            offset: 分页偏移

        Returns:
            traces: Trace 列表
        """

    async def get_trace_detail(
        self,
        trace_id: str
    ) -> TraceDetail:
        """
        获取 trace 详情（含 spans, generations）

        Args:
            trace_id: Trace ID

        Returns:
            detail: 包含完整执行信息的详情
        """
```

### Score Operations (Write)

```python
    async def add_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None
    ) -> None:
        """
        为 trace 添加评分

        Args:
            trace_id: Trace ID
            name: 评分维度 (correctness, skill_trigger, etc.)
            value: 分数 [0, 1]
            comment: 评分说明
        """

    async def add_scores_batch(
        self,
        scores: list[ScoreInput]
    ) -> None:
        """
        批量添加评分

        Args:
            scores: 评分列表
        """
```

## Data Types

```python
@dataclass
class Trace:
    """Trace 摘要"""
    id: str
    session_id: str | None
    name: str | None
    input: dict | None
    output: dict | None
    metadata: dict | None
    timestamp: datetime

@dataclass
class TraceDetail:
    """Trace 详情"""
    trace: Trace
    spans: list[Span]
    generations: list[Generation]

@dataclass
class Span:
    """执行步骤"""
    id: str
    name: str
    start_time: datetime
    end_time: datetime
    input: dict | None
    output: dict | None

@dataclass
class Generation:
    """LLM 调用"""
    id: str
    model: str
    prompt: str | None
    completion: str | None
    usage: dict | None

@dataclass
class ScoreInput:
    """评分输入"""
    trace_id: str
    name: str
    value: float
    comment: str | None = None
```

## Error Handling

```python
class LangfuseError(Exception):
    """Langfuse 操作错误"""
    pass

class LangfuseConnectionError(LangfuseError):
    """连接错误"""
    pass

class LangfuseNotFoundError(LangfuseError):
    """资源不存在"""
    pass
```

## Usage Example

```python
client = LangfuseClient()

# 创建数据集
dataset_id = await client.create_dataset(
    name="meta-agent-qc-v1",
    description="Manufacturing QC plugin test dataset"
)

# 添加测试项
await client.create_dataset_item(
    dataset_id=dataset_id,
    input_data={"input": "/complaint-analysis 分析投诉"},
    expected_output={"skill": "quality-analysis"},
    metadata={"case_id": "qc_001"}
)

# 读取 traces
traces = await client.get_traces(session_id="test-session-123")

# 添加评分
await client.add_score(
    trace_id=traces[0].id,
    name="correctness",
    value=0.85,
    comment="输出包含所有期望关键词"
)
```
