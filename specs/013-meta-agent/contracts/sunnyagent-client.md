# Contract: SunnyAgent Client

**Module**: `meta_agent/services/sunnyagent_client.py`
**Version**: 1.0.0
**Date**: 2026-03-04

## Overview

SunnyAgent API 客户端封装，负责通过 HTTP API 与 SunnyAgent 交互。

## Configuration

```python
SUNNYAGENT_BASE_URL: str = "http://localhost:8008"
SUNNYAGENT_ADMIN_USERNAME: str
SUNNYAGENT_ADMIN_PASSWORD: str
```

## Interface

### Authentication

```python
class SunnyAgentClient:
    """SunnyAgent API 客户端"""

    async def login(self) -> None:
        """
        使用 admin 账号登录

        Raises:
            AuthenticationError: 登录失败
        """

    async def logout(self) -> None:
        """登出"""
```

### Project Operations

```python
    async def create_project(
        self,
        name: str,
        description: str | None = None
    ) -> Project:
        """
        创建项目

        Args:
            name: 项目名称
            description: 项目描述

        Returns:
            project: 创建的项目

        Raises:
            ProjectExistsError: 项目已存在
        """

    async def get_project(
        self,
        name: str
    ) -> Project | None:
        """
        获取项目（按名称）

        Returns:
            project: 项目或 None
        """

    async def delete_project(
        self,
        project_id: str
    ) -> None:
        """删除项目"""
```

### File Operations

```python
    async def upload_file(
        self,
        project_id: str,
        file_path: str,
        file_name: str | None = None
    ) -> FileInfo:
        """
        上传文件到项目

        Args:
            project_id: 项目 ID
            file_path: 本地文件路径
            file_name: 上传后的文件名（可选）

        Returns:
            file_info: 文件信息

        Raises:
            FileTooLargeError: 文件超过 10MB
            UploadError: 上传失败
        """

    async def get_project_files(
        self,
        project_id: str
    ) -> list[FileInfo]:
        """获取项目的所有文件"""
```

### Conversation Operations

```python
    async def create_conversation(
        self,
        project_id: str,
        title: str | None = None
    ) -> Conversation:
        """
        创建对话

        Args:
            project_id: 项目 ID
            title: 对话标题

        Returns:
            conversation: 创建的对话
        """

    async def get_conversation(
        self,
        conversation_id: str
    ) -> Conversation | None:
        """获取对话详情"""
```

### Chat Operations

```python
    async def send_message(
        self,
        thread_id: str,
        message: str,
        file_ids: list[str] | None = None,
        command: str | None = None
    ) -> AsyncIterator[SSEEvent]:
        """
        发送消息并获取流式响应

        Args:
            thread_id: 线程 ID
            message: 用户消息
            file_ids: 选中的文件 ID 列表
            command: 直接调用的 Command 名称（可选）

        Yields:
            event: SSE 事件

        Note:
            SunnyAgent 会自动将执行 trace 写入 Langfuse
        """

    async def send_message_and_wait(
        self,
        thread_id: str,
        message: str,
        file_ids: list[str] | None = None,
        timeout: float = 60.0
    ) -> ChatResponse:
        """
        发送消息并等待完整响应

        Args:
            timeout: 超时时间（秒）

        Returns:
            response: 完整响应

        Raises:
            TimeoutError: 超时
        """
```

## Data Types

```python
@dataclass
class Project:
    """项目"""
    id: str
    name: str
    description: str | None
    created_at: datetime

@dataclass
class FileInfo:
    """文件信息"""
    id: str
    name: str
    size: int
    content_type: str
    uploaded_at: datetime

@dataclass
class Conversation:
    """对话"""
    id: str
    project_id: str
    thread_id: str
    title: str | None
    created_at: datetime

@dataclass
class SSEEvent:
    """SSE 事件"""
    event: str  # message, tool_call, error, done
    data: dict

@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    tool_calls: list[dict]
    agent_used: str | None
    skill_used: str | None
    langfuse_trace_id: str | None
```

## Error Handling

```python
class SunnyAgentError(Exception):
    """SunnyAgent 操作错误"""
    pass

class AuthenticationError(SunnyAgentError):
    """认证错误"""
    pass

class ProjectExistsError(SunnyAgentError):
    """项目已存在"""
    pass

class FileTooLargeError(SunnyAgentError):
    """文件过大"""
    pass

class UploadError(SunnyAgentError):
    """上传错误"""
    pass

class ChatTimeoutError(SunnyAgentError):
    """聊天超时"""
    pass
```

## Usage Example

```python
client = SunnyAgentClient()

# 登录
await client.login()

# 创建或获取项目
project = await client.get_project("meta-agent-test")
if not project:
    project = await client.create_project(
        name="meta-agent-test",
        description="Meta-Agent 测试项目"
    )

# 上传文件
file_info = await client.upload_file(
    project_id=project.id,
    file_path="/path/to/test-data.csv"
)

# 创建对话
conversation = await client.create_conversation(
    project_id=project.id,
    title="QC Test Case 001"
)

# 发送消息
response = await client.send_message_and_wait(
    thread_id=conversation.thread_id,
    message="/complaint-analysis 分析这批客户投诉",
    file_ids=[file_info.id]
)

print(f"Response: {response.content}")
print(f"Skill used: {response.skill_used}")
print(f"Trace ID: {response.langfuse_trace_id}")
```

## SSE Event Stream

```
event: message
data: {"content": "正在分析..."}

event: tool_call
data: {"name": "data_profile", "input": {...}}

event: message
data: {"content": "分析完成。根据数据..."}

event: done
data: {"trace_id": "abc123", "agent": "manufacturing-qc", "skill": "quality-analysis"}
```
