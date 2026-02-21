# Quickstart: Langfuse 可观测性集成

**Branch**: `007-langfuse-integration` | **Date**: 2026-02-19

## 前置条件

1. Docker 和 docker-compose 已安装
2. SunnyAgent 开发环境已配置

## 快速开始

### 1. 启动基础设施服务

```bash
# 使用启动脚本一键启动所有服务
# 包括：PostgreSQL + ClickHouse + Redis + MinIO + Langfuse v3
./scripts/start.sh infra
```

或手动启动：

```bash
# 生成必要的密钥（可选，有默认值）
export LANGFUSE_NEXTAUTH_SECRET=$(openssl rand -base64 32)
export LANGFUSE_SALT=$(openssl rand -base64 32)
export LANGFUSE_ENCRYPTION_KEY=$(openssl rand -hex 32)

# 启动所有服务
docker compose up -d
```

### 2. 配置环境变量

在 `.env` 文件中添加：

```env
# Langfuse 服务配置
LANGFUSE_URL=http://localhost:3001
LANGFUSE_DATABASE_URL=postgresql://sunnyagent:sunnyagent123@localhost:5432/langfuse
LANGFUSE_NEXTAUTH_SECRET=<generated>
LANGFUSE_SALT=<generated>
LANGFUSE_ENCRYPTION_KEY=<generated>

# SunnyAgent 集成配置（从 Langfuse UI 获取）
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_BASE_URL=http://localhost:3001

# Admin API 配置（从 Langfuse 组织设置获取）
LANGFUSE_ORG_PUBLIC_KEY=pk-org-xxx
LANGFUSE_ORG_SECRET_KEY=sk-org-xxx
```

### 3. 安装 Python 依赖

```bash
uv add langfuse>=3.0.0
```

### 4. 验证集成

```python
from langfuse import get_client

# 验证连接
langfuse = get_client()
assert langfuse.auth_check(), "Langfuse authentication failed"
print("Langfuse connected successfully!")
```

---

## 测试场景

### 场景 1: Agent 执行链路追踪

**验证 FR-001, FR-002, FR-003**

```bash
# 1. 发送一条消息
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: auth_token=xxx" \
  -d '{"thread_id": "test-123", "message": "今天天气怎么样？"}'

# 2. 打开 Langfuse UI
open http://localhost:3001

# 3. 验证：
#    - 可以看到完整的 Trace
#    - Trace 包含 AIME 组件 Span（intent-analyzer, planner, actor）
#    - 每个 Span 有耗时、输入、输出信息
```

### 场景 2: 错误追踪

**验证 FR-004**

```bash
# 1. 触发一个会失败的请求（如无效的 Agent）
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: auth_token=xxx" \
  -d '{"thread_id": "test-456", "message": "test", "agent": "nonexistent"}'

# 2. 在 Langfuse UI 中查看 Trace
# 3. 验证：
#    - 错误 Trace 被标记为 error 状态
#    - 错误位置和堆栈信息可见
```

### 场景 3: 优雅降级

**验证 FR-006, SC-007**

```bash
# 1. 停止 Langfuse 服务
docker compose stop langfuse

# 2. 发送消息
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: auth_token=xxx" \
  -d '{"thread_id": "test-789", "message": "Hello"}'

# 3. 验证：
#    - Agent 正常响应
#    - 响应时间不受影响
#    - 日志中有 Langfuse 不可用警告
```

### 场景 4: 账号同步

**验证 FR-015, FR-016, FR-017, SC-009**

```bash
# 1. 创建 SunnyAgent 用户
curl -X POST http://localhost:8008/api/users \
  -H "Content-Type: application/json" \
  -H "Cookie: auth_token=admin_xxx" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "xxx"}'

# 2. 在 Langfuse UI 验证用户已创建

# 3. 禁用 SunnyAgent 用户
curl -X PATCH http://localhost:8008/api/users/123/status \
  -H "Content-Type: application/json" \
  -H "Cookie: auth_token=admin_xxx" \
  -d '{"is_active": false}'

# 4. 验证 Langfuse 用户已被禁用
```

### 场景 5: 测试数据集评估

**验证 FR-008, FR-009, FR-010, FR-011, SC-005**

```python
# scripts/evaluation/run_experiment.py

from langfuse import get_client
import httpx

langfuse = get_client()

# 创建数据集
dataset = langfuse.create_dataset(
    name="agent-qa-test",
    description="Agent QA 测试数据集"
)

# 添加测试用例
dataset.create_item(
    input={"message": "你好"},
    expected_output={"contains": "你好"}
)

# 定义任务函数（调用真实 Agent）
async def agent_task(item):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8008/api/chat",
            json={"thread_id": f"eval-{item.id}", "message": item.input["message"]},
            headers={"Cookie": "auth_token=xxx"}
        )
        return response.text

# 运行评估
result = dataset.run_experiment(
    name="Agent QA Evaluation",
    task=agent_task,
    evaluators=[...]
)

print(result.format())
```

---

## 常见问题

### Q: Langfuse 连接失败

```bash
# 检查服务状态
curl http://localhost:3001/api/public/health

# 检查环境变量
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY
```

### Q: Trace 没有出现

1. 确认 `CallbackHandler` 已传递给 graph
2. 检查 `LANGFUSE_SAMPLE_RATE` 是否为 1.0
3. 查看 debug 日志：`LANGFUSE_DEBUG=True`

### Q: Admin API 返回 401

1. 确认使用的是组织 API 密钥（`pk-org-xxx`），而非项目密钥
2. 检查密钥是否有 Admin 权限

---

## 验收检查清单

### 自动验证（运行脚本）

```bash
# 设置环境变量
export SUNNYAGENT_PASSWORD="your-admin-password"

# 运行验证脚本
python scripts/evaluation/validate_langfuse.py --all
```

### 手动验证

- [ ] Langfuse 服务启动成功 (`docker compose up -d langfuse`)
- [ ] 发送消息后 Trace 出现在 Langfuse UI
- [ ] AIME 组件 Span 正确嵌套（intent-analyzer → actor-factory → actor-execution）
- [ ] 错误 Trace 有清晰的错误信息和堆栈
- [ ] Langfuse 不可用时 Agent 正常工作（停止 langfuse 容器后测试）
- [ ] 创建用户时 Langfuse 账号同步创建
- [ ] 禁用用户时 Langfuse 账号同步禁用
- [ ] 系统管理页面有 Langfuse 链接（"系统设置" tab）
- [ ] 点击链接在新窗口打开 Langfuse
- [ ] Langfuse 仪表盘显示：调用次数、成功率、响应时间、Token 消耗
