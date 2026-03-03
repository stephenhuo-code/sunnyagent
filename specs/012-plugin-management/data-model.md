# Data Model: 插件管理系统

**Feature**: 012-plugin-management
**Date**: 2026-02-21

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────────┐       ┌─────────────────┐
│    users     │       │   uploaded_plugins   │       │ plugin_ratings  │
├──────────────┤       ├──────────────────────┤       ├─────────────────┤
│ id (PK)      │◄──────│ user_id (FK)         │       │ id (PK)         │
│ username     │       │ plugin_name (UK)     │───────│ user_id (FK)    │
│ ...          │       │ plugin_type          │       │ plugin_name     │
└──────────────┘       │ display_name         │       │ rating (1-5)    │
       │               │ description          │       │ created_at      │
       │               │ version              │       │ updated_at      │
       │               │ author               │       └─────────────────┘
       │               │ storage_path         │
       │               │ is_shared            │
       │               │ is_delisted          │
       │               │ created_at           │
       │               │ updated_at           │
       │               └──────────────────────┘
       │
       │               ┌──────────────────────┐
       └──────────────►│ user_plugin_states   │
                       ├──────────────────────┤
                       │ id (PK)              │
                       │ user_id (FK)         │
                       │ plugin_name (UK)     │
                       │ enabled              │
                       │ created_at           │
                       │ updated_at           │
                       └──────────────────────┘
```

## Entities

### 1. uploaded_plugins

用户上传的插件记录。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| user_id | UUID | FK → users.id, NOT NULL | 上传者 |
| plugin_name | VARCHAR(128) | NOT NULL | 插件标识（无前缀） |
| plugin_type | VARCHAR(16) | NOT NULL, CHECK IN ('agent', 'skill') | 插件类型 |
| display_name | VARCHAR(256) | NOT NULL | 显示名称 |
| description | TEXT | | 描述 |
| version | VARCHAR(32) | DEFAULT '1.0.0' | 版本号 |
| author | VARCHAR(128) | | 作者 |
| storage_path | VARCHAR(512) | NOT NULL | 文件存储路径 |
| is_shared | BOOLEAN | DEFAULT FALSE | 是否已分享 |
| is_delisted | BOOLEAN | DEFAULT FALSE | 是否已下架 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**Indexes**:
- `UNIQUE(user_id, plugin_name)` - 每用户插件名唯一
- `INDEX(user_id)` - 按用户查询
- `INDEX(is_shared, is_delisted)` - 插件市场查询

**Validation Rules**:
- plugin_name: 2-128字符，仅允许 `[a-z0-9-_]`
- plugin_type: 必须是 'agent' 或 'skill'
- storage_path: 必须指向有效目录

---

### 2. user_plugin_states

用户对插件的启用/禁用状态。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| user_id | UUID | FK → users.id, NOT NULL | 用户 |
| plugin_name | VARCHAR(192) | NOT NULL | 命名空间格式 {source}:{name} |
| enabled | BOOLEAN | DEFAULT TRUE | 是否启用 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**Indexes**:
- `UNIQUE(user_id, plugin_name)` - 每用户每插件唯一
- `INDEX(user_id, enabled)` - 查询用户启用的插件

**Validation Rules**:
- plugin_name: 格式 `{source}:{name}`，source ∈ {preset, package, uploaded, shared}

---

### 3. plugin_ratings

插件评分记录。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| user_id | UUID | FK → users.id, NOT NULL | 评分用户 |
| plugin_name | VARCHAR(192) | NOT NULL | 命名空间格式 {source}:{name} |
| rating | INT | NOT NULL, CHECK (1-5) | 评分 1-5 星 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**Indexes**:
- `UNIQUE(user_id, plugin_name)` - 每用户每插件一个评分
- `INDEX(plugin_name)` - 按插件聚合评分

**Validation Rules**:
- rating: 整数 1-5
- 仅 package: 和 shared: 前缀的插件可评分

---

## Runtime Models (Pydantic)

### PluginInfo

统一的插件信息模型，用于 API 响应。

```python
class PluginSource(str, Enum):
    PRESET = "preset"
    PACKAGE = "package"
    UPLOADED = "uploaded"
    SHARED = "shared"

class PluginType(str, Enum):
    AGENT = "agent"
    SKILL = "skill"

class SkillType(str, Enum):
    ATOMIC = "atomic"
    WORKFLOW = "workflow"

class SkillStepInfo(BaseModel):
    id: str
    description: str
    required_capability: str | None = None

class PluginRatingInfo(BaseModel):
    average: float
    count: int

class PluginInfo(BaseModel):
    name: str                          # 命名空间格式 {source}:{name}
    display_name: str
    type: PluginType
    source: PluginSource
    description: str
    version: str
    author: str
    enabled: bool                      # 当前用户是否启用

    # Agent 专有
    capabilities: list[str] | None = None
    commands: list[str] | None = None
    skills: list["PluginInfo"] | None = None

    # Skill 专有
    skill_type: SkillType | None = None
    steps: list[SkillStepInfo] | None = None

    # 评分（Package/Shared）
    rating: PluginRatingInfo | None = None

    # 分享相关
    uploader_id: UUID | None = None
    uploader_name: str | None = None
    is_delisted: bool = False
```

### UserPluginState

用户插件状态模型。

```python
class UserPluginState(BaseModel):
    plugin_name: str
    enabled: bool
    updated_at: datetime
```

### PluginUploadRequest

上传插件请求。

```python
class PluginUploadRequest(BaseModel):
    # 文件通过 multipart/form-data 上传
    pass

class PluginUploadResponse(BaseModel):
    plugin: PluginInfo
    message: str
```

### PluginStateUpdateRequest

更新插件状态请求。

```python
class PluginStateUpdateRequest(BaseModel):
    enabled: bool
```

### PluginRatingRequest

评分请求。

```python
class PluginRatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
```

---

## State Transitions

### 插件生命周期

```
[不存在] ──上传──► [Uploaded/Disabled]
                        │
                   启用/禁用
                        │
                        ▼
              [Uploaded/Enabled] ◄──┐
                        │           │
                      分享         取消分享
                        │           │
                        ▼           │
              [Shared/Enabled] ────►┘
                        │
                   下架（保留）
                        │
                        ▼
              [Shared/Delisted]
                        │
                      删除
                        │
                        ▼
                   [不存在]
```

### 状态说明

| 状态 | is_shared | is_delisted | 可见性 |
|------|-----------|-------------|--------|
| Uploaded | FALSE | FALSE | 仅上传者 |
| Shared | TRUE | FALSE | 所有用户 |
| Delisted | TRUE | TRUE | 已启用者保留 |

---

## Migration Script

```sql
-- Migration: create_plugin_tables
-- Created: 2026-02-21

-- 1. uploaded_plugins 表
CREATE TABLE uploaded_plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR(128) NOT NULL,
    plugin_type VARCHAR(16) NOT NULL CHECK (plugin_type IN ('agent', 'skill')),
    display_name VARCHAR(256) NOT NULL,
    description TEXT,
    version VARCHAR(32) DEFAULT '1.0.0',
    author VARCHAR(128),
    storage_path VARCHAR(512) NOT NULL,
    is_shared BOOLEAN DEFAULT FALSE,
    is_delisted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);

CREATE INDEX idx_uploaded_plugins_user_id ON uploaded_plugins(user_id);
CREATE INDEX idx_uploaded_plugins_shared ON uploaded_plugins(is_shared, is_delisted);

-- 2. user_plugin_states 表
CREATE TABLE user_plugin_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR(192) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);

CREATE INDEX idx_user_plugin_states_user_enabled ON user_plugin_states(user_id, enabled);

-- 3. plugin_ratings 表
CREATE TABLE plugin_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR(192) NOT NULL,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);

CREATE INDEX idx_plugin_ratings_plugin ON plugin_ratings(plugin_name);
```
