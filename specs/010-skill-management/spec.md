# Feature Specification: 用户级 Skill 管理

**Feature Branch**: `010-skill-management`
**Created**: 2026-02-21
**Status**: Draft

## 当前架构分析

### Skills 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Skills 层级结构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   │
│  │ Anthropic Skills │   │  Custom Skills  │   │ Package Skills  │   │
│  │ (Git Submodule)  │   │  (系统级自定义)   │   │  (Agent 内置)   │   │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘   │
│           │                     │                     │             │
│           └──────────┬──────────┴──────────┬──────────┘             │
│                      ▼                     ▼                        │
│           ┌──────────────────┐   ┌──────────────────┐               │
│           │  skills/loader.py │   │ agents/loader.py │               │
│           │  (全局 Skills)    │   │  (Package 内置)  │               │
│           └────────┬─────────┘   └────────┬─────────┘               │
│                    │                      │                         │
│                    └───────────┬──────────┘                         │
│                                ▼                                    │
│                    ┌──────────────────────┐                         │
│                    │   SKILL_REGISTRY     │                         │
│                    │   (全局注册表)        │                         │
│                    └──────────────────────┘                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 当前 Skill 数据结构

```python
@dataclass
class SkillEntry:
    name: str              # 唯一标识符 (lowercase-hyphen)
    description: str       # 触发条件描述 (YAML frontmatter)
    path: Path             # SKILL.md 所在目录
    skill_type: SkillType  # "atomic" | "workflow"
    _instructions: str     # 懒加载的完整指令
```

### 当前 Skill 存储位置

| 来源 | 目录 | 加载时机 | 所有者 |
|------|------|----------|--------|
| Anthropic Skills | `skills/anthropic/skills/` | 应用启动 | 系统（Git Submodule） |
| Custom Skills | `skills/custom/` | 应用启动 | 系统管理员 |
| Package Skills | `packages/<pkg>/skills/` | 应用启动 | Package 开发者 |

### 当前 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET | 列出所有注册的 Skills |
| `/api/skills/{name}` | GET | 获取 Skill 详情（含完整指令） |

### 当前使用方式

1. **前端直接调用**：用户在 InputBar 输入 `/skill-name` 触发
2. **Agent 内部激活**：Agent 调用 `activate_skill(skill_name)` 工具加载指令
3. **AIME 规划**：Planner 识别 workflow skill，按 steps 分解任务

---

## Agent 系统架构

### Agent 层级结构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent 层级结构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐                          │
│  │  Preset Agents  │   │ Package Agents  │                          │
│  │  (内置 Agent)    │   │ (packages/ 目录) │                          │
│  └────────┬────────┘   └────────┬────────┘                          │
│           │                     │                                   │
│   research.py                packages/<name>/                       │
│   sql.py                        ├── AGENTS.md                       │
│   general.py                    └── skills/                         │
│   generic.py                                                        │
│           │                     │                                   │
│           └──────────┬──────────┘                                   │
│                      ▼                                              │
│           ┌──────────────────────┐                                  │
│           │    AGENT_REGISTRY    │                                  │
│           │    (全局注册表)       │                                  │
│           └──────────────────────┘                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 当前 Agent 数据结构

```python
@dataclass
class AgentEntry:
    name: str                    # 唯一标识符
    description: str             # 人类可读描述
    graph: CompiledStateGraph    # LangGraph 执行图
    tools: list                  # Agent 工具列表
    icon: str = "bot"            # UI 图标
    show_in_selector: bool       # 是否显示在前端选择器
    capabilities: list[str]      # AIME 能力匹配
    source: AgentSource          # "preset" | "package"
```

---

## 用户级 Skill 管理需求

### 目标

1. 用户可以创建、编辑、启用/禁用自己的 Skills
2. 用户 Skills 与系统 Skills 隔离，互不影响
3. 用户 Skills 仅对创建者可见和可用
4. 支持 Skill 版本管理和导入/导出
5. (可选) 管理员可将用户 Skill 提升为系统级 Skill

### 用户场景

#### US1: 创建自定义 Skill
用户希望创建一个 "周报生成" Skill，每周自动汇总工作内容。

#### US2: 管理我的 Skills
用户希望查看、编辑、启用/禁用自己创建的 Skills。

#### US3: 使用自定义 Skill
用户在对话中输入 `/my-weekly-report` 触发自己的 Skill。

#### US4: 分享 Skill (P2)
用户希望将自己的 Skill 分享给其他用户或导出为文件。

---

## 设计方案

### 数据模型

```sql
-- 用户 Skill 表
CREATE TABLE user_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL REFERENCES users(id),
    name VARCHAR(100) NOT NULL,              -- 唯一标识符
    display_name VARCHAR(255),               -- 显示名称
    description TEXT,                        -- 触发条件描述
    instructions TEXT NOT NULL,              -- SKILL.md 内容
    skill_type VARCHAR(20) DEFAULT 'atomic', -- atomic | workflow
    steps JSONB,                             -- workflow 步骤定义
    is_enabled BOOLEAN DEFAULT TRUE,         -- 是否启用
    version INTEGER DEFAULT 1,               -- 版本号
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_user_skill UNIQUE (user_id, name)
);

-- 版本历史（可选，P2）
CREATE TABLE user_skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES user_skills(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    instructions TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 架构扩展

```
┌─────────────────────────────────────────────────────────────────────┐
│                    扩展后的 Skills 架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   │
│  │ System Skills   │   │  User Skills    │   │ Package Skills  │   │
│  │ (Anthropic+自定义)│  │ (PostgreSQL)    │   │  (Agent 内置)   │   │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘   │
│           │                     │                     │             │
│           │           ┌─────────┴─────────┐           │             │
│           │           │ UserSkillService  │           │             │
│           │           │  (按 user_id 隔离) │           │             │
│           │           └─────────┬─────────┘           │             │
│           │                     │                     │             │
│           └──────────┬──────────┼──────────┬──────────┘             │
│                      ▼          ▼          ▼                        │
│           ┌──────────────────────────────────────────┐              │
│           │          SkillResolver                   │              │
│           │  (统一解析：系统 > 用户 > Package)         │              │
│           └──────────────────────────────────────────┘              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| UserSkillService | `backend/services/user_skill_service.py` | 用户 Skill CRUD |
| UserSkillRepository | `backend/repositories/user_skill_repository.py` | 数据库操作 |
| SkillResolver | `backend/skills/resolver.py` | 统一 Skill 解析（合并系统和用户 Skills） |
| UserSkillRouter | `backend/core/user_skills_router.py` | REST API 端点 |

### API 设计

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/user/skills` | GET | User | 列出当前用户的 Skills |
| `/api/user/skills` | POST | User | 创建新 Skill |
| `/api/user/skills/{id}` | GET | User | 获取 Skill 详情 |
| `/api/user/skills/{id}` | PUT | User | 更新 Skill |
| `/api/user/skills/{id}` | DELETE | User | 删除 Skill |
| `/api/user/skills/{id}/enable` | PATCH | User | 启用 Skill |
| `/api/user/skills/{id}/disable` | PATCH | User | 禁用 Skill |
| `/api/skills/available` | GET | User | 列出当前用户可用的所有 Skills（系统+用户） |

### 前端组件

| 组件 | 路径 | 功能 |
|------|------|------|
| SkillList | `components/Skills/SkillList.tsx` | 展示用户 Skills 列表 |
| SkillEditor | `components/Skills/SkillEditor.tsx` | 创建/编辑 Skill |
| SkillCard | `components/Skills/SkillCard.tsx` | 单个 Skill 卡片 |
| SkillMarket | `components/Skills/SkillMarket.tsx` | 浏览系统 Skills (P2) |

---

## 实现计划

### Phase 1: 基础 CRUD (P1, 2天)

1. 创建 `user_skills` 表迁移
2. 实现 `UserSkillRepository`
3. 实现 `UserSkillService`
4. 实现 REST API 端点
5. 集成到 `SkillResolver`

### Phase 2: 前端管理界面 (P1, 2天)

1. 创建 Skills 管理页面
2. 实现 Skill 列表/创建/编辑组件
3. 集成到 Admin/个人设置面板

### Phase 3: 运行时集成 (P1, 1天)

1. 修改 `activate_skill` 支持用户 Skills
2. 修改 InputBar `/skill` 解析支持用户 Skills
3. 添加权限检查

### Phase 4: 增强功能 (P2)

1. Skill 版本历史
2. Skill 导入/导出
3. Skill 市场（分享）
4. 对话式 Skill Creator

---

## 技术决策

1. **存储方式**: PostgreSQL（而非文件系统），便于用户隔离和权限管理
2. **命名空间**: 用户 Skills 不添加前缀，但解析时系统 Skills 优先
3. **Skill 执行**: 复用现有 `activate_skill` 工具，只需修改 Skill 查找逻辑
4. **权限模型**: 用户只能访问自己的 Skills，管理员可管理所有 Skills

---

## 成功标准

- SC-001: 用户可在 30 秒内创建一个简单 Skill
- SC-002: 用户 Skill 与系统 Skill 同名时，系统 Skill 优先
- SC-003: 禁用的 Skill 不出现在可用列表中
- SC-004: 删除 Skill 后对话中引用不会报错（优雅降级）
