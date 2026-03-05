# Quick Start: Meta-Agent Plugin Optimization

## Prerequisites

1. **SunnyAgent 运行中**
   ```bash
   ./scripts/start.sh backend
   # 确认 http://localhost:8008 可访问
   ```

2. **Langfuse 运行中**
   ```bash
   ./scripts/start.sh infra
   # 确认 http://localhost:3001 可访问
   ```

3. **Admin 账号已创建**
   ```bash
   # SunnyAgent 首次启动时自动创建
   # 默认: admin / 由 ADMIN_PASSWORD 环境变量指定
   ```

## Installation

```bash
# 安装 Meta-Agent 依赖
cd meta_agent
uv sync
```

## Quick Optimization

### Step 1: 准备测试数据集

1. 复制模板：
   ```bash
   cp specs/013-meta-agent/templates/dataset-template.jsonl \
      meta_agent/test-resources/datasets/my-plugin.jsonl
   ```

2. 编辑数据集，添加测试用例：
   ```jsonl
   {"case_id": "001", "input": "/my-command 做某事", "expected_behavior": "应该完成某事", "expected_output_contains": ["结果"]}
   {"case_id": "002", "input": "/my-command 另一件事", "expected_behavior": "应该处理另一件事"}
   ```

3. 如果需要文件上下文，将文件放到：
   ```bash
   meta_agent/test-resources/files/
   ```

### Step 2: 创建配置文件

```yaml
# meta_agent/config.yaml
optimization:
  target_plugin: "my-plugin"
  dataset_path: "test-resources/datasets/my-plugin.jsonl"

  # 可选：覆盖默认值
  # target_score: 0.8
  # max_iterations: 5
```

### Step 3: 运行优化

```bash
# 基本用法
uv run python -m meta_agent optimize

# 指定配置文件
uv run python -m meta_agent optimize --config config.yaml

# 从检查点恢复
uv run python -m meta_agent resume --checkpoint-id <uuid>
```

### Step 4: 查看结果

- **终端输出**：每轮迭代的分数和操作
- **Langfuse Dashboard**：详细的 trace 和评估结果
- **最终报告**：`meta_agent/results/report-<timestamp>.md`
- **Git 历史**：每次修改的 commit

## CLI Commands

```bash
# 运行优化
uv run python -m meta_agent optimize [OPTIONS]

Options:
  --config PATH       配置文件路径 (默认: config.yaml)
  --target-plugin     目标 Plugin 名称
  --dataset PATH      数据集文件路径
  --target-score      目标分数 (默认: 0.8)
  --max-iterations    最大迭代次数 (默认: 5)
  --dry-run           仅验证，不执行

# 恢复中断的优化
uv run python -m meta_agent resume --checkpoint-id <uuid>

# 仅运行评估（不优化）
uv run python -m meta_agent evaluate --dataset PATH

# 验证数据集
uv run python -m meta_agent validate --dataset PATH

# 同步数据集到 Langfuse
uv run python -m meta_agent sync --dataset PATH

# 列出检查点
uv run python -m meta_agent checkpoints list

# 查看检查点详情
uv run python -m meta_agent checkpoints show <uuid>
```

## Configuration Reference

```yaml
optimization:
  # 必填
  target_plugin: string        # 目标 Plugin 名称

  # 数据集
  dataset_path: string         # 数据集文件路径

  # 完成准则（都有默认值）
  target_score: 0.8            # 目标分数 [0, 1]
  max_iterations: 5            # 最大迭代次数
  regression_threshold: 0.05   # 回归阈值
  patience: 2                  # 耐心值
  min_improvement: 0.02        # 最小有效提升

  # 测试项目
  test_project_name: "meta-agent-test"
  cleanup_on_complete: false

  # Git
  auto_commit: true
  commit_prefix: "meta-agent:"

# SunnyAgent 连接
sunnyagent:
  base_url: "http://localhost:8008"
  admin_username: "admin"
  admin_password: ${ADMIN_PASSWORD}  # 从环境变量

# Langfuse 连接（与 SunnyAgent 共享）
langfuse:
  public_key: ${LANGFUSE_PUBLIC_KEY}
  secret_key: ${LANGFUSE_SECRET_KEY}
  base_url: "http://localhost:3001"
```

## Dataset Format

### JSONL (推荐)

```jsonl
{"case_id": "qc_001", "input": "/complaint-analysis 分析投诉", "command": "complaint-analysis", "expected_skill": "quality-analysis", "expected_output_contains": ["原因", "建议"], "expected_behavior": "应该分析投诉原因并给出改进建议", "tags": ["complaint"], "context_files": ["test-data/complaints.csv"]}
```

### CSV (简单场景)

```csv
case_id,input,command,expected_skill,expected_output_contains,expected_behavior,tags,context_files
qc_001,/complaint-analysis 分析投诉,complaint-analysis,quality-analysis,"[""原因"",""建议""]",应该分析投诉原因并给出改进建议,"[""complaint""]","[""test-data/complaints.csv""]"
```

## Troubleshooting

### SunnyAgent 连接失败

```bash
# 检查服务状态
curl http://localhost:8008/api/health

# 检查认证
curl -X POST http://localhost:8008/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

### Langfuse 连接失败

```bash
# 检查服务状态
curl http://localhost:3001/api/public/health

# 检查 API 密钥
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY
```

### 数据集验证失败

```bash
# 验证数据集格式
uv run python -m meta_agent validate --dataset path/to/dataset.jsonl

# 检查文件是否存在
ls -la meta_agent/test-resources/files/
```

### 优化中断

```bash
# 列出可恢复的检查点
uv run python -m meta_agent checkpoints list

# 恢复
uv run python -m meta_agent resume --checkpoint-id <uuid>
```

## Example: Manufacturing QC Plugin

```bash
# 1. 使用示例数据集
cp specs/013-meta-agent/templates/dataset-template.jsonl \
   meta_agent/test-resources/datasets/qc-plugin.jsonl

# 2. 创建配置
cat > meta_agent/config.yaml << EOF
optimization:
  target_plugin: "manufacturing-qc"
  dataset_path: "test-resources/datasets/qc-plugin.jsonl"
  target_score: 0.85
EOF

# 3. 运行优化
uv run python -m meta_agent optimize

# 4. 查看结果
cat meta_agent/results/report-*.md
```
