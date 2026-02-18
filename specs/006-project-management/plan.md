# Implementation Plan: Project Management

**Branch**: `006-project-management` | **Date**: 2026-02-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-project-management/spec.md`

## Summary

实现项目管理功能,允许用户创建项目来组织对话和文件。包括:
- **项目 CRUD**: 创建/编辑/删除项目,强制用户级别唯一名称
- **项目工作区**: 双栏布局 (Sources 面板 + Chat 面板)
- **文件源管理**: 永久存储、多选文件作为对话上下文
- **导航集成**: 项目与 History 同级,支持对话添加/移除项目

技术方案:
- 后端: 新增 `projects` 模块,复用现有文件上传和对话系统
- 前端: 扩展 Sidebar 组件,新增 ProjectWorkspace 组件
- 数据库: 新增 `projects` 和 `project_files` 表,扩展 `conversations` 表

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, React 19, LangGraph, asyncpg
**Storage**: PostgreSQL (projects, project_files 表), 文件系统 (项目文件永久存储)
**Testing**: pytest (backend), (frontend 暂无测试框架)
**Target Platform**: Web (Linux server + modern browsers)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: 项目列表 <500ms, 文件上传 <30s (10MB)
**Constraints**: 每项目最多 50 文件, 单文件最大 10MB
**Scale/Scope**: 每用户最多 50 项目,支持 PDF/DOCX/TXT/MD/CSV/JSON/代码文件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent 隔离 | ✅ PASS | 项目管理不涉及 Agent 修改 |
| II. 注册驱动发现 | ✅ PASS | 不涉及新 Agent 注册 |
| III. 流式优先 | ✅ PASS | 复用现有 Chat SSE 流式传输 |
| IV. 包扩展性 | ✅ PASS | 不涉及包 Agent |
| V. 简洁性 | ✅ PASS | 复用现有组件,最小新增代码 |
| VI. 测试优先 | ⚠️ PARTIAL | 需要为关键 API 添加测试 |
| VII. 分层依赖 | ✅ PASS | projects/ 模块遵循分层架构 |
| VIII. 接口优先 | ✅ PASS | 先定义 API contracts |
| IX. 安全边界 | ✅ PASS | 所有端点验证用户权限 |

**Gate Result**: PASS (测试在实现阶段补充)

## Project Structure

### Documentation (this feature)

```text
specs/006-project-management/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── projects_api.py  # API contract definitions
├── prototype.html       # UI prototype
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── projects/                    # NEW: 项目管理模块
│   ├── __init__.py
│   ├── models.py               # Pydantic models
│   ├── database.py             # Database operations
│   └── router.py               # API endpoints
├── conversations/
│   ├── models.py               # MODIFY: 添加 project_id
│   ├── database.py             # MODIFY: 支持项目过滤
│   └── router.py               # MODIFY: 添加项目关联端点
├── files/
│   ├── models.py               # MODIFY: 支持项目文件
│   └── database.py             # MODIFY: 项目文件存储
└── main.py                     # MODIFY: 注册 projects router

frontend/src/
├── api/
│   └── projects.ts             # NEW: Projects API client
├── hooks/
│   └── useProjects.ts          # NEW: Projects state management
├── components/
│   ├── Layout/
│   │   └── Sidebar.tsx         # MODIFY: 添加 Projects section
│   ├── Projects/               # NEW: 项目组件
│   │   ├── ProjectList.tsx     # 项目列表
│   │   ├── ProjectItem.tsx     # 单个项目项
│   │   ├── ProjectWorkspace.tsx # 项目工作区 (Sources + Chat)
│   │   ├── SourcesPanel.tsx    # 文件源面板
│   │   └── NewProjectModal.tsx # 新建项目对话框
│   └── Conversations/
│       └── ConversationItem.tsx # MODIFY: 支持右键菜单
└── types/
    └── index.ts                # MODIFY: 添加 Project 类型

infra/migrations/versions/
└── 004_create_projects_table.py # NEW: 项目相关表
```

**Structure Decision**: 遵循现有 Web application 结构,新增 `backend/projects/` 模块和 `frontend/src/components/Projects/` 目录。

## Complexity Tracking

> No constitution violations requiring justification.

---

## Phase Completion Status

| Phase | Status | Output |
|-------|--------|--------|
| Phase 0: Research | ✅ Complete | [research.md](./research.md) |
| Phase 1: Design | ✅ Complete | [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md) |
| Phase 2: Tasks | ⏳ Pending | Run `/speckit.tasks` to generate |

## Generated Artifacts

- `research.md` - 技术研究和决策记录
- `data-model.md` - 数据模型设计 (projects, project_files 表)
- `contracts/projects_api.py` - API 契约定义
- `quickstart.md` - 测试场景和验收标准
- `prototype.html` - 可交互 UI 原型

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks
2. Review generated tasks and adjust priorities if needed
3. Run `/speckit.implement` to start implementation
