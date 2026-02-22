# Data Model: 定时任务功能 (Scheduled Tasks)

**Feature**: 013-scheduled-tasks
**Date**: 2026-02-22

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        users                                │
│  (existing table)                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   scheduled_tasks                           │
│  - id (UUID, PK)                                           │
│  - user_id (UUID, FK → users.id)                           │
│  - title (VARCHAR(255), NOT NULL)                          │
│  - schedule_type (ENUM, NOT NULL)                          │
│  - schedule_config (JSONB, NOT NULL)                       │
│  - expiry_date (TIMESTAMP, NULL)                           │
│  - enabled (BOOLEAN, DEFAULT TRUE)                         │
│  - status (ENUM, DEFAULT 'scheduled')                      │
│  - script_file_path (VARCHAR(500), NOT NULL)               │
│  - apscheduler_job_id (VARCHAR(100), NULL)                 │
│  - created_at (TIMESTAMP, NOT NULL)                        │
│  - updated_at (TIMESTAMP, NOT NULL)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   task_executions                           │
│  - id (UUID, PK)                                           │
│  - task_id (UUID, FK → scheduled_tasks.id)                 │
│  - execution_time (TIMESTAMP, NOT NULL)                    │
│  - status (ENUM, NOT NULL)                                 │
│  - duration_ms (INTEGER, NULL)                             │
│  - retry_count (INTEGER, DEFAULT 0)                        │
│  - log_file_path (VARCHAR(500), NULL)                      │
│  - conversation_id (UUID, FK → conversations.id, NULL)     │
│  - error_message (TEXT, NULL)                              │
│  - created_at (TIMESTAMP, NOT NULL)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Entities

### ScheduledTask (scheduled_tasks)

定时任务的核心实体，存储任务配置和调度信息。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | 任务唯一标识符 |
| user_id | UUID | FK → users.id, NOT NULL | 创建任务的用户 |
| title | VARCHAR(255) | NOT NULL | 任务标题 |
| schedule_type | schedule_type_enum | NOT NULL | 计划类型 |
| schedule_config | JSONB | NOT NULL | 计划配置详情 |
| expiry_date | TIMESTAMP | NULL | 任务到期日期（可选） |
| enabled | BOOLEAN | DEFAULT TRUE | 启用状态 |
| status | task_status_enum | DEFAULT 'scheduled' | 任务状态 |
| script_file_path | VARCHAR(500) | NOT NULL | 脚本文件相对路径 |
| apscheduler_job_id | VARCHAR(100) | NULL | APScheduler 任务 ID |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | 更新时间 |

**Indexes**:
- `idx_scheduled_tasks_user_id` on `user_id`
- `idx_scheduled_tasks_status` on `status`
- `idx_scheduled_tasks_enabled` on `enabled`

**Enums**:
```sql
CREATE TYPE schedule_type_enum AS ENUM ('once', 'daily', 'weekly', 'monthly');
CREATE TYPE task_status_enum AS ENUM ('scheduled', 'completed', 'expired', 'error');
```

**schedule_config JSONB Structure**:
```json
// once
{
  "run_date": "2024-12-25",
  "run_time": "09:00"
}

// daily
{
  "time": "09:00"
}

// weekly
{
  "days_of_week": ["mon", "wed", "fri"],
  "time": "09:00"
}

// monthly
{
  "days_of_month": [1, 15],
  "time": "09:00"
}
```

---

### TaskExecution (task_executions)

记录每次任务执行的历史和结果。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | 执行记录唯一标识符 |
| task_id | UUID | FK → scheduled_tasks.id, NOT NULL, ON DELETE CASCADE | 所属任务 |
| execution_time | TIMESTAMP | NOT NULL | 计划执行时间 |
| status | execution_status_enum | NOT NULL | 执行状态 |
| duration_ms | INTEGER | NULL | 执行耗时（毫秒） |
| retry_count | INTEGER | DEFAULT 0 | 重试次数 |
| log_file_path | VARCHAR(500) | NULL | 日志文件相对路径 |
| conversation_id | UUID | FK → conversations.id, NULL | 关联的对话 ID |
| error_message | TEXT | NULL | 错误信息 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | 记录创建时间 |

**Indexes**:
- `idx_task_executions_task_id` on `task_id`
- `idx_task_executions_execution_time` on `execution_time`
- `idx_task_executions_status` on `status`

**Enums**:
```sql
CREATE TYPE execution_status_enum AS ENUM ('pending', 'running', 'success', 'failed', 'timeout');
```

---

## State Transitions

### ScheduledTask Status

```
                 ┌──────────────┐
                 │  scheduled   │ ◀─────── 创建任务
                 └──────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌───────────┐ ┌───────────────┐
│   completed   │ │  expired  │ │     error     │
│  (一次性执行)  │ │ (到期日期) │ │  (脚本缺失)   │
└───────────────┘ └───────────┘ └───────────────┘
```

**Transition Rules**:
- `scheduled` → `completed`: 一次性任务执行完成
- `scheduled` → `expired`: 到期日期已过
- `scheduled` → `error`: 脚本文件缺失或其他配置错误

### TaskExecution Status

```
┌──────────────┐
│   pending    │ ◀─────── 创建执行记录
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   running    │ ◀─────── 开始执行
└──────┬───────┘
       │
       ├───────────────┬───────────────┐
       │               │               │
       ▼               ▼               ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│  success  │   │  failed   │   │  timeout  │
└───────────┘   └───────────┘   └───────────┘
```

**Transition Rules**:
- `pending` → `running`: 任务开始执行
- `running` → `success`: 执行成功
- `running` → `failed`: 执行失败（包括重试后仍失败）
- `running` → `timeout`: 执行超时（15分钟）

---

## File System Structure

```
data/
└── scheduled_tasks/
    └── {user_id}/
        ├── scripts/
        │   ├── {task_id}.txt      # 脚本内容（提示词）
        │   └── ...
        └── logs/
            └── {task_id}/
                ├── {execution_id}.log
                └── ...
```

**Path Generation Rules**:
- Script path: `data/scheduled_tasks/{user_id}/scripts/{task_id}.txt`
- Log path: `data/scheduled_tasks/{user_id}/logs/{task_id}/{execution_id}.log`

**File Constraints**:
- Script file max size: 64KB
- Script encoding: UTF-8
- Log retention: 90 days

---

## Validation Rules

### ScheduledTask
- `title`: 1-255 characters, required
- `schedule_type`: must be one of enum values
- `schedule_config`: must match schema for schedule_type
- `expiry_date`: must be in the future (if provided)

### schedule_config Validation
| Type | Required Fields | Validation |
|------|-----------------|------------|
| once | run_date, run_time | run_date must be in future |
| daily | time | time format HH:MM |
| weekly | days_of_week, time | days_of_week: array of mon-sun |
| monthly | days_of_month, time | days_of_month: array of 1-31 |

### Script Content
- Required, non-empty
- Max length: 65536 bytes (64KB)
- UTF-8 encoded

---

## Relationships

| Parent | Child | Relationship | ON DELETE |
|--------|-------|--------------|-----------|
| users | scheduled_tasks | 1:N | CASCADE |
| scheduled_tasks | task_executions | 1:N | CASCADE |
| conversations | task_executions | 1:N | SET NULL |

---

## Migration Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| users table | Existing | FK reference |
| conversations table | Existing | FK reference |
| APScheduler tables | Auto-created | By SQLAlchemyDataStore |

---

## APScheduler Integration

APScheduler 使用 `SQLAlchemyDataStore` 自动创建以下表（由库管理，不在应用迁移中）：

- `apscheduler_jobs` - 存储调度任务
- `apscheduler_schedules` - 存储调度计划
- `apscheduler_job_results` - 存储执行结果

**与应用数据的关联**:
- `scheduled_tasks.apscheduler_job_id` → APScheduler 内部 job ID
- 用于启用/禁用任务时操作 APScheduler
