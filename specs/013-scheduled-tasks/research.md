# Research: 定时任务功能 (Scheduled Tasks)

**Feature**: 013-scheduled-tasks
**Date**: 2026-02-22

## Research Questions

1. APScheduler + PostgreSQL job store 配置
2. FastAPI 生命周期集成
3. 并发执行限制实现
4. 重试逻辑实现
5. 任务超时处理
6. Cron 触发器类型配置

---

## 1. APScheduler + PostgreSQL Job Store

### Decision
使用 APScheduler 4.x 的 `SQLAlchemyDataStore` 配合 `asyncpg` 异步驱动，实现任务持久化。

### Rationale
- APScheduler 4.x 原生支持 async/await，与 FastAPI 异步架构匹配
- `SQLAlchemyDataStore` 自动创建必要的表结构，简化部署
- 复用现有 PostgreSQL 数据库，无需额外基础设施
- 支持跨服务器重启的任务恢复

### Configuration Pattern
```python
from sqlalchemy.ext.asyncio import create_async_engine
from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore

engine = create_async_engine("postgresql+asyncpg://...")
data_store = SQLAlchemyDataStore(engine)
scheduler = AsyncScheduler(data_store=data_store)
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Celery Beat | 需要额外的 Redis/RabbitMQ 基础设施 |
| System cron | 不支持动态任务添加/删除，难以与应用集成 |
| APScheduler MemoryJobStore | 不支持持久化，服务重启后任务丢失 |

---

## 2. FastAPI 生命周期集成

### Decision
使用 FastAPI lifespan context manager 管理 APScheduler 的启动和关闭。

### Rationale
- 官方推荐的现代化生命周期管理方式
- 确保 scheduler 在应用启动时初始化，关闭时优雅停止
- 避免使用已废弃的 `on_event` 装饰器

### Implementation Pattern
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 初始化并启动 scheduler
    await scheduler.start_in_background()
    yield
    # Shutdown: 优雅停止 scheduler
    await scheduler.stop()

app = FastAPI(lifespan=lifespan)
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| `@app.on_event("startup")` | 已废弃，不推荐使用 |
| 手动启动线程 | 不够优雅，可能导致资源泄漏 |

---

## 3. 并发执行限制

### Decision
使用 APScheduler 的 `max_concurrent_jobs` 参数限制全局并发数为 5。

### Rationale
- APScheduler 原生支持，无需额外代码
- 防止资源耗尽，保护服务器稳定性
- 超出限制的任务自动排队等待

### Configuration Pattern
```python
scheduler = AsyncScheduler(
    data_store=data_store,
    max_concurrent_jobs=5
)
```

### Task-Level Configuration
```python
await scheduler.add_schedule(
    task_func,
    trigger,
    max_running_jobs=1  # 单任务不允许重叠执行
)
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| 自定义信号量 | 增加复杂性，APScheduler 已内置支持 |
| 无限制 | 可能导致资源耗尽 |

---

## 4. 重试逻辑

### Decision
在任务执行函数内实现重试逻辑，1 次重试，5 分钟延迟。

### Rationale
- APScheduler 不内置重试机制
- 在函数内实现更灵活，可自定义重试条件
- 避免复杂的事件监听机制

### Implementation Pattern
```python
async def execute_task_with_retry(task_id: str, prompt: str):
    MAX_RETRIES = 1
    RETRY_DELAY = 5 * 60  # 5 minutes

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await execute_ai_prompt(task_id, prompt)
            await save_result(task_id, result, "success")
            return
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                await save_result(task_id, None, "failed", str(e))
                raise
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| APScheduler 事件监听重新调度 | 更复杂，需要额外的任务 ID 管理 |
| 立即重试 | 对于网络/API 错误无效，需要等待恢复 |

---

## 5. 任务超时处理

### Decision
使用 `asyncio.wait_for()` 实现 15 分钟任务超时。

### Rationale
- Python 标准库原生支持
- 与 async/await 模式完美配合
- 可精确控制超时时间

### Implementation Pattern
```python
async def execute_with_timeout(task_id: str, prompt: str):
    TIMEOUT = 15 * 60  # 15 minutes

    try:
        result = await asyncio.wait_for(
            execute_ai_prompt(task_id, prompt),
            timeout=TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        await save_result(task_id, None, "timeout")
        raise
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Threading timeout | 不适用于 async 函数 |
| APScheduler misfire_grace_time | 这是错过执行的宽限期，不是执行超时 |

---

## 6. Cron 触发器配置

### Decision
使用 APScheduler CronTrigger 和 DateTrigger 支持四种计划类型。

### Schedule Type Mapping

| 计划类型 | APScheduler 触发器 | 配置示例 |
|---------|-------------------|---------|
| 不重复 (once) | DateTrigger | `DateTrigger(run_date=datetime(2024,12,25,9,0))` |
| 每天 (daily) | CronTrigger | `CronTrigger(hour=9, minute=0)` |
| 每周 (weekly) | CronTrigger | `CronTrigger(day_of_week="mon,wed,fri", hour=9, minute=0)` |
| 每月 (monthly) | CronTrigger | `CronTrigger(day="1,15", hour=9, minute=0)` |

### Weekly Multi-Day Selection
```python
# 支持多选：周一、周三、周五
CronTrigger(day_of_week="mon,wed,fri", hour=9, minute=0)
```

### Monthly Multi-Day Selection
```python
# 支持多选：1号、15号
CronTrigger(day="1,15", hour=9, minute=0)

# 每月最后一天
CronTrigger(day="last", hour=9, minute=0)
```

### End Date Support
```python
CronTrigger(
    hour=9, minute=0,
    end_date=datetime(2024, 12, 31)  # 到期后自动停止
)
```

### Rationale
- APScheduler 内置丰富的 cron 语法支持
- 支持 `last` 关键字处理每月最后一天
- 支持 `end_date` 参数实现到期日期

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| 自定义 trigger | APScheduler 内置已满足需求 |
| 存储 cron 表达式字符串 | 不如直接使用 CronTrigger 参数灵活 |

---

## Implementation Recommendations

### 1. 模块结构
```
backend/scheduled_tasks/
├── scheduler.py      # APScheduler 初始化和管理
├── executor.py       # 任务执行逻辑（含超时和重试）
├── triggers.py       # 触发器工厂函数
├── service.py        # 业务逻辑层
├── database.py       # 数据库操作
└── router.py         # API 端点
```

### 2. 任务 ID 命名规范
使用 `{user_id}:{task_id}` 格式，便于管理和查询。

### 3. Coalesce Policy
使用 `CoalescePolicy.latest`，服务重启后只执行最近一次错过的任务。

### 4. 冲突策略
使用 `ConflictPolicy.replace`，更新任务时替换现有调度。

### 5. Langfuse 集成
在 `execute_task_with_retry` 中使用现有 AIME 的追踪模式：
```python
from langfuse.decorators import observe

@observe(name="scheduled_task_execution")
async def execute_ai_prompt(task_id: str, prompt: str):
    ...
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| apscheduler | >=4.0.0 | 任务调度 |
| sqlalchemy[asyncio] | >=2.0 | 异步数据库访问 |
| asyncpg | >=0.27 | PostgreSQL 异步驱动 |

**Note**: 确保与现有 `asyncpg` 版本兼容。
