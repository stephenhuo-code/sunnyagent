# Research: 插件管理系统

**Feature**: 012-plugin-management
**Date**: 2026-02-21

## 1. 现有 Skills 系统架构

### Decision: 保留现有 SKILL_REGISTRY，新增用户级过滤层

**Rationale**:
- 现有 `SKILL_REGISTRY` 已支持 atomic/workflow 两种类型
- `WORKFLOW_SKILLS` 字典存储 workflow skill 元数据
- 两层结构清晰，无需重构

**Alternatives Considered**:
- 统一为 PLUGIN_REGISTRY（增加复杂度，推迟到后续版本）

### 现有实现细节

**SkillEntry 结构**（`backend/skills/registry.py`）:
```python
@dataclass
class SkillEntry:
    name: str
    description: str
    skill_type: SkillType  # "atomic" | "workflow"
    load_instructions: Callable[[], str]  # Lazy loading
    steps: list[SkillStep] | None = None
    source: str = "custom"
```

**YAML Frontmatter 格式**（SKILL.md）:
```yaml
---
name: skill-name
description: Short description
type: workflow  # Optional, default: "atomic"
steps:          # Required for workflow
  - id: step1
    description: First step
    required_capability: web_search
---
```

**加载来源**:
- `skills/anthropic/skills/` - Anthropic 开源 skills (submodule)
- `skills/custom/` - 项目自定义 skills

---

## 2. 现有 Package Agent 系统

### Decision: 复用 deepagents FilesystemBackend，扩展加载器支持用户目录

**Rationale**:
- `deepagents` 的 `FilesystemBackend` 已实现目录隔离
- 现有 loader 结构清晰，易于扩展

**Alternatives Considered**:
- 自定义 Agent 加载框架（增加维护成本）

### 现有实现细节

**Package 结构**:
```
packages/
  content-writer/
    AGENTS.md          # Agent 系统提示 + 元数据
    skills/            # 可选：包内 skills
      blog-post/
        SKILL.md
```

**AGENTS.md 格式**:
```yaml
---
name: content-writer
description: Agent description
capabilities:
  - content_generation
  - writing
---
# System prompt content
```

**关键函数**（`backend/agents/loader.py`）:
- `load_package_agents()` - 扫描 packages/ 目录
- `_register_package()` - 注册单个 package

---

## 3. AIME Planner 中的 Skill 使用

### Decision: 复用现有 _expand_workflow_skill()，在 intent 层增加 skill 字段

**Rationale**:
- Planner 已有完整的 workflow skill 展开逻辑（第 1404-1455 行）
- SubtaskSpec 已支持 `skill_name` 和 `skill_step_id` 字段

**Alternatives Considered**:
- 重写 skill 执行引擎（不必要，现有实现完备）

### Workflow 执行机制

**展开流程**:
1. `_expand_workflow_skill(skill_name, message)` 读取步骤定义
2. 为每个步骤生成 `SubtaskSpec`
3. 相邻步骤自动建立 `depends_on` 依赖
4. `required_capability` 用于 Agent 匹配

**集成点**:
- IntentAnalyzer 识别 `/skill-name` 命令
- IntentResult.skill 字段传递 skill 名称
- `_handle_delegate()` 检测 skill 并转为计划执行

---

## 4. 用户数据隔离模式

### Decision: 采用与 conversations/files 一致的 user_id 隔离模式

**Rationale**:
- 现有模式已验证，符合安全边界原则
- 所有查询包含 `user_id` 过滤
- 软删除 `is_deleted` 而非物理删除

**Alternatives Considered**:
- 基于角色的多租户（过于复杂）

### 隔离模式示例

```python
# 查询用户数据的标准模式
async def get_user_resource(resource_id: UUID, user_id: UUID):
    row = await fetchrow(
        """SELECT * FROM resources
           WHERE id = $1 AND user_id = $2 AND NOT is_deleted""",
        resource_id, user_id
    )
```

---

## 5. 文件上传机制

### Decision: 复用现有文件上传 API，扩展支持 ZIP 解压

**Rationale**:
- 现有 `/api/files/upload` 已实现完整上传流程
- 文件大小限制（10MB）与 spec 一致

**Alternatives Considered**:
- 对象存储（S3/MinIO）- 推迟到扩展阶段

### 上传存储策略

**插件包存储路径**:
```
/data/plugins/
  preset/           # 内置插件（git tracked）
  packages/         # Package 插件（packages/ 目录）
  uploaded/         # 用户上传
    {user_id}/
      {plugin_id}/
        AGENTS.md / SKILL.md
        skills/
  shared/           # 分享的插件（引用 uploaded）
```

---

## 6. 插件状态与评分存储

### Decision: 新建 user_plugin_states 和 plugin_ratings 表

**Rationale**:
- 插件启用状态按用户独立存储
- 评分支持统计聚合

### 数据库设计

**user_plugin_states 表**:
```sql
CREATE TABLE user_plugin_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR NOT NULL,       -- 命名空间格式: {source}:{name}
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);
```

**plugin_ratings 表**:
```sql
CREATE TABLE plugin_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR NOT NULL,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);
```

**uploaded_plugins 表**:
```sql
CREATE TABLE uploaded_plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_name VARCHAR NOT NULL,
    plugin_type VARCHAR NOT NULL CHECK (plugin_type IN ('agent', 'skill')),
    display_name VARCHAR NOT NULL,
    description TEXT,
    version VARCHAR DEFAULT '1.0.0',
    author VARCHAR,
    storage_path VARCHAR NOT NULL,
    is_shared BOOLEAN DEFAULT FALSE,
    is_delisted BOOLEAN DEFAULT FALSE,  -- 取消分享后保留
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, plugin_name)
);
```

---

## 7. 统一管理策略

### Decision: Skills 和 Agents 在 UI 层统一展示，注册层保持独立

**Rationale**:
- UI 统一管理降低用户认知负担
- 保持 SKILL_REGISTRY 和 AGENT_REGISTRY 独立，便于后续演进

### 统一展示模型

```typescript
interface PluginInfo {
  name: string;                    // 唯一标识 {source}:{name}
  displayName: string;
  type: 'agent' | 'skill';
  source: 'preset' | 'package' | 'uploaded' | 'shared';
  description: string;
  version: string;
  author: string;
  enabled: boolean;

  // Agent 专有
  capabilities?: string[];
  commands?: string[];             // /command 列表
  skills?: SkillInfo[];            // 包含的 skills

  // Skill 专有
  skillType?: 'atomic' | 'workflow';
  steps?: SkillStep[];

  // 评分（Package/Shared 才有）
  rating?: {
    average: number;
    count: number;
  };

  // 上传/分享相关
  uploaderId?: string;             // 上传者 ID
  isDelisted?: boolean;            // 已下架
}
```

---

## 8. 命名空间隔离

### Decision: 采用 `{source}:{name}` 格式

**Rationale**:
- 避免不同来源的同名冲突
- 支持明确识别插件来源

**格式示例**:
- `preset:research` - 内置研究 agent
- `package:content-writer` - Package agent
- `uploaded:my-agent` - 用户上传
- `shared:community-tool` - 已分享

---

## 9. 分享机制

### Decision: Shared 插件引用原 uploaded 目录，不复制文件

**Rationale**:
- 避免文件冗余
- 原作者更新自动同步到所有启用者

### 分享流程

1. 用户点击"分享" → `uploaded_plugins.is_shared = true`
2. 插件出现在插件市场 "Shared" 标签
3. 其他用户启用 → 创建 `user_plugin_states` 记录
4. 原作者取消分享 → `is_shared = false, is_delisted = true`
5. 已启用用户保留使用，但标记"已下架"

---

## 10. Agent Skills 与 SKILL_REGISTRY 统一

### Decision: 全局统一 SKILL_REGISTRY，替换 deepagents SkillsMiddleware

**Current Problem**:
- 独立 skills（`skills/anthropic/`, `skills/custom/`）注册到 `SKILL_REGISTRY`
- Package Agent 的 skills 由 deepagents `SkillsMiddleware` 管理，**不在 SKILL_REGISTRY**
- 导致 `/api/skills` 无法返回 Agent 内部的 skills
- /命令自动完成也无法显示这些 skills
- 两套 skills 系统，概念混乱

**深入分析 deepagents SkillsMiddleware**:

经过代码分析，deepagents 的 skills 机制本质上是：
1. 扫描 Backend 的 `/skills/` 目录
2. 解析 SKILL.md frontmatter (name, description)
3. 将摘要注入系统提示（Progressive Disclosure）
4. Agent 通过 `read_file` 工具读取完整指令

**这只是一个文件命名空间 + 系统提示注入机制，不是能力注册。**

**Solution: 自己实现，替换 deepagents SkillsMiddleware**

```python
# backend/agents/loader.py
def _register_package(pkg_dir: Path) -> None:
    # 1. 加载 Package skills 到全局 SKILL_REGISTRY
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        from backend.skills.loader import load_skills_from_directory
        load_skills_from_directory(skills_dir, source=f"package:{agent_name}")

    # 2. 创建 Agent，不传 skills 参数（不用 SkillsMiddleware）
    agent = create_deep_agent(
        model=model,
        backend=backend,
        skills=None,  # ← 关键：不使用 deepagents skills
        memory=memory,
        name=agent_name,
        checkpointer=get_checkpointer(),
    )
```

**统一的 Skills 来源**:

| source 值 | 描述 | 示例 |
|-----------|------|------|
| `preset` | 内置 Anthropic skills | summarize, research |
| `custom` | 项目自定义 skills | my-workflow |
| `package:{agent}` | Package Agent 的 skills | package:content-writer |
| `uploaded:{user_id}` | 用户上传的 skills | uploaded:user-123 |
| `shared` | 用户分享的 skills | shared |

**方案对比**:

| 方面 | 当前 (deepagents skills) | 替换后 (统一 SKILL_REGISTRY) |
|------|-------------------------|------------------------------|
| **统一管理** | ❌ 两套系统 | ✅ 单一注册中心 |
| **API 可见** | ❌ Package skills 不可见 | ✅ 全部可通过 `/api/skills` 查询 |
| **/命令调用** | ❌ Package skills 不支持 | ✅ 全部支持 /命令 |
| **启用/禁用** | ❌ 无法控制 | ✅ 统一的 UserPluginState |
| **跨 Agent 共享** | ❌ 隔离在 Package 内 | ✅ 任何 Agent 可用 |
| **用户上传** | ❌ 无统一机制 | ✅ 统一的上传和注册 |

**需要保留的 deepagents 能力**:

| 中间件 | 保留 | 说明 |
|--------|------|------|
| `FilesystemMiddleware` | ✅ | 文件操作工具 (ls, read, write, edit) |
| `MemoryMiddleware` | ✅ | AGENTS.md 系统提示加载 |
| `SubAgentMiddleware` | ✅ | 子 Agent 调用 |
| `SummarizationMiddleware` | ✅ | 上下文压缩 |
| `SkillsMiddleware` | ❌ 替换 | 用 SKILL_REGISTRY + activate_skill 工具 |

**Rationale**: 符合 spec 中"Skills 统一管理"架构约束（FR-033 到 FR-036）

**设计选择记录**:
- ❌ Agent 作用域隔离（过于复杂，增加用户认知负担）
- ✅ 全局统一可见（简单清晰，符合"用户无需关心 skill 技术来源"原则）

---

## 11. 统一的 Agent 加载机制

### Decision: 所有来源的 Agent 统一使用 deepagents

**Rationale**:
- Package Agent 已使用 deepagents，结构成熟
- 用户上传的 Agent 结构与 Package Agent 相同（AGENTS.md + 可选 skills/）
- 复用 deepagents 的中间件能力（文件操作、上下文压缩等）
- 统一加载逻辑，降低维护成本

**统一加载架构**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Agent 来源                                 │
├─────────────────────────────────────────────────────────────────────┤
│  packages/               │  uploaded/{user_id}/    │  shared/       │
│  ├─ content-writer/      │  ├─ my-agent/          │  ├─ tool-x/    │
│  │   ├─ AGENTS.md        │  │   ├─ AGENTS.md      │  │   ├─ ...    │
│  │   └─ skills/          │  │   └─ skills/        │  │   └─ ...    │
└──────────┬───────────────┴──────────┬─────────────┴───────┬────────┘
           │                          │                      │
           └──────────────────────────┼──────────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  load_agent_from_directory()        │
                    │  (统一加载函数，复用 deepagents)     │
                    └─────────────────────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
   ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
   │ SKILL_REGISTRY│         │ AGENT_REGISTRY│         │  deepagent    │
   │ (注册 skills) │         │ (注册 agent)  │         │  (运行实例)   │
   └───────────────┘         └───────────────┘         └───────────────┘
```

**加载时机差异**:

| 来源 | 加载时机 | 触发方式 |
|------|----------|----------|
| **Package** | 启动时 | 扫描 `packages/` 目录，静态加载 |
| **Uploaded** | 上传时 | 用户上传后动态加载到内存 |
| **Shared** | 用户启用时 | 首次启用时动态加载 |

**统一加载函数设计**:

```python
def load_agent_from_directory(
    pkg_dir: Path,
    source: str,           # "package" | "uploaded" | "shared"
    user_id: UUID | None,  # uploaded/shared 时需要
) -> tuple[str, CompiledStateGraph]:
    """统一的 Agent 加载函数"""

    # 1. 解析 AGENTS.md 元数据
    frontmatter = parse_agents_md_frontmatter(pkg_dir / "AGENTS.md")
    agent_name = frontmatter.get("name", pkg_dir.name)

    # 2. 注册 skills 到全局 SKILL_REGISTRY
    skills_dir = pkg_dir / "skills"
    if skills_dir.is_dir():
        load_skills_from_directory(skills_dir, source=f"{source}:{agent_name}")

    # 3. 创建 deepagent (不使用 SkillsMiddleware)
    agent = create_deep_agent(
        model=get_model(agent_name),
        backend=FilesystemBackend(root_dir=pkg_dir, virtual_mode=True),
        skills=None,  # 使用 SKILL_REGISTRY 替代
        memory=["/AGENTS.md"],
        name=agent_name,
        checkpointer=get_checkpointer(),
    )

    # 4. 注册到 AGENT_REGISTRY
    register_agent(name=agent_name, graph=agent, source=source, user_id=user_id)

    return agent_name, agent
```

**Benefits**:
- 代码复用：一套加载逻辑适用所有来源
- 一致性：所有 Agent 具有相同的能力（文件操作、上下文压缩等）
- 可维护性：修改一处，全部生效

---

## 12. 实现优先级

### Phase 1 (MVP)
1. **统一 Skills 注册** - Package Agent skills 同步注册到 SKILL_REGISTRY
2. 数据库迁移（3 张新表）
3. 插件列表 API（合并所有来源）
4. 启用/禁用 API
5. 前端插件管理页面

### Phase 2
6. 上传插件 API + 解压验证
7. 前端上传弹窗
8. AIME 集成用户插件状态过滤

### Phase 3
9. 插件评分 API
10. 分享/取消分享 API
11. Workflow Skill 增强（/command 触发）

---

## 13. Package 热加载架构

### Decision: 启动时全量加载 + 运行时扫描新 Package

**Rationale**:
- 启动时加载所有现有 packages，确保服务可用
- 运行时支持热添加新 package，无需重启
- Package 默认禁用，用户需手动启用

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    服务启动                                  │
│   load_package_agents()  ← 加载所有现有 packages             │
│   所有 agents/skills 注册到全局 REGISTRY                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              全局 REGISTRY（所有用户共享）                    │
│   AGENT_REGISTRY: { "content-writer": agent, ... }          │
│   SKILL_REGISTRY: { "blog-post": skill, ... }               │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         ▼                                         ▼
┌─────────────────────────┐          ┌─────────────────────────┐
│   用户打开插件页面       │          │   用户发消息             │
│         ↓               │          │         ↓               │
│   GET /api/plugins      │          │   POST /api/chat        │
│         ↓               │          │         ↓               │
│   scan_and_load_new()   │          │   AIME 检查用户启用状态  │
│   发现新 package → 加载  │          │   过滤可用 agents       │
└─────────────────────────┘          └─────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据库（per-user 状态）                   │
│   user_plugin_states:                                       │
│     用户 A: { "package:content-writer": enabled=true }      │
│     用户 B: { "package:content-writer": enabled=false }     │
│                                                             │
│   Package 默认禁用，需明确启用记录才可用                      │
└─────────────────────────────────────────────────────────────┘
```

### 热加载函数设计

**backend/agents/loader.py**:

```python
# 记录已加载的 package 名称
_LOADED_PACKAGES: set[str] = set()

def scan_and_load_new_packages() -> list[str]:
    """扫描 packages/ 目录，加载新发现的 packages。

    Returns:
        新加载的 package 名称列表
    """
    if not _PACKAGES_DIR.is_dir():
        return []

    newly_loaded = []
    for pkg_dir in sorted(_PACKAGES_DIR.iterdir()):
        if not pkg_dir.is_dir():
            continue

        agents_md = pkg_dir / "AGENTS.md"
        if not agents_md.exists():
            continue

        # 解析 frontmatter 获取 agent name
        frontmatter = _parse_agents_md_frontmatter(agents_md)
        name = str(frontmatter.get("name", pkg_dir.name))

        # 跳过已加载的
        if name in _LOADED_PACKAGES:
            continue

        # 加载新 package
        _register_package(pkg_dir)
        _LOADED_PACKAGES.add(name)
        newly_loaded.append(name)

    return newly_loaded
```

### Package 默认禁用逻辑

**backend/plugins/database.py**:

```python
async def get_enabled_package_plugins(user_id: UUID) -> set[str]:
    """获取用户明确启用的 package 插件。

    Package 类型默认禁用，只返回明确启用的。
    """
    query = """
        SELECT plugin_name FROM user_plugin_states
        WHERE user_id = $1 AND plugin_name LIKE 'package:%' AND enabled = TRUE
    """
    rows = await fetch_all(query, user_id)
    return {row["plugin_name"] for row in rows}
```

**backend/plugins/service.py**:

```python
async def get_all_plugins(...) -> list[PluginInfo]:
    # 热加载新 packages
    from backend.agents.loader import scan_and_load_new_packages
    newly_loaded = scan_and_load_new_packages()

    # 获取用户明确启用的 package 插件
    enabled_packages = await plugin_db.get_enabled_package_plugins(user_id)

    for entry in AGENT_REGISTRY.values():
        plugin_name = f"{entry.source}:{entry.name}"

        # Package 默认禁用，其他类型默认启用
        if entry.source == "package":
            enabled = plugin_name in enabled_packages
        else:
            enabled = plugin_name not in disabled_plugins

        # ... 构建 PluginInfo ...
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 注册表数量 | 全局共享一份 | 代码共享，per-user 状态靠数据库 |
| 加载时机 | 启动 + 打开插件页时 | 平衡启动速度和热加载需求 |
| Package 默认状态 | 禁用 | 用户明确意图，避免新 package 自动生效 |
| Skills 跟随 Agent | 是 | Agent 启用时其 skills 同步可用 |

### 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/agents/loader.py` | 新增 `scan_and_load_new_packages()`，`_LOADED_PACKAGES` 集合 |
| `backend/plugins/service.py` | 调用热加载函数，修改 Package 默认禁用逻辑 |
| `backend/plugins/database.py` | 新增 `get_enabled_package_plugins()` 函数 |
