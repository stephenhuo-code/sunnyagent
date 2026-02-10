<!--
=== 同步影响报告 ===
版本变更: 1.0.0 → 1.1.0
变更理由: 添加 4 项新原则（MINOR — 扩展性变更）

修改的原则: 无
新增原则:
  - VI. 测试优先
  - VII. 分层依赖
  - VIII. 接口优先
  - IX. 安全边界

技术约束更新:
  - 持久化: SQLite → PostgreSQL（反映当前架构）

模板更新状态:
  - .specify/templates/plan-template.md — ✅ 兼容（Constitution Check 支持动态原则）
  - .specify/templates/spec-template.md — ✅ 兼容（User Stories 结构支持测试优先）
  - .specify/templates/tasks-template.md — ✅ 兼容（已包含 Tests 阶段和分层结构）

相关文档更新建议:
  - docs/architecture.md — ✅ 已包含分层依赖和安全边界
  - CLAUDE.md — ✅ 已引用 architecture.md

遗留 TODO: 无
===========================
-->

# SunnyAgent 项目宪法

## 核心原则

### I. Agent 隔离

每个专业 Agent 必须（MUST）是独立的 `create_deep_agent()` 单元，拥有自己的
中间件栈。Agent 之间禁止（MUST NOT）直接共享可变状态。每个 Agent 必须（MUST）
能够在不依赖 Supervisor 或其他 Agent 运行的情况下独立测试。

**理由**：隔离可防止级联故障，支持独立开发周期，并使系统更易于推理。Research
Agent 出现故障时，绝不能影响 SQL Agent 的正常运行。

### II. 注册驱动发现

所有 Agent 必须（MUST）通过 `register_agent()` 在中央 `AGENT_REGISTRY` 中
自注册。Supervisor 和 General Agent 必须（MUST）在运行时从该注册表自动发现
Agent。禁止（MUST NOT）在 Supervisor 中使用硬编码的路由表。

**理由**：解耦的注册机制意味着添加新 Agent 只需创建文件并导入——无需修改
Supervisor 或路由逻辑。这使系统对扩展开放而无需修改现有代码。

### III. 流式优先

所有聊天响应必须（MUST）通过 Server-Sent Events（SSE）进行流式传输。
管线——LangGraph `astream()` → `stream_handler` → 类型化 SSE 事件 →
React 状态——必须（MUST）保持完整。禁止（MUST NOT）对用户面向的聊天交互
使用阻塞式请求-响应模式。

**理由**：流式传输提供实时反馈，降低感知延迟，对于长时间运行的 Agent 任务
至关重要——用户需要看到增量进展。

### IV. 包扩展性

新 Agent 必须（MUST）能够通过在 `packages/` 目录中仅放置 `AGENTS.md` 文件
（系统提示词）和可选的 `skills/` 子目录（含 `SKILL.md` 文件）来添加。包
Agent 必须（MUST）在启动时自动加载，无需修改现有代码。

**理由**：低摩擦的扩展性鼓励实验，允许非核心贡献者在不理解完整代码库内部
实现的情况下添加 Agent。

### V. 简洁性

从最小可行实现开始。严格执行 YAGNI（你不会需要它）原则。抽象必须（MUST）
由具体的、当前的需求来证明其合理性——而非假设性的未来需求。三行类似的代码
优于一个过早的抽象。

**理由**：过度工程化产生的维护负担和认知开销与其价值不成比例。本项目的优势
在于其直观的 Supervisor-to-Agent 路由模式；不必要的层级会模糊这种清晰性。

### VI. 测试优先

关键业务逻辑和 Agent 工具必须（MUST）有单元测试覆盖。新功能应（SHOULD）
先写测试再写实现（TDD）。集成测试必须（MUST）覆盖 Supervisor 路由和
Agent 协作场景。合并前测试必须（MUST）通过。

**理由**：测试是重构的安全网。AI 生成的代码更需要测试验证正确性。没有测试
的代码是负债，有测试的代码是资产。

### VII. 分层依赖

代码必须（MUST）遵循 API → Agent → Service → Repository → Database 的
依赖方向。禁止（MUST NOT）反向依赖。Agent 禁止（MUST NOT）直接导入
`asyncpg` 或 `db.py`。数据库访问必须（MUST）通过 Repository 层。

**理由**：清晰的分层使代码易于测试、替换和理解。每一层只依赖其下层，
确保变更影响可控。

### VIII. 接口优先

跨模块的共享功能必须（MUST）先在 `contracts/` 目录中定义接口。实现
必须（MUST）符合接口契约。接口变更必须（MUST）经过架构师审批。禁止
（MUST NOT）在未定义接口的情况下跨模块调用。

**理由**：接口优先支持并行开发，减少集成冲突。明确的契约使团队成员
可以独立工作而不产生隐性耦合。

### IX. 安全边界

用户提供的代码必须（MUST）在沙箱容器中执行，禁用网络，移除所有
capabilities。所有 API 端点必须（MUST）验证用户权限。禁止（MUST NOT）
在日志中记录敏感信息（密码、令牌、API 密钥）。文件操作必须（MUST）
通过 `file_service` 而非直接文件系统访问。

**理由**：安全是不可妥协的基础设施要求。一次安全漏洞可能导致整个系统
被攻破。防御性设计从第一天开始。

## 技术约束

- **后端**：Python 3.11+，FastAPI 框架；依赖管理使用 `uv`
- **前端**：React 19 + Vite 7 + TypeScript；依赖管理使用 `npm`
- **Agent 框架**：LangGraph `StateGraph` 用于编排；`deepagents` 库用于
  创建专业 Agent
- **持久化**：PostgreSQL，通过 `asyncpg` 连接池和 LangGraph
  `AsyncPostgresSaver` 存储会话线程
- **认证**：JWT + HTTP-only Cookies，bcrypt 密码哈希
- **注册顺序**：General Agent 必须（MUST）在
  `backend/agents/__init__.py` 中最后构建，因为它会收集所有已注册 Agent
  的工具

## 开发工作流

- **类型检查**：`uv run pyright` 检查 Python；`npx tsc` 检查 TypeScript。
  合并前两者必须（MUST）通过。
- **测试**：`uv run pytest` 运行测试套件。关键路径必须（MUST）有测试覆盖。
- **端口**：后端运行在 8008；前端开发服务器运行在 3008（将 `/api` 代理到
  后端）
- **数据库**：`docker compose up -d` 启动 PostgreSQL；
  `cd infra && uv run alembic upgrade head` 应用迁移。
- **添加代码 Agent**：在 `backend/agents/` 创建文件，在 `__init__.py` 中
  于 `build_general_agent()` 之前导入，重启后端。
- **添加包 Agent**：创建 `packages/<名称>/AGENTS.md`；启动时自动加载，
  无需修改代码。
- **提交纪律**：每个逻辑工作单元完成后提交。保持提交聚焦且原子化。

## 治理

本宪法是项目级原则和约束的权威来源。所有设计决策、代码审查和功能计划
必须（MUST）根据这些原则进行评估。

**修订程序**：
1. 在 Pull Request 或对话中提出变更及其理由。
2. 记录受影响的具体原则。
3. 更新本文件，并按语义化版本规则递增版本号（MAJOR 用于原则的移除/重新
   定义，MINOR 用于添加/扩展，PATCH 用于澄清）。
4. 验证依赖模板（plan、spec、tasks）保持一致。

**合规审查**：每次 `/speckit.plan` 执行时必须（MUST）包含 Constitution
Check 门禁，在进入实施阶段前验证与这些原则的一致性。

**指导文件**：
- 系统架构详见 `docs/architecture.md`
- 运行时开发指导详见 `CLAUDE.md`
- AI 协作最佳实践详见 `docs/ai-dev-best-practices.md`

**版本**: 1.1.0 | **批准日期**: 2026-02-07 | **最后修订**: 2026-02-10
