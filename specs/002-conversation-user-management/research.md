# Research: 对话历史与用户管理

**Feature**: 002-conversation-user-management
**Date**: 2026-02-08

## 1. 认证方案

### Decision: JWT + HttpOnly Cookie

使用 JWT (JSON Web Token) 存储在 HttpOnly Cookie 中进行会话管理。

### Rationale

1. **安全性**: HttpOnly Cookie 防止 XSS 攻击窃取 token
2. **简洁性**: 无需额外的 session 存储（JWT 自包含）
3. **兼容性**: 与现有 FastAPI 架构无缝集成
4. **无状态**: 服务端无需存储会话状态，重启不影响已登录用户

### Alternatives Considered

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| Session + Redis | 可立即失效 | 需要额外依赖 | 违反简洁性原则 |
| JWT in localStorage | 前端控制方便 | XSS 风险高 | 安全性不足 |
| OAuth2 | 标准化、可扩展 | 过于复杂 | 超出当前需求 |

### Implementation Notes

- Token 有效期: 24 小时（可通过环境变量配置）
- 密码哈希: 使用 `passlib` 的 `bcrypt` 算法
- 刷新策略: 每次请求自动延长 token 有效期

---

## 2. 数据库方案

### Decision: PostgreSQL（完全替代 SQLite）

使用 PostgreSQL 作为唯一数据库，迁移现有 SQLite 数据并完全放弃 SQLite。

### Rationale

1. **生产就绪**: PostgreSQL 是企业级数据库，支持高并发和大数据量
2. **功能丰富**: 支持 JSON 类型、全文搜索、事务隔离级别等高级功能
3. **统一存储**: 用户、会话、对话、LangGraph checkpoints 全部存储在同一数据库
4. **可扩展性**: 未来可轻松扩展到集群部署

### Alternatives Considered

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 保留 SQLite | 无需迁移 | 不适合生产、并发受限 | 放弃 |
| SQLite + PostgreSQL 混合 | 渐进迁移 | 维护两套连接、复杂度高 | 不采用 |
| MySQL | 也是生产级 | 社区版功能受限 | PostgreSQL 更适合 |

### Implementation Notes

- 使用 `asyncpg` 作为异步 PostgreSQL 驱动
- 使用 `langgraph-checkpoint-postgres` 替代 SQLite checkpointer
- 迁移脚本: 一次性将 threads.db 数据导入 PostgreSQL
- 环境变量: `DATABASE_URL=postgresql://user:pass@host:5432/dbname`
- **chinook.db 保留**: SQL Agent 使用的示例音乐数据库保留为 SQLite（只读示例数据）

### 需要迁移的数据

| 来源 | 表 | 目标 | 说明 |
|------|-----|------|------|
| threads.db | checkpoints | PostgreSQL | LangGraph 对话状态快照 |
| threads.db | writes | PostgreSQL | LangGraph 增量写入 |
| chinook.db | * | 不迁移 | 保留为 SQLite，SQL Agent 只读使用 |

---

## 8. 数据模型管理（Schema Migration）

### Decision: Alembic 数据库迁移

使用 Alembic 管理 PostgreSQL schema 变更，支持版本化迁移和回滚。

### Rationale

1. **版本控制**: Schema 变更纳入代码版本管理
2. **可回滚**: 支持升级和降级操作
3. **团队协作**: 多人开发时 schema 变更可追踪
4. **生产安全**: 避免手动执行 DDL 语句

### Alternatives Considered

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 手动 SQL 脚本 | 简单 | 无版本管理、易出错 | 不可靠 |
| 启动时自动创建 | 零配置 | 无法处理 schema 变更 | 仅适合初始化 |
| Django ORM migrations | 功能强大 | 需要 Django | 不适合 FastAPI |

### Implementation Notes

- 新增依赖: `alembic>=1.13.0`
- 迁移目录: `backend/migrations/`
- 配置文件: `alembic.ini`
- 使用 async 模式支持 asyncpg

### 目录结构

```
backend/
├── migrations/
│   ├── versions/           # 迁移版本文件
│   │   ├── 001_initial_schema.py
│   │   └── 002_add_user_fields.py
│   ├── env.py              # Alembic 环境配置
│   └── script.py.mako      # 迁移脚本模板
└── alembic.ini             # Alembic 配置
```

### 常用命令

```bash
# 创建新迁移
uv run alembic revision --autogenerate -m "add users table"

# 执行迁移
uv run alembic upgrade head

# 回滚一个版本
uv run alembic downgrade -1

# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history
```

---

## 3. 对话持久化策略

### Decision: 独立 Conversations 表 + 关联 threads

创建独立的 conversations 表存储对话元数据，通过 thread_id 关联现有的 LangGraph 线程数据。

### Rationale

1. **兼容性**: 不修改 LangGraph 的 checkpoint 表结构
2. **灵活性**: 可添加用户归属、标题、创建时间等元数据
3. **查询效率**: 列表查询只需访问 conversations 表

### Data Relationship

```
User (1) ──── (N) Conversation ──── (1) LangGraph Thread (PostgreSQL checkpoints)
              │
              └── thread_id (外键指向 checkpoints 表)
```

### Implementation Notes

- 每次创建新线程时同步创建 conversation 记录
- 对话标题在第一条消息后自动生成（取前 50 字符）
- 删除对话时保留线程数据（软删除）或级联删除
- LangGraph checkpoints 使用 `langgraph-checkpoint-postgres`

---

## 4. 前端路由方案

### Decision: 基于状态的条件渲染

使用 React 状态管理控制页面显示，不引入 React Router。

### Rationale

1. **简洁性**: 当前只有 3 个视图（登录、主界面、用户管理）
2. **复杂度低**: 无需学习路由库 API
3. **与现有代码一致**: 现有项目未使用路由库

### Alternatives Considered

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| React Router | 标准方案、URL 可分享 | 增加依赖和复杂度 | 3 个页面不需要 |
| 自定义路由 | 完全控制 | 重新发明轮子 | 不必要 |

### Implementation Notes

- 使用 `useState` 管理当前视图: `'login' | 'main' | 'admin'`
- 认证状态存储在 Context 中
- 页面刷新后通过 cookie 自动恢复登录状态

---

## 5. 左侧导航栏设计

### Decision: 可收缩 Sidebar 组件

实现独立的 Sidebar 组件，支持展开/收缩状态。

### Layout Structure

```
┌─────────────────────────────────────────┐
│ ┌─────────┐ ┌─────────────────────────┐ │
│ │ Sidebar │ │     Main Content        │ │
│ │ (280px) │ │     (flex: 1)           │ │
│ │         │ │                         │ │
│ │ - Logo  │ │                         │ │
│ │ - New   │ │                         │ │
│ │ - List  │ │                         │ │
│ │ - Admin │ │                         │ │
│ │ - User  │ │                         │ │
│ └─────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Collapsed State

- 收缩宽度: 64px
- 只显示图标
- 鼠标悬停显示 tooltip

### Implementation Notes

- 使用 CSS variables 定义宽度
- 动画过渡: 0.2s ease
- 状态持久化到 localStorage

---

## 6. 默认管理员初始化

### Decision: 环境变量配置 + 启动时创建

通过环境变量配置默认管理员凭据，应用启动时自动创建。

### Environment Variables

```bash
ADMIN_USERNAME=admin          # 默认: admin
ADMIN_PASSWORD=changeme       # 必须配置，无默认值
```

### Rationale

1. **安全性**: 密码不硬编码在代码中
2. **灵活性**: 不同环境可配置不同凭据
3. **简单性**: 无需额外的初始化脚本

### Implementation Notes

- 启动时检查是否存在管理员账户
- 如不存在，使用环境变量创建
- 如 ADMIN_PASSWORD 未设置，记录警告但不阻止启动（开发环境友好）

---

## 7. API 认证中间件

### Decision: FastAPI Dependency Injection

使用 FastAPI 的依赖注入系统实现认证检查。

### Pattern

```python
async def get_current_user(request: Request) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401)
    return decode_and_validate(token)

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403)
    return user

# Usage
@app.get("/api/users")
async def list_users(user: User = Depends(require_admin)):
    ...
```

### Rationale

1. **清晰性**: 每个端点的权限要求一目了然
2. **可测试性**: 依赖可以被 mock
3. **FastAPI 原生**: 无需额外中间件库

### Public vs Protected Endpoints

| 类别 | 端点 | 认证要求 |
|------|------|----------|
| Public | POST /api/auth/login | 无 |
| Protected | GET /api/conversations | 登录用户 |
| Protected | GET /api/chat | 登录用户 |
| Admin Only | GET /api/users | 管理员 |
| Admin Only | POST /api/users | 管理员 |

---

## Summary

主要技术选型（PostgreSQL 替代 SQLite 以获得生产级可靠性）：

1. **认证**: JWT + HttpOnly Cookie
2. **存储**: PostgreSQL（替代 threads.db；chinook.db 保留为示例数据）
3. **Schema 管理**: Alembic（版本化数据库迁移）
4. **前端路由**: 状态管理（无 React Router）
5. **密码**: bcrypt 哈希
6. **会话**: 24 小时有效期，自动续期
7. **数据迁移**: 提供 threads.db → PostgreSQL 迁移脚本

**新增依赖**:
- `asyncpg` - PostgreSQL 异步驱动
- `langgraph-checkpoint-postgres` - LangGraph PostgreSQL checkpointer
- `alembic` - 数据库迁移管理
- `passlib[bcrypt]` - 密码哈希
- `python-jose[cryptography]` - JWT 处理

**保留依赖**:
- `aiosqlite` - SQL Agent 查询 chinook.db 需要
