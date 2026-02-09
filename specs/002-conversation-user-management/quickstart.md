# Quickstart: 对话历史与用户管理

**Feature**: 002-conversation-user-management
**Date**: 2026-02-08

## Prerequisites

- Python 3.11+
- Node.js 18+
- uv (Python package manager)
- npm
- **PostgreSQL 14+** (新增)

## Environment Setup

### 1. Setup PostgreSQL

```bash
# macOS (使用 Homebrew)
brew install postgresql@14
brew services start postgresql@14

# 创建数据库和用户
createdb sunnyagent
psql -d sunnyagent -c "CREATE USER sunnyagent WITH PASSWORD 'your_password';"
psql -d sunnyagent -c "GRANT ALL PRIVILEGES ON DATABASE sunnyagent TO sunnyagent;"
psql -d sunnyagent -c "GRANT ALL ON SCHEMA public TO sunnyagent;"
```

### 2. Configure Environment Variables

在项目根目录的 `.env` 文件中添加以下配置：

```bash
# 必需：PostgreSQL 连接字符串
DATABASE_URL=postgresql://sunnyagent:your_password@localhost:5432/sunnyagent

# 必需：默认管理员密码
ADMIN_PASSWORD=your_secure_password_here

# 可选：管理员用户名（默认: admin）
ADMIN_USERNAME=admin

# 可选：JWT 密钥（默认: 自动生成）
JWT_SECRET_KEY=your_jwt_secret_here

# 可选：JWT 有效期（秒，默认: 86400 = 24小时）
JWT_EXPIRATION=86400
```

### 3. Install Dependencies

```bash
# Backend - 安装新增的 PostgreSQL 依赖
uv sync

# Frontend - 无新增依赖
cd frontend && npm install
```

## Database Initialization

### 首次部署（无历史数据）

```bash
# 运行 Alembic 迁移，创建业务表（users, conversations）
uv run alembic upgrade head
```

LangGraph checkpoint 表会在首次启动时由 `langgraph-checkpoint-postgres` 自动创建。

### 数据迁移（从现有 SQLite）

如果有现有的 `threads.db` 数据需要迁移：

```bash
# 1. 先运行 Alembic 创建业务表
uv run alembic upgrade head

# 2. 运行数据迁移脚本（迁移 LangGraph checkpoints）
uv run python scripts/migrate_sqlite_to_pg.py

# 3. 验证迁移成功后删除 SQLite 文件
rm threads.db
```

**注意**: `chinook.db`（SQL Agent 示例数据库）保留不变，无需迁移。

## Schema Management with Alembic

### 常用命令

```bash
# 查看当前迁移版本
uv run alembic current

# 查看迁移历史
uv run alembic history

# 执行所有待执行的迁移
uv run alembic upgrade head

# 回滚一个版本
uv run alembic downgrade -1

# 创建新的迁移文件（开发时使用）
uv run alembic revision --autogenerate -m "description"
```

## Running the Application

### Start Backend

```bash
uv run uvicorn backend.main:app --reload --port 8008
```

首次启动时，系统会：
1. 连接 PostgreSQL 并创建必要的表结构
2. 创建默认管理员账户（使用环境变量中的凭据）

### Start Frontend

```bash
cd frontend && npm run dev
```

前端开发服务器启动在 http://localhost:3008

## First Login

1. 打开浏览器访问 http://localhost:3008
2. 使用默认管理员凭据登录：
   - 用户名: `admin`（或 ADMIN_USERNAME 配置的值）
   - 密码: 环境变量 `ADMIN_PASSWORD` 的值

## Quick Verification

### 1. 验证 PostgreSQL 连接

```bash
# 检查数据库表
psql $DATABASE_URL -c "\dt"

# 应该看到：users, conversations, 以及 LangGraph 的 checkpoint 表
```

### 2. 验证登录功能

```bash
# 登录获取 cookie
curl -X POST http://localhost:8008/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' \
  -c cookies.txt

# 验证登录状态
curl http://localhost:8008/api/auth/me \
  -b cookies.txt
```

### 3. 验证对话管理

```bash
# 创建新对话
curl -X POST http://localhost:8008/api/conversations \
  -b cookies.txt

# 获取对话列表
curl http://localhost:8008/api/conversations \
  -b cookies.txt
```

### 4. 验证用户管理（需要管理员权限）

```bash
# 获取用户列表
curl http://localhost:8008/api/users \
  -b cookies.txt

# 创建新用户
curl -X POST http://localhost:8008/api/users \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123", "role": "user"}' \
  -b cookies.txt
```

## New Dependencies

### Backend (pyproject.toml)

```toml
# 新增依赖
"passlib[bcrypt]>=1.7.4",               # 密码哈希
"python-jose[cryptography]>=3.3.0",      # JWT 处理
"asyncpg>=0.29.0",                       # PostgreSQL 异步驱动
"langgraph-checkpoint-postgres>=2.0.0",  # LangGraph PostgreSQL checkpointer
"alembic>=1.13.0",                       # 数据库迁移管理
```

### Removed Dependencies

```toml
# 移除依赖
"langgraph-checkpoint-sqlite>=2.0.0",  # 不再使用（threads.db 迁移到 PG）
```

### Retained Dependencies

```toml
# 保留依赖（chinook.db 仍使用 SQLite）
"aiosqlite>=0.20.0",  # SQL Agent 查询 chinook.db 需要
```

### Frontend (package.json)

无新增依赖，继续使用现有的 React 和 lucide-react。

## Database Schema

PostgreSQL 中会创建以下表：

- `users` - 用户信息表
- `conversations` - 对话元数据表
- LangGraph checkpoint 相关表（由 `langgraph-checkpoint-postgres` 自动管理）

## Troubleshooting

### PostgreSQL 连接失败

- 检查 PostgreSQL 服务是否运行: `brew services list` 或 `systemctl status postgresql`
- 检查 `DATABASE_URL` 格式是否正确
- 确认数据库用户有足够权限

### 登录失败 - "Invalid credentials"

- 检查 `.env` 文件中 `ADMIN_PASSWORD` 是否正确设置
- 确认首次启动时没有错误日志

### 对话列表为空

- 对话需要用户登录后创建
- 迁移后的历史对话需要手动关联用户

### 用户管理入口不可见

- 确认使用管理员账户登录
- 普通用户无法访问系统管理功能

### JWT 相关错误

- 检查 `JWT_SECRET_KEY` 是否配置
- 如果更换了密钥，所有用户需要重新登录

### 迁移脚本失败

- 确保 `threads.db` 文件存在且可读
- 确保 PostgreSQL 连接正常
- 查看脚本输出的详细错误信息
