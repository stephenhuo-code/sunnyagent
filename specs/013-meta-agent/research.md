# Research: Meta-Agent Plugin Optimization System

**Feature**: 013-meta-agent
**Date**: 2026-03-04
**Status**: Complete

## Research Summary

本文档记录了 Meta-Agent 系统设计过程中的技术研究和决策。

---

## 1. Claude Agent Team 架构

### Decision
直接使用 Anthropic 的 Claude Agent Team 模式实现多 Agent 协作。

### Rationale
- spec.md 和 design-notes.md 明确要求使用此架构
- Claude Agent Team 提供了成熟的多 Agent 协作模式
- 与 SunnyAgent 使用的 LangGraph 互补而非替代

### Alternatives Considered
| 方案 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| Claude Agent Team | 官方支持，适合多 Agent 协作 | 需要 Anthropic API | ✅ 选用 |
| LangGraph StateGraph | SunnyAgent 已使用 | 更适合单 Agent 流程 | 不适用 |
| 自定义协作框架 | 完全控制 | 开发成本高，维护负担 | 拒绝 |

### Implementation Notes
- 使用 `anthropic` Python SDK
- 每个 Agent 对应一个专门的 system prompt
- Orchestrator 负责协调和决策
- Agent 间通过消息传递协作

---

## 2. Langfuse 集成模式

### Decision
复用 SunnyAgent 已有的 Langfuse 实例，Meta-Agent 只负责：
- **写入**: Dataset（测试数据集）
- **读取**: Trace（执行记录）、Score（评分）

### Rationale
- 避免重复部署 Langfuse
- SunnyAgent 执行时自动产生 trace，无需 Meta-Agent 额外写入
- 数据一致性（同一个 Langfuse 实例查看所有数据）

### Alternatives Considered
| 方案 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| 复用现有实例 | 简单，数据统一 | 共享配置 | ✅ 选用 |
| 独立 Langfuse 实例 | 隔离 | 运维成本，数据分散 | 拒绝 |
| 不使用 Langfuse | 无外部依赖 | 失去可观测性平台 | 拒绝 |

### Implementation Notes
- 使用相同的 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY`
- Dataset 使用命名约定：`meta-agent-{plugin}-{version}`
- 通过 `langfuse` Python SDK 操作

---

## 3. SunnyAgent API 调用方式

### Decision
通过 HTTP API 调用 SunnyAgent（`POST /api/chat`），使用 admin 账号认证。

### Rationale
- SunnyAgent 已有完整的 API 接口
- 使用 admin 账号确保有足够权限创建项目、上传文件
- HTTP 调用保持系统解耦

### Alternatives Considered
| 方案 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| HTTP API 调用 | 解耦，接口稳定 | 网络开销 | ✅ 选用 |
| 直接导入 Python 模块 | 性能好 | 耦合紧密，违反隔离原则 | 拒绝 |
| 消息队列 | 异步解耦 | 过度复杂 | 拒绝 |

### Implementation Notes
- 使用 `httpx` 异步 HTTP 客户端
- 处理 SSE 流响应
- 实现重试和超时机制

---

## 4. 文件修改安全机制

### Decision
实现多层安全机制确保只修改 `packages/` 目录：
1. 路径白名单校验
2. Git commit 记录每次修改
3. 自动回滚机制

### Rationale
- spec 明确要求只能修改 `packages/` 目录
- 安全边界是宪法 IX 的要求
- Git 提供可靠的回滚能力

### Implementation Notes
- `file_service.py` 实现路径校验
- 使用 `gitpython` 操作 Git
- 每次修改自动 commit，包含详细 message

---

## 5. 评分计算方案

### Decision
使用 correctness 优先的加权平均：
```
overall_score = 0.50 × correctness
              + 0.167 × skill_trigger
              + 0.167 × response_quality
              + 0.167 × file_context_usage
```

### Rationale
- 用户在 clarify 阶段选择了此方案
- correctness（输出正确性）是最基本的要求
- 其他维度作为辅助评估

### Implementation Notes
- 在 `score_calculator.py` 中实现
- 每个维度分数范围 [0, 1]
- 总分范围 [0, 1]

---

## 6. 检查点和恢复机制

### Decision
每轮迭代后保存检查点到本地 JSON 文件，支持断点续跑。

### Rationale
- 优化可能长时间运行
- 支持中断后恢复
- 避免重复执行已完成的迭代

### Checkpoint Structure
```json
{
  "optimization_id": "uuid",
  "target_plugin": "manufacturing-qc",
  "current_iteration": 3,
  "best_score": 0.75,
  "best_iteration": 2,
  "last_evaluation_id": "langfuse-eval-id",
  "modified_files": [
    {"path": "packages/manufacturing-qc/commands/complaint-analysis.md", "commit": "abc123"}
  ],
  "state": "in_progress",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T10:30:00Z"
}
```

### Implementation Notes
- 检查点保存在 `meta_agent/.checkpoints/` 目录
- 使用 UUID 作为 optimization_id
- 恢复时验证检查点完整性

---

## 7. 数据集模板格式

### Decision
支持 CSV 和 JSONL 两种格式，JSONL 为完整功能格式。

### Rationale
- CSV 适合 Excel 编辑，降低用户门槛
- JSONL 支持多轮对话等高级功能
- 两种格式可以互相转换

### Field Mapping
| 字段 | CSV | JSONL | 必填 |
|------|-----|-------|------|
| case_id | ✅ | ✅ | 是 |
| input | ✅ | ✅ | 是 |
| command | ✅ | ✅ | 否 |
| expected_skill | ✅ | ✅ | 否 |
| expected_output_contains | JSON 字符串 | 数组 | 否 |
| expected_behavior | ✅ | ✅ | 是 |
| tags | JSON 字符串 | 数组 | 否 |
| context_files | JSON 字符串 | 数组 | 否 |
| project_config | JSON 字符串 | 对象 | 否 |
| conversation_history | 不支持 | 数组 | 否 |

### Implementation Notes
- `dataset_service.py` 负责解析和验证
- CSV 中的 JSON 字段使用双引号转义
- 验证失败返回行号和具体错误

---

## 8. 测试策略

### Decision
采用三层测试策略：
1. **单元测试**: 核心服务和工具函数
2. **集成测试**: API 客户端和完整流程
3. **端到端测试**: 使用 mock SunnyAgent

### Test Coverage Targets
| 模块 | 目标覆盖率 |
|------|-----------|
| services/ | 80% |
| models/ | 90% |
| utils/ | 85% |
| agents/ | 70%（涉及 LLM 调用） |

### Implementation Notes
- 使用 `pytest` + `pytest-asyncio`
- 使用 `respx` mock HTTP 请求
- 使用 `pytest-cov` 生成覆盖率报告

---

## Dependencies Summary

```toml
[project]
dependencies = [
    "anthropic>=0.18.0",
    "langfuse>=2.0.0",
    "httpx>=0.27.0",
    "gitpython>=3.1.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
    "click>=8.0.0",  # CLI 框架
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "respx>=0.20.0",
]
```

---

## Open Questions (Resolved)

所有 NEEDS CLARIFICATION 项已在 spec clarify 阶段解决：

| 问题 | 决策 |
|------|------|
| 评分维度权重 | correctness 50%，其他各 16.7% |
| 修改应用方式 | 全自动，依赖 git 回滚 |
| Agent Team 实现 | 使用 Claude Agent Team 架构 |
