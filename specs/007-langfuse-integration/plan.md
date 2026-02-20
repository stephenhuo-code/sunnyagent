# Implementation Plan: Langfuse 可观测性集成

**Branch**: `007-langfuse-integration` | **Date**: 2026-02-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-langfuse-integration/spec.md`

## Summary

集成 Langfuse 可观测性平台到 SunnyAgent，实现：
1. Agent 执行链路追踪（通过 LangGraph Callback + 自定义 Span）
2. 运行状态监控（利用 Langfuse 内置仪表盘）
3. 测试数据集管理与 Agent 评估（Dataset + Experiment + `/api/chat`）
4. 系统管理集成（Langfuse 链接 + Admin API 账号同步）

技术方案：使用 Langfuse Python SDK v3 + LangChain CallbackHandler，Docker 部署 Langfuse v2 复用现有 PostgreSQL。

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- `langfuse>=3.0.0` (Python SDK with OpenTelemetry foundation)
- `langfuse.langchain.CallbackHandler` (LangGraph integration)
- `httpx` (Admin API client)

**Storage**: PostgreSQL (复用 SunnyAgent 现有数据库，Langfuse 独立 schema)
**Testing**: pytest + Langfuse Dataset/Experiment
**Target Platform**: Linux server (Docker)
**Project Type**: Web application (backend + frontend)
**Performance Goals**:
- Trace 上报延迟 < 10ms（异步）
- 监控数据延迟 < 30s
- 账号同步 < 5s

**Constraints**:
- Langfuse 不可用时 Agent 正常运行（优雅降级）
- 95% Trace 成功上报率
- **Async Generator Span 处理**：在 async generator 中必须使用 `start_span()`/`start_generation()` 直接获取 span 引用，避免 OpenTelemetry context 丢失问题（详见 research.md）

**Scale/Scope**: 支持 100 个并发测试用例评估

**Implementation Notes**:
- Langfuse SDK v3 的 `start_as_current_observation(as_type="trace")` 在类型定义中未包含，需使用 `# type: ignore[arg-type]`
- 所有 async generator 方法（如 `_handle_direct_reply`, `_execute_actor`）使用直接 span 引用模式

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Agent 隔离 | ✅ PASS | Langfuse Callback 作为中间件注入，不改变 Agent 隔离性 |
| II. 注册驱动发现 | ✅ PASS | 无新 Agent 添加，仅增加可观测性层 |
| III. 流式优先 | ✅ PASS | Trace 异步上报，不影响 SSE 流式响应 |
| IV. 包扩展性 | ✅ PASS | 无影响 |
| V. 简洁性 | ✅ PASS | 使用 Langfuse 原生 Callback，几乎零代码改动；Admin API 封装为独立 service |
| VI. 测试优先 | ✅ PASS | Langfuse Dataset + Experiment 增强测试能力 |
| VII. 分层依赖 | ✅ PASS | `LangfuseService` 放入 Service 层，`LangfuseAdminClient` 封装 API 调用 |
| VIII. 接口优先 | ✅ PASS | Admin API 契约已定义在 contracts/ |
| IX. 安全边界 | ✅ PASS | Admin API 使用 Basic Auth，敏感信息通过环境变量配置 |

## Project Structure

### Documentation (this feature)

```text
specs/007-langfuse-integration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── langfuse-admin-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── services/
│   └── langfuse_service.py      # Langfuse 客户端封装 + 账号同步
├── aime/
│   ├── planner.py               # 添加 Langfuse Callback 注入点
│   ├── intent/
│   │   └── analyzer.py          # 添加自定义 Span
│   └── actors/
│       └── generic.py           # 添加自定义 Span
├── auth/
│   └── database.py              # 用户 CRUD 时触发 Langfuse 同步
└── main.py                      # Langfuse 初始化和优雅降级

frontend/
├── src/
│   └── components/
│       └── Admin/
│           └── SystemSettings.tsx  # 添加 Langfuse 链接

infra/
├── docker-compose.yml           # 添加 Langfuse 服务
└── .env.example                 # 添加 Langfuse 环境变量

scripts/
└── evaluation/                  # Agent 评估脚本
    └── run_experiment.py
```

**Structure Decision**: Web application 结构，Backend 增加 `services/langfuse_service.py`，Frontend 增加系统设置页面链接。

## Complexity Tracking

> No violations requiring justification. All changes align with constitution principles.

