# Implementation Plan: 插件管理系统 (Plugin Management)

**Branch**: `012-plugin-management` | **Date**: 2026-02-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-plugin-management/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

开发插件管理系统，允许用户浏览、启用/禁用、上传、分享和评分插件（Agent 和 Skill）。系统统一管理所有来源（Preset、Package、Uploaded、Shared）的插件，提供 /命令调用支持，并支持 Workflow Skill 的多步骤任务规划执行。

## Technical Context

**Language/Version**: Python 3.11+ (Backend), TypeScript 5.x (Frontend)
**Primary Dependencies**: FastAPI, React 19, LangGraph, deepagents, asyncpg
**Storage**: PostgreSQL (插件状态、评分)，文件系统 (上传的插件包)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Linux/macOS server, Modern browsers
**Project Type**: Web application (frontend + backend)
**Performance Goals**: 插件列表加载 <3s, 启用/禁用 <1s, 上传处理 <5s (1MB), /命令自动完成 <200ms
**Constraints**: 上传包大小 ≤10MB, 用户级状态隔离
**Scale/Scope**: 支持数百个插件，数千用户，每用户独立设置

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. Agent 隔离 | ✅ PASS | 插件管理不修改 Agent 核心，仅控制可用性过滤 |
| II. 注册驱动发现 | ✅ PASS | 复用现有 AGENT_REGISTRY，新增 UserPluginState 过滤层 |
| III. 流式优先 | ✅ PASS | 插件管理使用标准 REST API，不影响聊天流式管线 |
| IV. 包扩展性 | ✅ PASS | 上传功能扩展现有 packages/ 加载机制，保持兼容 |
| V. 简洁性 | ✅ PASS | 最小化新增表结构，复用现有认证和文件上传基础设施 |
| VI. 测试优先 | ✅ PASS | 计划编写 API 端点测试和状态过滤逻辑测试 |
| VII. 分层依赖 | ✅ PASS | 遵循 API → Service → Repository 分层 |
| VIII. 接口优先 | ✅ PASS | 先定义 API contracts，再实现 |
| IX. 安全边界 | ✅ PASS | 上传包验证、用户权限检查、数据隔离 |

## Project Structure

### Documentation (this feature)

```text
specs/012-plugin-management/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── core/
│   └── plugins.py           # 插件管理 API 端点
├── plugins/                 # 新增：插件管理模块
│   ├── __init__.py
│   ├── models.py            # PluginInfo, UserPluginState, PluginRating 模型
│   ├── database.py          # 插件状态/评分 CRUD
│   ├── service.py           # 插件管理业务逻辑
│   ├── loader.py            # 统一插件加载器
│   └── validator.py         # 上传包验证
├── skills/
│   └── registry.py          # 修改：增加 user_id 过滤支持
├── agents/
│   └── loader.py            # 修改：增加 user_id 过滤支持
└── aime/
    └── planner.py           # 修改：增加用户插件状态过滤

frontend/src/
├── api/
│   └── plugins.ts           # 插件管理 API 客户端
├── components/
│   └── Plugins/             # 新增：插件管理组件
│       ├── PluginSidebar.tsx
│       ├── PluginDetail.tsx
│       ├── BrowsePluginsModal.tsx
│       ├── UploadPluginModal.tsx
│       └── SharePluginModal.tsx
└── pages/
    └── PluginsPage.tsx      # 插件管理页面

infra/migrations/versions/
└── xxx_create_plugin_tables.py  # 新增数据库表
```

**Structure Decision**: Web application，扩展现有 backend/ 和 frontend/ 结构。新增 backend/plugins/ 模块封装插件管理逻辑，修改现有 skills/registry 和 agents/loader 增加用户过滤支持。

## Complexity Tracking

无宪法违规，无需填写此部分。

---

## Phase Completion Status

### Phase 0: Research ✅

**Output**: [research.md](./research.md)

**Key Decisions**:
1. 保留现有 SKILL_REGISTRY 和 AGENT_REGISTRY，新增用户级过滤层
2. 复用 deepagents FilesystemBackend，扩展加载器支持用户目录
3. 采用与 conversations/files 一致的 user_id 隔离模式
4. 插件命名空间格式 `{source}:{name}`
5. Shared 插件引用原 uploaded 目录，不复制文件

### Phase 1: Design & Contracts ✅

**Outputs**:
- [data-model.md](./data-model.md) - 3 张新表：uploaded_plugins, user_plugin_states, plugin_ratings
- [contracts/plugins-api.yaml](./contracts/plugins-api.yaml) - OpenAPI 3.1 规范，12 个端点
- [quickstart.md](./quickstart.md) - 8 个测试场景 + 边界条件测试

### Constitution Re-Check (Post Phase 1)

| 原则 | 状态 | 验证 |
|------|------|------|
| I. Agent 隔离 | ✅ PASS | 插件管理通过过滤层控制，不修改 Agent 内部 |
| II. 注册驱动发现 | ✅ PASS | 新增 PluginService 查询注册表 + 用户状态 |
| III. 流式优先 | ✅ PASS | API 设计为 REST，不影响 SSE 管线 |
| IV. 包扩展性 | ✅ PASS | 上传包复用现有 AGENTS.md/SKILL.md 格式 |
| V. 简洁性 | ✅ PASS | 3 张表，12 个端点，最小化设计 |
| VI. 测试优先 | ✅ PASS | quickstart.md 定义验证命令 |
| VII. 分层依赖 | ✅ PASS | API(plugins.py) → Service → Database |
| VIII. 接口优先 | ✅ PASS | OpenAPI 规范先于实现 |
| IX. 安全边界 | ✅ PASS | 用户隔离、包验证、权限检查均已设计 |

---

## Next Steps

运行 `/speckit.tasks` 生成 tasks.md 实现任务列表。
