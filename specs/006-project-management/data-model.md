# Data Model: Project Management

**Feature**: 006-project-management
**Date**: 2026-02-17

## Entity Relationship Diagram

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│     users       │         │    projects     │         │ project_files   │
├─────────────────┤         ├─────────────────┤         ├─────────────────┤
│ id (PK)         │◄───────┤ user_id (FK)    │         │ id (PK)         │
│ username        │    1:N  │ id (PK)         │◄───────┤ project_id (FK) │
│ ...             │         │ name            │    1:N  │ file_id         │
└─────────────────┘         │ created_at      │         │ storage_path    │
                            │ updated_at      │         │ original_name   │
                            │ is_deleted      │         │ content_type    │
                            └────────┬────────┘         │ size_bytes      │
                                     │                  │ created_at      │
                                     │ 1:N              └─────────────────┘
                                     │ (optional)
                            ┌────────▼────────┐
                            │  conversations  │
                            ├─────────────────┤
                            │ id (PK)         │
                            │ project_id (FK) │  ← NEW FIELD (nullable)
                            │ user_id (FK)    │
                            │ thread_id       │
                            │ title           │
                            │ ...             │
                            └─────────────────┘
```

---

## Table: projects

新建表,存储项目基本信息。

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 项目唯一标识 |
| user_id | UUID | FK → users(id), NOT NULL, ON DELETE CASCADE | 所属用户 |
| name | VARCHAR(100) | NOT NULL | 项目名称 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |
| is_deleted | BOOLEAN | NOT NULL, DEFAULT FALSE | 软删除标记 |

### Indexes

| Name | Columns | Condition | Purpose |
|------|---------|-----------|---------|
| idx_projects_user | user_id | WHERE NOT is_deleted | 按用户查询项目 |
| idx_projects_updated | updated_at DESC | WHERE NOT is_deleted | 按更新时间排序 |

### Constraints

| Name | Type | Definition |
|------|------|------------|
| uq_projects_user_name | UNIQUE | (user_id, name) WHERE NOT is_deleted |

### Triggers

- `projects_updated_at`: 更新时自动设置 `updated_at = NOW()`

---

## Table: project_files

新建表,存储项目关联的文件。

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 记录唯一标识 |
| project_id | UUID | FK → projects(id), NOT NULL, ON DELETE CASCADE | 所属项目 |
| file_id | VARCHAR(36) | NOT NULL | 文件唯一标识 (UUID 字符串) |
| storage_path | VARCHAR(512) | NOT NULL | 文件存储路径 |
| original_name | VARCHAR(255) | NOT NULL | 原始文件名 |
| content_type | VARCHAR(100) | | MIME 类型 |
| size_bytes | BIGINT | NOT NULL | 文件大小 (字节) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 上传时间 |

### Indexes

| Name | Columns | Purpose |
|------|---------|---------|
| idx_project_files_project | project_id | 按项目查询文件 |
| idx_project_files_file_id | file_id | 按文件 ID 查询 |

### Constraints

| Name | Type | Definition |
|------|------|------------|
| uq_project_files_project_name | UNIQUE | (project_id, original_name) |

---

## Table: conversations (MODIFY)

修改现有表,添加 `project_id` 字段。

### New Column

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| project_id | UUID | FK → projects(id), ON DELETE SET NULL | 所属项目 (可空) |

### New Index

| Name | Columns | Condition | Purpose |
|------|---------|-----------|---------|
| idx_conversations_project | project_id | WHERE project_id IS NOT NULL AND NOT is_deleted | 按项目查询对话 |

---

## Validation Rules

### Project

| Field | Rule | Error Message |
|-------|------|---------------|
| name | 长度 1-100 字符 | "项目名称长度必须在 1-100 字符之间" |
| name | 同用户下唯一 | "项目名称已存在" |
| name | 不能只包含空白字符 | "项目名称不能为空" |

### ProjectFile

| Field | Rule | Error Message |
|-------|------|---------------|
| size_bytes | ≤ 10MB (10485760) | "文件大小不能超过 10MB" |
| original_name | 长度 ≤ 255 字符 | "文件名过长" |
| content_type | 在允许列表中 | "不支持的文件类型" |
| project file count | ≤ 50 | "项目文件数量已达上限 (50)" |

### Allowed Content Types

```python
ALLOWED_CONTENT_TYPES = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    # Code files (by extension, mapped to text/plain or specific type)
    "text/x-python",
    "text/javascript",
    "text/typescript",
    "text/x-java",
    "text/x-go",
    "text/x-c",
    "text/x-c++",
    "text/x-rust",
}

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".csv", ".json",
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".c", ".cpp", ".h", ".hpp",
    ".rs", ".rb", ".php", ".swift", ".kt",
}
```

---

## State Transitions

### Project Lifecycle

```
┌─────────┐    create()    ┌─────────┐    delete()    ┌─────────┐
│ (none)  │ ──────────────►│ active  │ ──────────────►│ deleted │
└─────────┘                └────┬────┘                └─────────┘
                                │
                                │ update()
                                │
                           ┌────▼────┐
                           │ active  │
                           │(updated)│
                           └─────────┘
```

### Conversation-Project Association

```
┌──────────────┐   addToProject()   ┌────────────────┐
│ project_id   │ ─────────────────► │ project_id     │
│ = NULL       │                    │ = {project_id} │
│ (in History) │ ◄───────────────── │ (in Project)   │
└──────────────┘  removeFromProject └────────────────┘
                   or project deleted
```

---

## Migration Plan

### Migration 004: create_projects_table.py

```sql
-- Step 1: Create projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_projects_user ON projects(user_id) WHERE NOT is_deleted;
CREATE INDEX idx_projects_updated ON projects(updated_at DESC) WHERE NOT is_deleted;
CREATE UNIQUE INDEX uq_projects_user_name ON projects(user_id, name) WHERE NOT is_deleted;

-- Trigger for updated_at (reuse existing function if available)
CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Step 2: Create project_files table
CREATE TABLE project_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_id VARCHAR(36) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_project_files_project ON project_files(project_id);
CREATE INDEX idx_project_files_file_id ON project_files(file_id);
CREATE UNIQUE INDEX uq_project_files_project_name ON project_files(project_id, original_name);

-- Step 3: Add project_id to conversations
ALTER TABLE conversations ADD COLUMN project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
CREATE INDEX idx_conversations_project ON conversations(project_id) WHERE project_id IS NOT NULL AND NOT is_deleted;
```

### Rollback

```sql
ALTER TABLE conversations DROP COLUMN project_id;
DROP TABLE project_files;
DROP TABLE projects;
```
