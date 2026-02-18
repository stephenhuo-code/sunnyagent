# Feature Specification: Project Management

**Feature Branch**: `006-project-management`
**Created**: 2026-02-17
**Status**: Draft
**Input**: User description: "项目管理功能,以用户权限为单位,左侧导航与历史对话同级,支持项目增删改、文件上传、对话关联"

## Clarifications

### Session 2026-02-17

- Q: What file types are supported for project sources? → A: Documents + Code (PDF, DOCX, TXT, MD, CSV, JSON, common code files)
- Q: Can users create projects with duplicate names? → A: No, unique names required per user
- Q: Maximum files per project? → A: 50 files per project

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 项目基础管理 (Priority: P1)

用户需要能够创建、编辑和删除项目,项目作为组织工作的基本单元。用户登录后可以在左侧导航看到项目列表,点击可以进行项目操作。

**Why this priority**: 项目是整个功能的核心实体,没有项目就无法进行后续的文件管理和对话关联。这是最基础的功能,必须首先实现。

**Independent Test**: 可以通过创建一个新项目、修改其名称、然后删除来完整测试,无需其他功能即可验证核心价值。

**Acceptance Scenarios**:

1. **Given** 用户已登录, **When** 用户点击"新建项目"按钮并填写项目名称, **Then** 系统创建新项目并显示在项目列表中
2. **Given** 项目已存在, **When** 用户点击项目设置并修改名称, **Then** 项目名称更新成功
3. **Given** 项目已存在, **When** 用户选择删除项目并确认, **Then** 项目及其关联数据被删除
4. **Given** 用户A创建了项目, **When** 用户B尝试访问该项目, **Then** 系统拒绝访问并返回权限错误

---

### User Story 2 - 项目工作区界面 (Priority: P1)

用户点击项目后进入项目工作区,采用双栏布局:
- **左侧 Sources 面板**: 文件源管理列表,支持上传文件、多选文件、可收起
- **右侧 Chat 面板**: 对话窗口,复用现有对话实现

**Why this priority**: 工作区是用户与项目交互的主要入口,与项目管理同等重要。

**Independent Test**: 可以通过创建项目后点击进入,验证双栏布局正常显示,Sources 和 Chat 功能可用。

**Acceptance Scenarios**:

1. **Given** 项目已存在, **When** 用户点击项目名称, **Then** 系统显示项目工作区,左侧为 Sources 面板,右侧为 Chat 面板
2. **Given** 用户在项目工作区, **When** 用户点击 Sources 面板的收起按钮, **Then** Sources 面板收起,Chat 面板扩展占满宽度
3. **Given** 用户在项目工作区, **When** 用户在 Chat 面板发送消息, **Then** 对话功能与现有对话保持一致
4. **Given** 项目有关联文件, **When** 用户在 Chat 输入框看到, **Then** 显示已选择的文件数量(如 "1 source")

---

### User Story 3 - 项目导航集成 (Priority: P1)

项目列表与历史对话(History)在左侧导航中同级展示。用户可以:
- 展开项目查看其下的所有对话
- 在导航树上将对话从项目中移除
- 从历史对话列表将对话添加到项目

**Why this priority**: 导航是用户体验的关键部分,需要与现有界面无缝集成,对话与项目的关联管理是核心交互。

**Independent Test**: 可以验证左侧导航正确显示Projects和History,并测试对话的添加/移除项目操作。

**Acceptance Scenarios**:

1. **Given** 用户已登录, **When** 用户查看左侧导航, **Then** 看到Projects和History两个并列的导航项
2. **Given** 用户有多个项目, **When** 用户展开Projects, **Then** 看到所有属于该用户的项目列表
3. **Given** 项目有关联的对话, **When** 用户展开某个项目, **Then** 看到该项目下的所有对话列表
4. **Given** 项目下有对话, **When** 用户右键点击对话并选择"从项目移除", **Then** 对话从项目中移除,回到History列表
5. **Given** 用户在History列表, **When** 用户右键点击对话并选择"添加到项目", **Then** 显示项目选择菜单
6. **Given** 用户选择了目标项目, **When** 确认添加, **Then** 对话关联到该项目,在项目下显示
7. **Given** 用户在某个项目中, **When** 用户点击History, **Then** 系统切换到历史对话列表

---

### User Story 4 - 文件源管理 (Priority: P2)

用户可以在项目 Sources 面板管理文件:上传新文件、查看文件列表、多选文件作为对话上下文、删除文件。

**文件存储策略**: 项目文件采用永久存储,按 `用户ID/项目ID/文件名` 的目录结构组织,确保文件持久化且便于管理。

**Why this priority**: 文件管理是项目的重要组成部分,但可以在基础功能完成后再实现。

**Independent Test**: 可以通过上传一个文件、在列表中勾选、然后删除来验证。

**Acceptance Scenarios**:

1. **Given** 用户在项目工作区, **When** 用户点击"+ Add sources"按钮并选择文件, **Then** 文件上传成功并永久存储在用户/项目目录下
2. **Given** Sources 列表有文件, **When** 用户查看文件列表, **Then** 看到文件图标、文件名(支持截断显示长文件名)
3. **Given** Sources 列表有多个文件, **When** 用户勾选文件复选框, **Then** 文件被选中,Chat 输入框显示选中的文件数量
4. **Given** Sources 列表有文件, **When** 用户点击"Select all sources"复选框, **Then** 所有文件被选中/取消选中
5. **Given** 文件已选中, **When** 用户在 Chat 发送消息, **Then** 选中的文件作为上下文传递给对话
6. **Given** Sources 列表有文件, **When** 用户选择删除文件, **Then** 文件从项目中移除,同时从存储目录删除
7. **Given** 用户重新登录或刷新页面, **When** 用户进入项目工作区, **Then** 之前上传的文件仍然存在

---

### Edge Cases

- 用户删除项目时,关联的文件和对话如何处理?文件级联删除(包括存储目录),对话解除关联回到History
- 用户在项目中上传同名文件时,系统应提示是否覆盖或自动重命名
- 用户在没有任何项目时访问Projects页面,应显示空状态引导创建
- 用户在项目加载过程中切换页面,应正确取消请求避免内存泄漏
- 文件名过长时需要截断显示,鼠标悬停显示完整名称
- 用户在没有选中任何文件时发起对话,对话正常进行(无文件上下文)
- 对话已属于某项目时,添加到另一项目应提示"移动"而非"添加"
- 项目下没有对话时,展开项目应显示空状态提示
- 用户创建或重命名项目时使用已存在的名称,应显示错误提示
- 项目已达到50个文件上限时,上传新文件应显示错误提示

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow authenticated users to create new projects with a unique name (no duplicate names per user)
- **FR-002**: System MUST allow users to edit project names they own
- **FR-003**: System MUST allow users to delete projects they own, with confirmation dialog
- **FR-004**: System MUST display user's projects in the left navigation alongside History
- **FR-005**: System MUST provide a project workspace with two-column layout (Sources + Chat)
- **FR-006**: System MUST allow users to upload files to their projects via "+ Add sources" button
- **FR-006a**: System MUST store project files permanently (not in temp directory)
- **FR-006b**: System MUST organize files by user_id/project_id/filename directory structure
- **FR-006c**: System MUST support document and code file types: PDF, DOCX, TXT, MD, CSV, JSON, and common code files (py, js, ts, java, go, etc.)
- **FR-006d**: System MUST limit each project to a maximum of 50 files
- **FR-007**: System MUST display uploaded files in a scrollable Sources list with checkboxes
- **FR-008**: System MUST allow users to multi-select files as conversation context
- **FR-009**: System MUST allow users to collapse/expand the Sources panel
- **FR-010**: System MUST reuse existing chat implementation for the Chat panel
- **FR-011**: System MUST pass selected files as context when user sends a message
- **FR-012**: System MUST enforce user ownership - users can only access their own projects
- **FR-013**: System MUST cascade delete project files when a project is deleted
- **FR-014**: System MUST persist project data in the database
- **FR-015**: System MUST display project's conversations as expandable tree nodes in navigation
- **FR-016**: System MUST allow users to remove conversations from projects via right-click menu
- **FR-017**: System MUST allow users to add conversations to projects from History list
- **FR-018**: System MUST unlink (not delete) conversations when a project is deleted

### Key Entities

- **Project**: 项目基本信息,包含 id, name, user_id, created_at, updated_at
- **ProjectFile**: 项目关联文件,包含 id, project_id, file_id, storage_path, created_at
  - storage_path 格式: `{base_dir}/{user_id}/{project_id}/{filename}`
  - 关联到现有 files 表以复用文件元数据
- **Conversation**: 现有对话表,需要添加 project_id 外键字段以支持项目关联

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a new project in under 10 seconds
- **SC-002**: Users can navigate between projects and history with a single click
- **SC-003**: Project list displays within 500ms of page load
- **SC-004**: File upload completes within 30 seconds for files up to 10MB
- **SC-005**: 100% of project operations respect user ownership (no unauthorized access)
- **SC-006**: Project deletion with confirmation prevents accidental data loss
- **SC-007**: Users can manage at least 50 projects without UI performance degradation
- **SC-008**: Sources panel collapse/expand animation completes within 300ms

## Assumptions

- 现有的文件上传系统 (`/api/files/upload`) 可以复用,但需要扩展支持永久存储
- 现有的用户认证系统提供 user_id
- 左侧导航组件支持添加新的导航项
- 现有的 Chat 组件可以接收文件上下文参数
- 文件存储基础目录通过环境变量配置 (如 `PROJECT_FILES_DIR`)
