# Feature Specification: 插件管理系统 (Plugin Management)

**Feature Branch**: `012-plugin-management`
**Created**: 2026-02-21
**Status**: Draft
**Input**: 开发和优化 skills 管理、自定义 agent、agent 管理界面三个 feature

## Clarifications

### Session 2026-02-21

- Q: 分享的插件被原作者删除时，已启用该插件的用户如何处理？ → A: 禁止删除，分享的插件不允许删除，只能取消分享
- Q: 同名插件冲突如何处理？ → A: 命名空间隔离，按来源加前缀区分（如 `preset:xxx`、`shared:xxx`）
- Q: 取消分享后已启用该插件的用户如何处理？ → A: 保留副本，已启用的用户保留使用，但标记为"已下架"
- Q: 插件版本升级策略？ → A: 直接覆盖，上传同名插件时直接替换，不保留历史版本
- Q: 已分享插件更新推送策略？ → A: 自动更新，原作者更新后所有启用该插件的用户自动获得新版本

---

## 调研结论（基于现有实现）

### 当前 Skills 实现

**文件结构**：
- `backend/skills/registry.py` - 技能注册中心，支持 atomic 和 workflow 两种类型
- `backend/skills/loader.py` - 从 SKILL.md 文件加载技能，解析 YAML frontmatter
- 技能来源：`skills/anthropic/skills/`（git submodule）和 `skills/custom/`

**特点**：
- 技能通过 YAML frontmatter 定义 name、description、type、steps
- 支持延迟加载指令内容
- workflow 技能可定义多步骤，每步可指定 required_capability

### 当前 Package Agent 实现

**文件结构**：
- `backend/agents/loader.py` - 从 packages/ 目录加载 agent
- 每个 package 必须包含 AGENTS.md，可选包含 skills/ 子目录

**特点**：
- 使用 deepagents 框架的 FilesystemBackend
- 支持 YAML frontmatter 定义 name、description、capabilities
- agent 的 skills 通过 `/skills/` 路径自动加载
- 注册时 `show_in_selector=False`（不在前端选择器显示）

### 需要优化的问题

1. **缺乏统一管理界面** - 无法查看/管理已加载的 agent 和 skill
2. **无启用/禁用控制** - 所有加载的 agent/skill 默认全部启用
3. **无用户级权限控制** - 无法按用户控制 agent/skill 访问权限
4. **无上传机制** - 当前只支持预先放置在目录中的包

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 浏览已安装插件 (Priority: P1)

用户需要查看系统中所有可用的插件（agent 和 skill），了解它们的功能和状态，以便选择启用哪些插件。

**Why this priority**: 这是所有插件操作的基础，没有可见性就无法进行任何管理

**Independent Test**: 用户登录后进入插件管理页面，可以看到所有插件的列表、状态和描述信息

**Acceptance Scenarios**:

1. **Given** 用户已登录, **When** 进入插件管理页面, **Then** 显示所有可用的插件列表（包括 preset 和 package 来源）
2. **Given** 插件管理页面已打开, **When** 点击某个插件, **Then** 显示该插件的详细信息（描述、Commands、Skills）
3. **Given** 插件管理页面已打开, **When** 切换到 Skills 标签, **Then** 显示该插件的所有 skill

---

### User Story 2 - 浏览插件市场 (Priority: P1)

用户需要浏览所有可用的插件市场，发现新插件并选择安装到自己的工作环境。

**Why this priority**: 这是用户发现和获取新插件的主要入口，与已安装插件浏览共同构成完整的插件管理体验

**Independent Test**: 用户点击 "+" 按钮后可以浏览所有可用插件，按分类筛选，搜索特定插件

**Acceptance Scenarios**:

1. **Given** 用户在插件管理页面, **When** 点击 "+" 按钮并选择 "Browse plugins", **Then** 打开插件市场弹窗
2. **Given** 插件市场弹窗打开, **When** 切换标签页（Preset / Package / Uploaded）, **Then** 显示对应分类的插件列表
3. **Given** 插件市场弹窗打开, **When** 在搜索框输入关键词, **Then** 实时过滤显示匹配的插件
4. **Given** 插件市场显示某个未安装的插件, **When** 点击该插件卡片, **Then** 显示插件详情并提供安装/启用选项
5. **Given** 插件市场显示某个已安装的插件, **When** 查看该插件卡片, **Then** 显示 "Manage" 按钮跳转到详情页

---

### User Story 3 - 启用/禁用插件 (Priority: P2)

用户需要控制哪些插件和 skill 对自己可用，以便个性化自己的工作环境。

**Why this priority**: 提供灵活的个性化控制，用户可以根据需要启用或禁用功能

**Independent Test**: 用户禁用某个插件后，该插件的 Commands 和 Skills 不再出现在自动完成列表中

**Acceptance Scenarios**:

1. **Given** 插件列表显示, **When** 用户点击某插件的禁用开关, **Then** 该插件状态变为禁用，AIME 路由不再选择该插件
2. **Given** 某插件被禁用, **When** 用户在对话中输入 `/`, **Then** 该插件的 Commands 和 Skills 不出现在自动完成列表
3. **Given** 某插件被禁用, **When** 用户点击启用开关, **Then** 该插件重新可用
4. **Given** 插件有多个 skills, **When** 禁用该插件, **Then** 同时禁用其所有 skills；启用插件时同时启用所有 skills

---

### User Story 4 - 上传插件包 (Priority: P3)

用户需要通过上传文件包的方式安装自己的插件，扩展系统功能。

**Why this priority**: 允许用户自定义扩展，提升系统灵活性

**Independent Test**: 上传有效的插件包后，该插件自动出现在用户的插件列表中并可立即使用

**Acceptance Scenarios**:

1. **Given** 用户在插件管理页面, **When** 点击上传按钮并选择有效的插件包（zip 格式，包含 AGENTS.md）, **Then** 系统解压并注册该插件
2. **Given** 上传了包含 skills/ 目录的插件包, **When** 上传完成, **Then** 插件的 skills 同时被注册
3. **Given** 用户上传无效的包（缺少 AGENTS.md）, **When** 上传完成, **Then** 显示错误提示，不注册任何内容
4. **Given** 上传的插件包与已存在的插件同名, **When** 上传, **Then** 提示用户选择是否覆盖

---

### User Story 5 - 对话中使用 /命令调用 Skill (Priority: P1)

用户在对话窗口中可以通过 /命令 直接调用特定的 skill，获得针对性的帮助。

**Why this priority**: 这是 skill 系统的核心用户交互方式，与 P1 的浏览功能共同构成 MVP

**Independent Test**: 用户在对话框输入 /skill-name，系统自动注入对应 skill 的指令并执行

**Acceptance Scenarios**:

1. **Given** 用户在对话输入框, **When** 输入 `/` 字符, **Then** 显示可用 skill 列表（自动完成）
2. **Given** skill 自动完成列表显示, **When** 选择或输入完整的 skill 名称, **Then** 该 skill 被标记到消息中
3. **Given** 消息包含 skill 标记, **When** 发送消息, **Then** 后端注入 skill 指令并处理请求
4. **Given** 用户输入不存在的 skill 名称, **When** 发送消息, **Then** 系统提示 skill 不存在，列出可用 skills

---

### User Story 6 - Workflow Skill 任务规划 (Priority: P2)

用户调用 workflow 类型的 skill 时，系统自动进行多步骤任务规划和执行，无需用户手动拆解复杂任务。

**Why this priority**: Workflow skills 是复杂任务自动化的核心能力，提升用户处理多步骤任务的效率

**Independent Test**: 用户调用一个 workflow skill 后，系统自动按预定义步骤规划任务，依次执行并汇总结果

**Acceptance Scenarios**:

1. **Given** 用户调用一个 workflow skill, **When** 消息发送, **Then** Planner 识别为 workflow 类型并读取步骤定义
2. **Given** workflow skill 包含多个步骤, **When** Planner 规划任务, **Then** 按步骤顺序生成执行计划
3. **Given** 执行计划生成完成, **When** 开始执行, **Then** 依次执行每个步骤，显示进度
4. **Given** 某步骤指定了 required_capability, **When** 执行该步骤, **Then** 自动选择具备该能力的 agent
5. **Given** workflow 执行完成, **When** 所有步骤结束, **Then** 汇总各步骤结果返回给用户

**Skill 类型说明**：

| 类型 | 执行方式 | 适用场景 |
|------|----------|----------|
| atomic | 单次执行，直接注入指令 | 简单任务，单一操作 |
| workflow | Planner 规划，多步骤执行 | 复杂任务，需要多个 agent 协作 |

---

### User Story 7 - 插件评分 (Priority: P3)

用户可以对插件市场中的 package 或 skill 进行评分，帮助其他用户发现优质插件。

**Why this priority**: 评分系统提升插件发现效率，但不是核心功能

**Independent Test**: 用户对某个插件评分后，该评分显示在插件详情页，其他用户可以看到平均评分

**Acceptance Scenarios**:

1. **Given** 用户查看某个 Package 或 Shared 插件详情, **When** 点击评分区域, **Then** 显示评分选项（1-5 星）
2. **Given** 用户选择评分, **When** 提交评分, **Then** 系统记录该用户对该插件的评分
3. **Given** 插件有多个用户评分, **When** 查看插件详情, **Then** 显示平均评分和评分人数
4. **Given** 用户已对某插件评分, **When** 再次评分, **Then** 更新该用户的评分（每用户每插件仅一个评分）

---

### User Story 8 - 分享插件 (Priority: P3)

用户可以将自己上传的插件分享到插件市场，分享后该插件对所有用户可见。

**Why this priority**: 分享机制促进用户贡献，但依赖上传功能完成

**Independent Test**: 用户分享自己上传的插件后，该插件出现在插件市场的 "Shared" 分类中，其他用户可以看到并启用

**Acceptance Scenarios**:

1. **Given** 用户查看自己上传的插件详情, **When** 点击 "分享" 按钮, **Then** 显示分享确认对话框
2. **Given** 分享确认对话框显示, **When** 用户确认分享, **Then** 插件状态变为 "Shared"，对所有用户可见
3. **Given** 插件已分享, **When** 其他用户浏览插件市场, **Then** 可以在 "Shared" 分类中看到该插件
4. **Given** 插件已分享, **When** 原上传者查看插件, **Then** 显示 "取消分享" 选项
5. **Given** 用户取消分享, **When** 确认取消, **Then** 插件恢复为仅上传者可见

---

### Edge Cases

- 上传的 agent 包格式错误（非 zip、损坏、目录结构不符合规范）时的处理
- agent/skill 正在被对话使用时禁用该 agent/skill
- 同名插件通过命名空间隔离处理，格式 `{source}:{name}`（已澄清）
- 上传的包大小超过限制
- 并发上传同一个插件包
- 禁用所有可处理某类请求的 agent 后的降级策略
- 分享的插件不允许删除，必须先取消分享后才能删除（已澄清）
- 分享的插件与已有插件同名时的冲突处理

## Requirements *(mandatory)*

### Functional Requirements

**插件管理页面（左侧边栏）**：
- **FR-001**: 系统 MUST 在左侧边栏展示所有已安装的插件列表
- **FR-002**: 每个插件项 MUST 显示图标、名称、启用状态标签
- **FR-003**: 点击插件 MUST 展开子导航（Commands、Skills 等分类）
- **FR-004**: 系统 MUST 提供 "+" 按钮用于添加插件

**插件详情面板（右侧）**：
- **FR-005**: 系统 MUST 显示插件元数据：名称、来源（Source）、版本（Version）、作者（Author）
- **FR-006**: 系统 MUST 显示插件描述（Description）
- **FR-007**: 系统 MUST 以标签形式展示插件的 Commands（/命令列表）
- **FR-008**: 系统 MUST 以标签形式展示插件的 Skills 列表
- **FR-009**: 系统 MUST 提供启用/禁用开关控制插件状态

**Browse Plugins 弹窗**：
- **FR-010**: 系统 MUST 提供插件浏览弹窗，展示所有可用插件
- **FR-011**: 弹窗 MUST 支持按来源分类标签页（Preset / Package / Uploaded）
- **FR-012**: 弹窗 MUST 提供搜索功能过滤插件
- **FR-013**: 插件卡片 MUST 显示图标、名称、版本、描述
- **FR-014**: 已安装插件 MUST 显示 "Manage" 按钮跳转到详情

**启用/禁用控制**：
- **FR-015**: 用户 MUST 能够通过详情面板开关启用/禁用插件
- **FR-016**: 禁用插件时 MUST 同时禁用其所有 Commands 和 Skills
- **FR-017**: 启用/禁用状态 MUST 持久化存储
- **FR-018**: AIME 路由 MUST 仅考虑已启用的插件及其 skills

**上传功能**：
- **FR-019**: 点击 "+" → "Upload plugin" MUST 打开文件上传对话框
- **FR-020**: 系统 MUST 支持上传 zip 格式的插件包
- **FR-021**: 系统 MUST 验证上传的包结构（必须包含 AGENTS.md 或 SKILL.md）
- **FR-022**: 上传成功后系统 MUST 自动解析并注册插件
- **FR-023**: 上传的插件 MUST 出现在 "Uploaded" 分类标签页中
- **FR-056**: 上传同名插件时 MUST 直接覆盖原版本，不保留历史版本

**/命令调用（对话窗口）**：
- **FR-024**: 对话输入框 MUST 支持 `/` 触发 skill/command 自动完成
- **FR-025**: 自动完成列表 MUST 仅显示当前用户已启用插件的 commands/skills
- **FR-026**: 选中后 MUST 在消息中标记该 skill
- **FR-027**: 后端 MUST 识别 skill 标记并注入对应指令

**权限与数据隔离**：
- **FR-028**: Preset 和 Package 插件 MUST 对所有用户可见
- **FR-029**: Uploaded 插件 MUST 仅对上传者可见
- **FR-030**: 启用/禁用状态 MUST 按用户独立存储
- **FR-031**: 用户 MUST 只能删除自己上传的插件
- **FR-032**: AIME 路由 MUST 根据当前用户的插件设置过滤可用插件
- **FR-053**: 插件唯一标识 MUST 采用命名空间隔离，格式为 `{source}:{name}`（如 `preset:research`、`shared:my-plugin`）

**Skills 统一管理**：
- **FR-033**: Agent 内置 skills 和通用 skills MUST 在同一界面统一展示
- **FR-034**: 通用 skills MUST 聚合为"通用插件"分组显示
- **FR-035**: Skills 搜索和筛选 MUST 覆盖所有来源的 skills
- **FR-036**: /命令自动完成 MUST 包含所有已启用的 skills（无论来源）

**Workflow Skill 执行**：
- **FR-037**: 系统 MUST 区分 atomic 和 workflow 两种 skill 类型
- **FR-038**: Workflow skill 调用时，Planner MUST 读取 steps 定义进行任务规划
- **FR-039**: Planner MUST 按步骤顺序生成执行计划
- **FR-040**: 每个步骤 MUST 支持指定 required_capability 用于 agent 选择
- **FR-041**: Workflow 执行过程 MUST 显示当前步骤进度
- **FR-042**: Workflow 完成后 MUST 汇总各步骤结果返回用户

**插件评分**：
- **FR-043**: 用户 MUST 能够对 Package 和 Shared 来源的插件评分（1-5 星）
- **FR-044**: 每个用户对每个插件 MUST 只能有一个评分（可修改）
- **FR-045**: 插件详情页 MUST 显示平均评分和评分人数
- **FR-046**: 插件市场卡片 MUST 显示平均评分

**插件分享**：
- **FR-047**: 用户 MUST 能够将自己上传的插件分享到插件市场
- **FR-048**: 分享后插件状态 MUST 变为 "Shared"，对所有用户可见
- **FR-049**: 原上传者 MUST 能够取消分享，恢复为仅自己可见
- **FR-050**: 分享的插件 MUST 显示原作者信息
- **FR-051**: 插件市场 MUST 增加 "Shared" 分类标签页
- **FR-052**: 已分享的插件 MUST NOT 允许删除，只能先取消分享后再删除
- **FR-054**: 取消分享时，已启用该插件的用户 MUST 保留使用权，但插件标记为"已下架"
- **FR-055**: "已下架"插件 MUST NOT 出现在插件市场，新用户无法启用
- **FR-057**: 已分享插件更新时，所有启用该插件的用户 MUST 自动获得新版本

### Key Entities

- **Plugin**: 插件实体，包含名称、描述、图标、来源(preset/package/uploaded/shared)、版本、作者、上传者ID（uploaded/shared）
- **Command**: 插件提供的 /命令，包含名称、描述、所属插件
- **Skill**: 插件提供的技能，包含名称、描述、类型(atomic/workflow)、所属插件
- **UserPluginState**: 用户级插件状态，关联 user_id + plugin_name，存储 enabled 布尔值
- **PluginRating**: 插件评分记录，关联 user_id + plugin_name，存储评分值(1-5)、评分时间

### 架构约束

**Skills 统一管理**：

- Agent 内置的 skills 和通用 skills（如 anthropic skills、custom skills）MUST 在同一界面统一管理
- 用户在 Skills 视图中可以看到所有来源的 skills，不区分是 agent 内置还是独立 skill
- Skills 的启用/禁用、搜索、筛选操作对所有 skills 统一生效
- 通用 skills 作为"通用插件"分组显示，与 agent 插件平级展示

**统一数据模型**：

| 类型 | 展示方式 | 说明 |
|------|----------|------|
| Agent 插件 | 独立插件卡片 | 包含 Commands + Skills 子分类 |
| 通用 Skills | "通用插件"分组 | 所有独立 skills 聚合为一个虚拟插件 |

**设计原则**：

- 用户无需关心 skill 的技术来源（agent 内置 vs 独立定义）
- 所有 skills 使用相同的启用/禁用机制
- /命令调用时，所有已启用的 skills 统一出现在自动完成列表

### 权限模型

**插件与 Skills 可见性（按来源）**：

| 来源 | 可见范围 | 插件 | Skills | 可评分 |
|------|----------|------|--------|--------|
| Preset | 所有用户 | 全局可见 | 全局可见 | 否 |
| Package | 所有用户 | 全局可见 | 全局可见 | 是 |
| Uploaded | **仅上传者** | 仅上传者可见 | **仅上传者可见** | 否 |
| Shared | 所有用户 | 全局可见 | 全局可见 | 是 |

> **重要**：
> - 用户上传的插件和 skills 只对该用户可见，其他用户无法在 /命令自动完成或插件市场中看到
> - 用户可以将 Uploaded 插件"分享"，分享后变为 Shared 状态，对所有用户可见
> - 仅 Package 和 Shared 来源的插件支持评分

**启用/禁用设置（用户级别）**：

- 每个用户拥有独立的插件启用/禁用设置
- 用户 A 禁用某插件不影响用户 B 的设置
- 新用户默认启用所有 Preset 和 Package 插件
- 用户上传的插件默认启用

**数据隔离**：

- **UserPluginState** 表按 user_id 隔离，每个用户只能读写自己的设置
- **Uploaded 插件** 按 user_id 隔离，用户只能管理自己上传的插件
- AIME 路由时，根据当前用户的 UserPluginState 过滤可用插件

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可在 3 秒内查看到完整的插件列表
- **SC-002**: 启用/禁用操作在 1 秒内生效，无需重启服务
- **SC-003**: 上传 1MB 以内的插件包在 5 秒内完成处理并注册
- **SC-004**: /命令自动完成在输入 `/` 后 200ms 内显示
- **SC-005**: 90% 的用户能在无额外指导下完成插件上传操作
- **SC-006**: 插件启用/禁用状态在服务重启后保持一致

## UI 设计参考（基于 Claude.ai 插件界面）

### 页面结构

**左侧边栏**：
- 标题：Personal plugins + "+" 添加按钮
- 插件列表：每项显示图标 + 名称 + 状态标签（如 "Disabled"）
- 子导航（选中插件后）：Commands、Connectors、Skills、[其他分类]

**右侧详情面板**：
- 标题区：插件名称 + 操作按钮（Customize）+ 启用/禁用开关
- 元数据行：Source（来源）、Version（版本）、Author（作者）
- Description：插件描述文本
- "Ask questions like..."：示例问题列表，点击可快速使用
- Commands 部分：显示 /命令 标签（如 `/analyze`、`/build-dashboard`）
- Skills 部分：显示技能标签（如 `data-context-extractor`、`data-exploration`）

### 添加插件菜单（点击 "+" 按钮）

- Browse plugins：打开插件市场弹窗
- Upload plugin：上传本地插件包

### Browse Plugins 弹窗

- 标题：Browse plugins
- 副标题：说明插件用途
- 标签页：By Anthropic（官方插件）/ Personal（个人插件）
- 搜索框：支持搜索插件
- 卡片网格布局：
  - 图标
  - Manage 按钮（已安装的插件显示）
  - 插件名称 + 版本号
  - 描述（截断显示）

### 适配说明

由于 SunnyAgent 是自部署系统，UI 设计需做以下调整：

| Claude.ai | SunnyAgent |
|-----------|------------|
| By Anthropic / Personal | Preset（内置）/ Package（包）/ Uploaded（用户上传） |
| Marketplace (Anthropic) | preset / package / uploaded |
| Update 按钮 | 不实现（用户可删除后重新上传） |
| Customize 按钮 | 保留，用于编辑插件配置 |
| Version | 从 AGENTS.md/SKILL.md 元数据读取 |
| Author | 从元数据读取，默认 "Unknown" |

## Assumptions

- 上传的插件包遵循现有的 packages/ 目录结构规范（AGENTS.md + 可选 skills/）
- 上传的 skill 包遵循现有的 skills/ 目录结构规范（SKILL.md）
- 插件状态按用户存储（每个用户独立的启用/禁用设置）
- 所有登录用户都可以访问插件管理功能
- 上传的包大小限制为 10MB（与现有文件上传限制一致）
- UI 设计参考 Claude.ai 插件管理界面，但根据自部署场景做适当调整
