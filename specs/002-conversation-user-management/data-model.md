# Data Model: 对话历史与用户管理

**Feature**: 002-conversation-user-management
**Date**: 2026-02-08

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    User      │       │   Conversation   │       │  LangGraph       │
├──────────────┤       ├──────────────────┤       │  Thread          │
│ id (PK)      │───┐   │ id (PK)          │       ├──────────────────┤
│ username     │   │   │ thread_id (FK)───│───────│ thread_id (PK)   │
│ password_hash│   └──►│ user_id (FK)     │       │ (managed by      │
│ role         │       │ title            │       │  LangGraph)      │
│ status       │       │ created_at       │       └──────────────────┘
│ created_at   │       │ updated_at       │
└──────────────┘       │ is_deleted       │
                       └──────────────────┘
```

---

## 1. User (用户)

用户实体，用于认证和权限控制。

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 用户唯一标识符 |
| username | VARCHAR(20) | UNIQUE, NOT NULL | 用户名 (3-20字符, 字母数字下划线) |
| password_hash | TEXT | NOT NULL | bcrypt 哈希后的密码 |
| role | user_role | NOT NULL | 角色: 'admin' 或 'user' |
| status | user_status | NOT NULL, DEFAULT 'active' | 状态: 'active' 或 'disabled' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |

### Validation Rules

- **username**:
  - 长度: 3-20 字符
  - 格式: `^[a-zA-Z][a-zA-Z0-9_]*$` (字母开头，只含字母数字下划线)
  - 唯一性: 不区分大小写 (使用 CITEXT 或 LOWER() 索引)
- **role**: 枚举值 `['admin', 'user']`
- **status**: 枚举值 `['active', 'disabled']`

### PostgreSQL Schema

```sql
-- 创建枚举类型
CREATE TYPE user_role AS ENUM ('admin', 'user');
CREATE TYPE user_status AS ENUM ('active', 'disabled');

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(20) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'user',
    status user_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建索引（不区分大小写的用户名查询）
CREATE UNIQUE INDEX idx_users_username_lower ON users(LOWER(username));
CREATE INDEX idx_users_status ON users(status);
```

---

## 2. Conversation (对话)

对话元数据，关联用户和 LangGraph 线程。

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 对话唯一标识符 |
| thread_id | VARCHAR(8) | NOT NULL | LangGraph 线程 ID |
| user_id | UUID | FK → users.id, NOT NULL | 所属用户 |
| title | VARCHAR(50) | NOT NULL | 对话标题 (最长 50 字符) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 最后更新时间 |
| is_deleted | BOOLEAN | NOT NULL, DEFAULT FALSE | 软删除标记 |

### Validation Rules

- **title**:
  - 长度: 1-50 字符
  - 自动生成: 取第一条消息前 50 字符
  - 可手动修改
- **thread_id**: 8 字符十六进制字符串

### PostgreSQL Schema

```sql
-- 创建对话表
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(8) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- 创建索引
CREATE INDEX idx_conversations_user ON conversations(user_id) WHERE NOT is_deleted;
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC) WHERE NOT is_deleted;
CREATE INDEX idx_conversations_thread ON conversations(thread_id);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
```

---

## 3. Session (会话) - JWT 内嵌

会话信息直接编码在 JWT token 中，无需独立表。

### JWT Payload Structure

```json
{
  "sub": "user_id",
  "username": "admin",
  "role": "admin",
  "iat": 1707350400,
  "exp": 1707436800
}
```

### Token Lifecycle

| State | Condition | Action |
|-------|-----------|--------|
| Valid | exp > now | 允许请求，自动续期 |
| Expired | exp <= now | 返回 401，重定向登录 |
| Invalid | 签名不匹配 | 返回 401，清除 cookie |

---

## State Transitions

### User.status

```
┌──────────┐  disable()  ┌──────────┐
│  active  │ ──────────► │ disabled │
└──────────┘             └──────────┘
      ▲                        │
      │      enable()          │
      └────────────────────────┘
```

### Conversation Lifecycle

```
         create()           first_message()        delete()
[New Thread] ──────► [Created] ──────────► [Active] ──────► [Deleted]
                         │                     │
                         │    update_title()   │
                         └──────────◄──────────┘
```

---

## Data Integrity Rules

### Business Rules

1. **最后一个管理员保护**: 禁止删除或禁用系统中唯一的活跃管理员
2. **自我保护**: 用户不能删除或禁用自己的账户
3. **对话隔离**: 用户只能访问自己的对话列表
4. **级联删除**: 删除用户时自动删除其所有对话

### Referential Integrity

| Parent | Child | On Delete |
|--------|-------|-----------|
| users | conversations | CASCADE |

---

## Migration Strategy

### From Current State

当前系统有两个 SQLite 数据库：

| 数据库 | 用途 | 迁移策略 |
|--------|------|----------|
| `threads.db` | LangGraph checkpoints | **迁移到 PostgreSQL** |
| `chinook.db` | SQL Agent 示例数据 | **保留为 SQLite**（只读示例数据） |

### 现有 threads.db Schema

```sql
-- checkpoints 表（需要迁移）
CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BLOB,
    metadata BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- writes 表（需要迁移）
CREATE TABLE writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
```

### Migration Steps

1. **部署 PostgreSQL**: 确保 PostgreSQL 服务可用
2. **创建数据库**: 创建 sunnyagent 数据库和用户
3. **初始化 Alembic**: 运行 `uv run alembic upgrade head` 创建业务表
4. **运行数据迁移脚本**: 执行 `scripts/migrate_sqlite_to_pg.py`
   - 迁移 SQLite 中的 LangGraph checkpoint 数据到 PostgreSQL
   - 创建默认管理员账户
5. **更新环境变量**: 配置 `DATABASE_URL`
6. **验证并删除**: 验证成功后删除 `threads.db`

### Schema Management with Alembic

使用 Alembic 管理业务表（users, conversations）的 schema 变更：

```
backend/
├── migrations/
│   ├── versions/
│   │   ├── 001_initial_schema.py    # 创建 users, conversations 表
│   │   └── ...
│   ├── env.py
│   └── script.py.mako
└── alembic.ini
```

**LangGraph checkpoint 表**由 `langgraph-checkpoint-postgres` 自动管理，不纳入 Alembic。

### Migration Script Outline

```python
# scripts/migrate_sqlite_to_pg.py
import asyncio
import aiosqlite
import asyncpg
import os

async def migrate():
    # 1. 连接两个数据库
    sqlite_conn = await aiosqlite.connect("threads.db")
    pg_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])

    # 2. 迁移 checkpoints 表
    async with sqlite_conn.execute("SELECT * FROM checkpoints") as cursor:
        rows = await cursor.fetchall()
        async with pg_pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO checkpoints
                   (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                rows
            )

    # 3. 迁移 writes 表
    async with sqlite_conn.execute("SELECT * FROM writes") as cursor:
        rows = await cursor.fetchall()
        async with pg_pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO writes
                   (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                rows
            )

    # 4. 创建默认管理员（通过 Alembic 或应用启动逻辑）
    print(f"Migrated {len(rows)} checkpoint records")

if __name__ == "__main__":
    asyncio.run(migrate())
```

### Backward Compatibility

- `threads.db` 迁移后删除，不保留向后兼容
- `chinook.db` 保留，SQL Agent 继续使用 SQLite 查询示例数据
- 现有 `/api/chat` 端点在无认证时返回 401
- LangGraph 使用 `langgraph-checkpoint-postgres` 替代 SQLite checkpointer
- 已有的 thread_id 在迁移后继续有效（但需要创建 conversation 记录才能在列表显示）

### LangGraph Checkpoint Tables (PostgreSQL)

`langgraph-checkpoint-postgres` 会自动创建以下表：

```sql
-- 由 langgraph-checkpoint-postgres 自动管理，schema 可能略有不同
CREATE TABLE checkpoints (
    thread_id VARCHAR NOT NULL,
    checkpoint_ns VARCHAR NOT NULL DEFAULT '',
    checkpoint_id VARCHAR NOT NULL,
    parent_checkpoint_id VARCHAR,
    type VARCHAR,
    checkpoint BYTEA,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE writes (
    thread_id VARCHAR NOT NULL,
    checkpoint_ns VARCHAR NOT NULL DEFAULT '',
    checkpoint_id VARCHAR NOT NULL,
    task_id VARCHAR NOT NULL,
    idx INTEGER NOT NULL,
    channel VARCHAR NOT NULL,
    type VARCHAR,
    value BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
```
