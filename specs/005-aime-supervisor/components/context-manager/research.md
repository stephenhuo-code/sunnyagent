# Research: Context Manager

**Date**: 2026-02-16
**Feature**: ContextManager for AIME task context management

## Research Topics

### 1. LRU Cache Implementation

**Decision**: 使用 Python 标准库 `collections.OrderedDict` 实现 LRU Cache

**Rationale**:
- 无需额外依赖
- `OrderedDict.move_to_end()` 提供 O(1) 的 LRU 更新
- 简单可靠，易于测试

**Alternatives considered**:
- `cachetools.LRUCache`: 增加依赖，功能过剩
- `functools.lru_cache`: 不适合异步场景，无法手动管理
- `redis`: 复杂度过高，单实例场景不需要

### 2. PostgreSQL 异步操作

**Decision**: 使用现有 `backend/db.py` 的 asyncpg 连接池

**Rationale**:
- 复用现有基础设施
- asyncpg 是 Python 最快的 PostgreSQL 驱动
- 连接池已配置 (min_size=2, max_size=10)

**Alternatives considered**:
- SQLAlchemy async: 增加 ORM 复杂度，不必要
- 新建独立连接池: 违反 DRY 原则

### 3. Token 估算方法

**Decision**: 简单字符估算 `len(text) // 3`

**Rationale**:
- 对于阈值判断（2000 tokens）足够准确
- 无需额外依赖 (tiktoken)
- 性能影响可忽略

**Alternatives considered**:
- tiktoken: 精确但增加依赖和延迟
- 按字数估算: 中英文混合场景不准确

### 4. LLM 摘要生成

**Decision**: 使用现有 `get_model("supervisor")` 进行摘要

**Rationale**:
- 复用现有 LLM 配置
- 无需新增模型配置
- Supervisor 模型能力足够

**Prompts**:
```python
# 摘要生成
SUMMARY_PROMPT = """请为以下内容生成简洁摘要，保留关键信息和数据。最多300字。

## 原文
{content}
"""

# 关键数据提取
KEY_DATA_PROMPT = """从以下内容提取关键数据，返回 JSON：
- numbers: 关键数字 [{{"label": "xxx", "value": "xxx"}}]
- findings: 关键发现 ["xxx"]

## 原文
{content}

直接返回 JSON，不要其他文字。
"""

# 输出类型分类
CLASSIFY_PROMPT = """分析以下内容，判断它包含哪些类型的数据。

## 可选类型
- financial_report, revenue_data, table, chart, code, analysis_report, summary, file, raw_data

## 内容
{content}

返回 JSON 数组，如 ["financial_report", "table"]
"""
```

### 5. 滑动过期实现

**Decision**: 每次访问时更新 `last_accessed_at` 和 `expires_at`

**Rationale**:
- 活跃用户的上下文永不过期
- 减少不必要的清理
- 简单直观

**Implementation**:
```python
def touch(self):
    self.last_accessed_at = datetime.now()
    self.expires_at = self.last_accessed_at + timedelta(days=CONTEXT_EXPIRATION_DAYS)
```

### 6. 清理任务调度

**Decision**: 使用 FastAPI `lifespan` 后台任务

**Rationale**:
- 无需额外依赖 (Celery, APScheduler)
- 与应用生命周期绑定
- 简单可靠

**Implementation**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    cleanup_task.cancel()
```

### 7. 并发安全

**Decision**: 依赖 PostgreSQL `ON CONFLICT DO UPDATE` + asyncpg 连接池

**Rationale**:
- 数据库层面保证原子性
- 内存缓存是读缓存，写操作先写 DB
- 单实例场景无需分布式锁

**Pattern**:
```sql
INSERT INTO task_contexts (...) VALUES (...)
ON CONFLICT (context_id) DO UPDATE SET
    content = EXCLUDED.content,
    last_accessed_at = NOW(),
    ...
```

### 8. 优雅降级策略

**Decision**: PostgreSQL 故障时降级为仅缓存模式，LLM 故障时使用简单截断

**Rationale**:
- 上下文传递是增强功能，不应阻塞核心流程
- 降级后仍能提供基本功能

**Implementation**:
```python
async def store(self, ...):
    # 先存内存
    self._cache[context_id] = entry

    # 尝试持久化
    try:
        await self._save_to_db(entry)
    except Exception as e:
        logger.error(f"[ContextManager] DB save failed: {e}")
        # 不抛出，继续使用内存缓存
```

### 9. 安全隔离

**Decision**: 所有访问操作验证 thread_id 一致性

**Rationale**:
- 防止跨会话数据泄露
- 符合最小权限原则

**Implementation**:
```python
async def get(self, context_id: str, thread_id: str) -> ContextEntry | None:
    entry = await self._load(context_id)
    if entry and entry.thread_id != thread_id:
        logger.warning(f"[ContextManager] Access denied: thread_id mismatch")
        return None
    return entry
```

## Dependencies Confirmed

| Dependency | Version | Purpose |
|------------|---------|---------|
| asyncpg | existing | PostgreSQL async driver |
| langchain_core | existing | LLM invocation |
| collections.OrderedDict | stdlib | LRU cache |
| dataclasses | stdlib | Data models |

## No Outstanding Questions

All technical decisions resolved. Ready for Phase 1 design.
