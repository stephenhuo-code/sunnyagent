# Research: Project Management

**Feature**: 006-project-management
**Date**: 2026-02-17

## Research Summary

本功能基于现有技术栈实现,无需引入新技术。主要研究点为如何最佳集成到现有架构。

---

## R1: 文件永久存储策略

### Decision
使用本地文件系统存储,按 `{base_dir}/{user_id}/{project_id}/{filename}` 组织。

### Rationale
- 复用现有 `backend/files/` 模块的文件处理逻辑
- 本地存储满足当前规模需求 (50 项目 × 50 文件 × 10MB = 最大 25GB/用户)
- 目录结构清晰,便于管理和清理
- 环境变量 `PROJECT_FILES_DIR` 配置基础目录,方便部署调整

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| S3/MinIO | 当前规模不需要,增加运维复杂度 |
| 数据库 BLOB | 大文件存储效率低,备份困难 |
| 临时目录 | 重启后文件丢失,不符合需求 |

---

## R2: 对话-项目关联模型

### Decision
在 `conversations` 表添加可空 `project_id` 外键,一对多关系。

### Rationale
- 最简单的关联方式,一个对话只能属于一个项目
- `project_id = NULL` 表示对话在 History 中
- 级联规则: 项目删除时 SET NULL (对话不删除,回到 History)
- 复用现有 conversations 表,最小迁移成本

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| 多对多关联表 | 需求是一对多,过度设计 |
| 新建 project_conversations 表 | 冗余,直接加外键更简单 |

---

## R3: 前端状态管理

### Decision
新增 `useProjects` hook,与现有 `useConversations` 模式一致。

### Rationale
- 遵循现有代码风格,降低学习成本
- 使用 React Context 管理全局项目状态
- 与 `useChat` 集成传递选中文件上下文

### Implementation Pattern
```typescript
// hooks/useProjects.ts
interface UseProjectsReturn {
  projects: Project[];
  isLoading: boolean;
  error: string | null;
  createProject: (name: string) => Promise<Project>;
  updateProject: (id: string, name: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;
}
```

---

## R4: 文件上下文传递到 Chat

### Decision
扩展 `ChatRequest` 添加 `selected_file_ids` 字段,后端自动加载文件内容。

### Rationale
- 复用现有 `file_ids` 字段模式
- 后端负责文件权限验证和内容加载
- 前端只需传递选中文件 ID 列表

### Integration Points
- `frontend/src/hooks/useChat.ts`: 添加 `selectedFileIds` 状态
- `backend/main.py`: ChatRequest 已支持 `file_ids`
- `backend/stream_handler.py`: 已有文件上下文处理逻辑

---

## R5: 导航树 UI 模式

### Decision
扩展现有 Sidebar 组件,Projects 和 History 作为同级 section。

### Rationale
- 复用现有 CSS 变量和组件样式
- 项目采用可展开树结构,显示关联对话
- 右键菜单使用自定义 ContextMenu 组件

### UI Structure
```
Sidebar
├── [+ 新建对话] (existing)
├── PROJECTS section (new)
│   ├── 📂 项目 A (expandable)
│   │   └── 💬 对话 1, 2...
│   └── 📂 项目 B
└── HISTORY section (existing, moved)
    └── 💬 对话列表
```

---

## R6: API 设计模式

### Decision
RESTful API,遵循现有 conversations/files API 模式。

### Endpoints Summary
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/projects | 获取用户项目列表 |
| POST | /api/projects | 创建项目 |
| PATCH | /api/projects/{id} | 更新项目名称 |
| DELETE | /api/projects/{id} | 删除项目 |
| GET | /api/projects/{id}/files | 获取项目文件列表 |
| POST | /api/projects/{id}/files | 上传文件到项目 |
| DELETE | /api/projects/{id}/files/{file_id} | 删除项目文件 |
| POST | /api/conversations/{id}/project | 关联对话到项目 |
| DELETE | /api/conversations/{id}/project | 移除对话项目关联 |

---

## Dependencies Confirmed

| Dependency | Version | Already in Project |
|------------|---------|-------------------|
| FastAPI | 0.x | ✅ Yes |
| asyncpg | 0.x | ✅ Yes |
| Pydantic | 2.x | ✅ Yes |
| React | 19.x | ✅ Yes |
| TypeScript | 5.x | ✅ Yes |

**No new dependencies required.**

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| 文件系统空间不足 | 环境变量配置存储路径,可挂载外部存储 |
| 文件上传大文件阻塞 | 使用现有分块上传逻辑,设置 10MB 限制 |
| 并发项目名冲突 | 数据库 UNIQUE 约束 + 前端 optimistic lock |
| 项目删除后文件残留 | 数据库触发器或应用层级联删除确保清理 |
