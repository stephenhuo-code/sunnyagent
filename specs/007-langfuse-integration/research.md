# Research: Langfuse 可观测性集成

**Branch**: `007-langfuse-integration` | **Date**: 2026-02-19

## 1. Langfuse LangGraph/LangChain 集成

### Decision
使用 `langfuse.langchain.CallbackHandler` + `@observe` 装饰器 + `start_as_current_observation()` 上下文管理器。

### Rationale
- CallbackHandler 自动捕获所有 LangChain/LangGraph 操作
- `@observe` 装饰器为自定义函数提供自动 Span 创建
- 上下文管理器允许对 AIME 组件进行细粒度 Span 控制
- SDK v3（2025年6月发布）基于 OpenTelemetry，提供自动上下文传播

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| 手动调用 Langfuse API | 代码侵入性高，需要大量改动 |
| OpenTelemetry 直接集成 | Langfuse SDK 已封装，无需直接使用 OTEL |
| 自建可观测性系统 | 重复造轮子，Langfuse 已提供完整方案 |

### Code Pattern - 普通异步函数

对于普通的 `async def` 函数，可以使用上下文管理器模式：

```python
from langfuse import get_client, observe
from langfuse.langchain import CallbackHandler

@observe(name="intent-analyzer")
async def analyze_intent(message: str) -> Intent:
    # 自动创建 Span
    return intent

async def execute_plan(message: str, session_id: str, user_id: str):
    langfuse = get_client()
    handler = CallbackHandler()

    with langfuse.start_as_current_observation(
        as_type="span",
        name="aime-planner"
    ) as planner_span:
        # AIME 组件执行
        intent = await analyze_intent(message)

        # LangGraph 执行
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config={"callbacks": [handler]}
        )

        planner_span.update_trace(
            input={"message": message},
            output={"result": result}
        )
```

### Code Pattern - Async Generator（重要）

> **⚠️ 关键发现**：在 async generator 中使用 `start_as_current_observation()` 上下文管理器会导致 **context 丢失问题**。
>
> **原因**：OpenTelemetry 使用 `contextvars` 存储当前 span 上下文，但 Python 的 async generator 在每次 `yield` 后会切换上下文，导致 `update_current_observation()` 无法找到正确的 span。
>
> **参考**：[langfuse/langfuse#7226](https://github.com/langfuse/langfuse/issues/7226)

**错误模式**（async generator 中 context 丢失）：
```python
async def stream_response() -> AsyncGenerator[dict, None]:
    langfuse = get_client()

    # ❌ 错误：上下文管理器在 yield 后会丢失
    span_context = langfuse.start_as_current_observation(
        as_type="generation",
        name="llm-stream",
    )
    span_context.__enter__()

    try:
        async for chunk in llm.astream(messages):
            yield chunk
            # ❌ 此时 update_current_observation() 无效！
            langfuse.update_current_observation(output={"text": chunk})
    finally:
        span_context.__exit__(None, None, None)
```

**正确模式**（使用直接 span 引用）：
```python
async def stream_response() -> AsyncGenerator[dict, None]:
    langfuse = get_client()

    # ✅ 正确：使用 start_generation() 或 start_span() 获取直接引用
    span = langfuse.start_generation(
        name="llm-stream",
        model="gpt-4",
        input={"messages": messages[:500]},
    )

    output_text = ""
    try:
        async for chunk in llm.astream(messages):
            output_text += chunk.content
            yield chunk
    except Exception as e:
        # ✅ 直接调用 span.update()，不依赖上下文
        span.update(output={"error": str(e)})
        raise
    finally:
        # ✅ 成功时更新输出并关闭 span
        span.update(output={"text": output_text[:500]})
        span.end()
```

### Span 类型选择

| 方法 | 用途 | 适用场景 |
|------|------|----------|
| `start_generation()` | LLM 调用 | 任务分解、摘要生成、重规划等 LLM 调用 |
| `start_span()` | 通用执行 | Actor 执行、工具调用等非 LLM 操作 |
| `trace()` | 顶层追踪 | 请求入口（如 `process()` 方法） |

### 当前实现总结

`backend/aime/planner.py` 中的 Langfuse span 处理：

| 方法 | Span 类型 | 模式 |
|------|-----------|------|
| `process()` | trace | `start_as_current_observation(as_type="trace")` + `update_current_trace()` |
| `_handle_direct_reply()` | generation | `start_generation()` + `span.update()` + `span.end()` |
| `_execute_actor()` | span | `start_span()` + `span.update()` + `span.end()` |
| `_decompose_task()` | generation | `start_generation()` + `span.update()` + `span.end()` |
| `_generate_summary()` | generation | `start_generation()` + `span.update()` + `span.end()` |
| `_create_alternative_subtask()` | generation | `start_generation()` + `span.update()` + `span.end()` |
| `_replan_from_failure()` | generation | `start_generation()` + `span.update()` + `span.end()` |

> **注意**：`start_as_current_observation(as_type="trace")` 在 SDK v3 类型定义中未包含，需要添加 `# type: ignore[arg-type]` 注释来抑制 pyright 警告（运行时正常工作）。

---

## 2. Langfuse Admin API 账号同步

### Decision
使用 SCIM-compliant API (`/api/public/scim/Users`) + Organization Membership API。

### Rationale
- SCIM 是身份管理标准协议
- Basic Auth 认证简单安全
- 支持用户创建、查询、删除（从组织移除）

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| SSO (方案 A) | 需要引入 Keycloak 等额外基础设施 |
| Token 访问 (方案 C) | 安全性较低，token 管理复杂 |

### API Summary
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/public/scim/Users` | GET | 列出所有用户 |
| `/api/public/scim/Users` | POST | 创建用户 |
| `/api/public/scim/Users/{id}` | DELETE | 从组织移除用户 |
| `/api/public/organizations/memberships` | PUT | 更新成员权限 |

### Code Pattern
```python
import httpx

class LangfuseAdminClient:
    def __init__(self, base_url: str, public_key: str, secret_key: str):
        self.base_url = base_url
        self.auth = (public_key, secret_key)

    async def create_user(self, email: str, name: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/public/scim/Users",
                auth=self.auth,
                json={
                    "userName": email,
                    "displayName": name,
                    "emails": [{"value": email, "primary": True}]
                }
            )
            response.raise_for_status()
            return response.json()

    async def disable_user(self, user_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/api/public/scim/Users/{user_id}",
                auth=self.auth
            )
            response.raise_for_status()
```

---

## 3. Langfuse Docker 部署

### Decision
使用 **Langfuse Server v3** Docker 镜像，配合 ClickHouse、Redis、MinIO 部署。

> **重要**：Langfuse Server 版本与 Python SDK 版本**必须匹配**。
> - **SDK v3 需要 Server v3**（≥ 3.63.0）
> - **SDK v2 需要 Server v2**
>
> 本方案采用 **Server v3 + SDK v3** 组合，获得完整功能支持。

### Rationale
- SDK v3 基于 OpenTelemetry，API 更现代
- Server v3 提供更好的性能和扩展性
- ClickHouse 提供高效的 OLAP 查询
- 虽然部署复杂度增加，但 docker-compose 可以一键启动

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Server v2 + SDK v2 | SDK v2 API 较老，功能受限 |
| Server v2 + SDK v3 | **不兼容**，SDK v3 需要 Server ≥ 3.63.0 |
| Langfuse Cloud | 数据在外部，不符合私有化部署要求 |

### Configuration
```yaml
# docker-compose.yml
services:
  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    volumes:
      - clickhouse-data:/var/lib/clickhouse

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory-policy noeviction

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123

  langfuse:
    image: langfuse/langfuse:3
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: ${LANGFUSE_DATABASE_URL}
      CLICKHOUSE_URL: http://clickhouse:8123
      REDIS_HOST: redis
      LANGFUSE_S3_EVENT_UPLOAD_ENABLED: true
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      NEXTAUTH_URL: ${LANGFUSE_URL}
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      SALT: ${LANGFUSE_SALT}
      ENCRYPTION_KEY: ${LANGFUSE_ENCRYPTION_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/public/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
```

### Environment Variables
```env
# Langfuse 服务配置
LANGFUSE_URL=http://localhost:3001
LANGFUSE_DATABASE_URL=postgresql://sunnyagent:sunnyagent123@localhost:5432/langfuse
LANGFUSE_NEXTAUTH_SECRET=<generated-256-bit-secret>
LANGFUSE_SALT=<generated-256-bit-salt>
LANGFUSE_ENCRYPTION_KEY=<generated-32-byte-hex>

# SunnyAgent 集成配置
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_BASE_URL=http://localhost:3001
```

---

## 4. Langfuse Python SDK

### Decision
使用 **Langfuse Python SDK v3** (`langfuse>=3.0.0`)，通过环境变量配置。

> **版本说明**：SDK v3 需要 Langfuse Server ≥ 3.63.0，**不兼容 Server v2**。

### Rationale
- SDK v3 基于 OpenTelemetry，性能更好
- 装饰器和上下文管理器 API 简洁
- 环境变量配置符合 12-factor 原则
- 需要配合 Langfuse Server v3 使用

### Package
```bash
uv add langfuse>=3.0.0
```

### Key Classes
| Class/Function | Purpose |
|----------------|---------|
| `get_client()` | 获取全局 Langfuse 客户端 |
| `@observe` | 装饰器，自动创建 Span |
| `CallbackHandler` | LangChain/LangGraph 集成 |
| `start_as_current_observation()` | 创建自定义 Span |
| `propagate_attributes()` | 传播 session_id/user_id |

### Initialization Pattern
```python
# backend/main.py
from contextlib import asynccontextmanager
from langfuse import get_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 验证 Langfuse 连接（非阻塞，失败时 warn）
    try:
        langfuse = get_client()
        if langfuse.auth_check():
            logger.info("Langfuse connected successfully")
        else:
            logger.warning("Langfuse auth check failed, tracing disabled")
    except Exception as e:
        logger.warning(f"Langfuse initialization failed: {e}, tracing disabled")

    yield

    # 确保所有 trace 发送完成
    try:
        get_client().flush()
    except Exception:
        pass
```

---

## 5. 优雅降级策略

### Decision
Langfuse 不可用时，跳过 trace 上报，Agent 正常运行。

### Rationale
- 可观测性是增强功能，不应影响核心业务
- 异步上报已将影响降到最低
- 用户体验优先于数据完整性

### Code Pattern
```python
class LangfuseService:
    def __init__(self):
        self._enabled = True
        try:
            self._client = get_client()
            if not self._client.auth_check():
                self._enabled = False
        except Exception:
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_callback_handler(self) -> CallbackHandler | None:
        if not self._enabled:
            return None
        return CallbackHandler()
```

---

## Sources

- [Langfuse LangChain Integration](https://langfuse.com/integrations/frameworks/langchain)
- [Langfuse LangGraph Cookbook](https://langfuse.com/guides/cookbook/integration_langgraph)
- [Langfuse Python SDK v3](https://langfuse.com/changelog/2025-06-05-python-sdk-v3-generally-available)
- [Langfuse SCIM & Org API](https://langfuse.com/docs/administration/scim-and-org-api)
- [Langfuse Docker Compose Deployment](https://langfuse.com/self-hosting/deployment/docker-compose)
- [Langfuse Configuration](https://langfuse.com/self-hosting/configuration)
