# API 文档

> SunnyAgent REST API 参考文档

## 概述

- **Base URL**: `/api`
- **认证方式**: JWT Token（HTTP-only Cookie）
- **响应格式**: JSON

---

## 端点汇总

### 认证 (`/api/auth`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 登录，返回 JWT cookie |
| `/api/auth/logout` | POST | 登出，清除 cookie |
| `/api/auth/me` | GET | 获取当前用户信息 |

### 用户管理 (`/api/users`) - 仅管理员

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/users` | GET | 获取所有用户列表 |
| `/api/users` | POST | 创建新用户 |
| `/api/users/{id}` | DELETE | 删除用户 |
| `/api/users/{id}/status` | PATCH | 更新用户状态 |

### 对话管理 (`/api/conversations`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/conversations` | GET | 列出用户对话 |
| `/api/conversations` | POST | 创建新对话 |
| `/api/conversations/{id}` | GET | 获取对话详情 |
| `/api/conversations/{id}` | PATCH | 更新对话标题 |
| `/api/conversations/{id}` | DELETE | 删除对话 |
| `/api/conversations/{id}/project` | POST | 关联对话到项目 |
| `/api/conversations/{id}/project` | DELETE | 取消对话与项目关联 |

### 项目管理 (`/api/projects`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/projects` | GET | 列出用户项目 |
| `/api/projects` | POST | 创建新项目 |
| `/api/projects/{id}` | GET | 获取项目详情 |
| `/api/projects/{id}` | PATCH | 更新项目 |
| `/api/projects/{id}` | DELETE | 删除项目 |
| `/api/projects/{id}/files` | GET | 列出项目文件 |
| `/api/projects/{id}/files` | POST | 上传项目文件 |
| `/api/projects/{id}/files/{file_id}` | PATCH | 更新文件信息 |
| `/api/projects/{id}/files/{file_id}` | DELETE | 删除项目文件 |
| `/api/projects/{id}/files/{file_id}/download` | GET | 下载项目文件 |
| `/api/projects/{id}/conversations` | GET | 列出项目关联的对话 |

### 聊天 (`/api/chat`, `/api/threads`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回 SSE 流 |
| `/api/threads` | POST | 创建新线程 |
| `/api/threads/{id}/history` | GET | 获取线程消息历史 |

### 文件 (`/api/files`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/files/upload` | POST | 上传临时文件 |
| `/api/files/{id}/download` | GET | 下载上传的文件 |
| `/api/files/{id}/content` | GET | 预览文件内容 |
| `/api/files/{id}/{filename}` | GET | 下载 AI 生成的文件 |

### Agent 和技能

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agents` | GET | 列出已注册 Agent |
| `/api/skills` | GET | 列出所有技能 |
| `/api/skills/{name}` | GET | 获取技能详情 |

---

## 认证

所有需要认证的端点必须在请求中包含有效的 `access_token` cookie。

---

## 认证 API

### POST `/api/auth/login`

用户登录，获取 JWT token。

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应** `200 OK`:
```json
{
  "user": {
    "id": "uuid",
    "username": "string",
    "role": "admin" | "user",
    "status": "active" | "disabled",
    "created_at": "datetime"
  }
}
```

**错误**:
- `401` - 用户名或密码错误
- `403` - 账户已禁用

---

### POST `/api/auth/logout`

用户登出，清除认证 cookie。

**响应** `200 OK`:
```json
{
  "message": "Logged out successfully"
}
```

---

### GET `/api/auth/me`

获取当前登录用户信息。

**认证**: 需要

**响应** `200 OK`:
```json
{
  "id": "uuid",
  "username": "string",
  "role": "admin" | "user",
  "status": "active" | "disabled",
  "created_at": "datetime"
}
```

---

## 用户管理 API（仅管理员）

### GET `/api/users`

获取所有用户列表。

**认证**: Admin

**响应** `200 OK`:
```json
{
  "users": [
    {
      "id": "uuid",
      "username": "string",
      "role": "admin" | "user",
      "status": "active" | "disabled",
      "created_at": "datetime"
    }
  ]
}
```

---

### POST `/api/users`

创建新用户。

**认证**: Admin

**请求体**:
```json
{
  "username": "string",
  "password": "string",
  "role": "admin" | "user"
}
```

**响应** `201 Created`:
```json
{
  "id": "uuid",
  "username": "string",
  "role": "admin" | "user",
  "status": "active",
  "created_at": "datetime"
}
```

**错误**:
- `400` - 用户名已存在

---

### DELETE `/api/users/{user_id}`

删除用户。

**认证**: Admin

**路径参数**:
- `user_id` - 用户 UUID

**响应** `204 No Content`

**错误**:
- `400` - 不能删除自己 / 不能删除最后一个管理员
- `404` - 用户不存在

---

### PATCH `/api/users/{user_id}/status`

更新用户状态（启用/禁用）。

**认证**: Admin

**路径参数**:
- `user_id` - 用户 UUID

**请求体**:
```json
{
  "status": "active" | "disabled"
}
```

**响应** `200 OK`:
```json
{
  "id": "uuid",
  "username": "string",
  "role": "admin" | "user",
  "status": "active" | "disabled",
  "created_at": "datetime"
}
```

---

## 对话管理 API

### GET `/api/conversations`

获取用户对话列表。

**认证**: 需要

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `limit` | int | 每页数量，默认 50，最大 100 |
| `offset` | int | 分页偏移量 |
| `project_id` | uuid | 按项目筛选 |
| `exclude_project` | bool | 仅返回未关联项目的对话（历史对话） |

**响应** `200 OK`:
```json
{
  "conversations": [
    {
      "id": "uuid",
      "thread_id": "string",
      "title": "string",
      "project_id": "uuid | null",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "total": 100
}
```

---

### POST `/api/conversations`

创建新对话。

**认证**: 需要

**请求体**:
```json
{
  "title": "string (optional)",
  "project_id": "uuid (optional)"
}
```

**响应** `201 Created`:
```json
{
  "id": "uuid",
  "thread_id": "string",
  "title": "string",
  "project_id": "uuid | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### GET `/api/conversations/{conversation_id}`

获取对话详情。

**认证**: 需要

**响应** `200 OK`:
```json
{
  "id": "uuid",
  "thread_id": "string",
  "title": "string",
  "project_id": "uuid | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### PATCH `/api/conversations/{conversation_id}`

更新对话标题。

**认证**: 需要

**请求体**:
```json
{
  "title": "string"
}
```

**响应** `200 OK`: 返回更新后的对话对象

---

### DELETE `/api/conversations/{conversation_id}`

删除对话。

**认证**: 需要

**响应** `204 No Content`

---

### POST `/api/conversations/{conversation_id}/project`

将对话关联到项目。

**认证**: 需要

**请求体**:
```json
{
  "project_id": "uuid"
}
```

**响应** `200 OK`:
```json
{
  "message": "对话已添加到项目"
}
```

---

### DELETE `/api/conversations/{conversation_id}/project`

取消对话与项目的关联（移至历史对话）。

**认证**: 需要

**响应** `204 No Content`

---

## 项目管理 API

### GET `/api/projects`

获取用户项目列表。

**认证**: 需要

**响应** `200 OK`:
```json
[
  {
    "id": "uuid",
    "name": "string",
    "file_count": 5,
    "conversation_count": 3,
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

### POST `/api/projects`

创建新项目。

**认证**: 需要

**请求体**:
```json
{
  "name": "string"
}
```

**响应** `201 Created`:
```json
{
  "id": "uuid",
  "name": "string",
  "files": [],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**错误**:
- `400` - 项目名称已存在

---

### GET `/api/projects/{project_id}`

获取项目详情。

**认证**: 需要

**响应** `200 OK`:
```json
{
  "id": "uuid",
  "name": "string",
  "files": [
    {
      "file_id": "uuid",
      "filename": "string",
      "file_type": "pdf | docx | txt | ...",
      "file_size": 1024,
      "created_at": "datetime"
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### PATCH `/api/projects/{project_id}`

更新项目名称。

**认证**: 需要

**请求体**:
```json
{
  "name": "string"
}
```

**响应** `200 OK`: 返回更新后的项目对象

---

### DELETE `/api/projects/{project_id}`

删除项目（包括所有关联文件）。

**认证**: 需要

**响应** `204 No Content`

---

### GET `/api/projects/{project_id}/files`

获取项目文件列表。

**认证**: 需要

**响应** `200 OK`:
```json
[
  {
    "file_id": "uuid",
    "filename": "string",
    "file_type": "pdf | docx | txt | ...",
    "file_size": 1024,
    "created_at": "datetime"
  }
]
```

---

### POST `/api/projects/{project_id}/files`

上传项目文件。

**认证**: 需要

**请求**: `multipart/form-data`
- `file` - 文件内容

**限制**:
- 最大文件大小: 10MB
- 每个项目最多 50 个文件
- 支持的扩展名: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.py`, `.js`, `.ts`, 等

**响应** `201 Created`:
```json
{
  "file_id": "uuid",
  "filename": "string",
  "file_type": "string",
  "file_size": 1024
}
```

---

### PATCH `/api/projects/{project_id}/files/{file_id}`

重命名项目文件。

**认证**: 需要

**请求体**:
```json
{
  "filename": "new_filename.pdf"
}
```

**响应** `200 OK`: 返回更新后的文件信息

---

### DELETE `/api/projects/{project_id}/files/{file_id}`

删除项目文件。

**认证**: 需要

**响应** `204 No Content`

---

### GET `/api/projects/{project_id}/files/{file_id}/download`

下载项目文件。

**认证**: 需要

**响应**: 文件流（Content-Disposition: attachment）

---

### GET `/api/projects/{project_id}/conversations`

获取项目关联的对话列表。

**认证**: 需要

**响应** `200 OK`:
```json
[
  {
    "id": "uuid",
    "thread_id": "string",
    "title": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

## 聊天 API

### POST `/api/chat`

发送消息并接收 AI 响应（SSE 流）。

**认证**: 需要

**请求体**:
```json
{
  "thread_id": "string",
  "message": "string",
  "agent": "string (optional)",
  "skill": "string (optional)",
  "file_ids": ["uuid"] ,
  "project_id": "uuid (optional)",
  "project_file_ids": ["uuid"]
}
```

| 字段 | 说明 |
|------|------|
| `thread_id` | 对话线程 ID |
| `message` | 用户消息 |
| `agent` | 指定 Agent，跳过路由 |
| `skill` | 注入技能指令 |
| `file_ids` | 上传的临时文件 ID |
| `project_id` | 项目 ID |
| `project_file_ids` | 项目文件 ID 列表 |

**响应**: `text/event-stream` (SSE)

**SSE 事件类型**:
```
event: thinking
data: {"type": "routing", "content": "..."}

event: task_spawned
data: {"task_id": "...", "subagent_type": "...", "status": "pending"}

event: task_started
data: {"task_id": "..."}

event: tool_call_start
data: {"name": "...", "task_id": "..."}

event: tool_call_result
data: {"result": "..."}

event: task_output
data: {"task_id": "...", "text": "..."}

event: task_completed
data: {"task_id": "...", "status": "success", "duration_ms": 1234}

event: text_delta
data: {"text": "..."}

event: error
data: {"error": "..."}

event: done
data: {}
```

---

### POST `/api/threads`

创建新线程。

**认证**: 需要

**响应** `200 OK`:
```json
{
  "thread_id": "string"
}
```

---

### GET `/api/threads/{thread_id}/history`

获取线程消息历史。

**认证**: 需要

**响应** `200 OK`:
```json
{
  "messages": [
    {
      "role": "user" | "assistant",
      "content": "string",
      "timestamp": "datetime"
    }
  ]
}
```

---

## 文件 API

### POST `/api/files/upload`

上传临时文件（用于对话）。

**认证**: 需要

**请求**: `multipart/form-data`
- `file` - 文件内容

**响应** `200 OK`:
```json
{
  "file_id": "uuid",
  "filename": "string",
  "content_type": "string"
}
```

---

### GET `/api/files/{file_id}/download`

下载上传的临时文件。

**认证**: 需要

**响应**: 文件流

---

### GET `/api/files/{file_id}/content`

预览文件内容（文本文件）。

**认证**: 需要

**响应** `200 OK`:
```json
{
  "content": "string",
  "truncated": false
}
```

---

### GET `/api/files/{file_id}/{filename}`

下载 AI 生成的文件。

**响应**: 文件流

---

## Agent 和技能 API

### GET `/api/agents`

获取已注册的 Agent 列表。

**响应** `200 OK`:
```json
{
  "agents": [
    {
      "name": "research",
      "description": "Web research, current events...",
      "icon": "search",
      "capabilities": ["web_search", "news_search"]
    }
  ]
}
```

---

### GET `/api/skills`

获取所有可用技能列表。

**响应** `200 OK`:
```json
{
  "skills": [
    {
      "name": "pdf",
      "description": "PDF 文件处理技能"
    }
  ]
}
```

---

### GET `/api/skills/{name}`

获取技能详情和指令。

**响应** `200 OK`:
```json
{
  "name": "pdf",
  "description": "PDF 文件处理技能",
  "instructions": "..."
}
```

---

## 错误响应

所有 API 错误使用统一格式:

```json
{
  "detail": "错误描述"
}
```

**常见 HTTP 状态码**:
| 状态码 | 说明 |
|--------|------|
| `400` | 请求参数错误 |
| `401` | 未认证 |
| `403` | 权限不足 |
| `404` | 资源不存在 |
| `500` | 服务器内部错误 |
