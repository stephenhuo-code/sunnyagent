# SunnyAgent 评估系统

使用 Langfuse Dataset 和 Experiment 功能评估 SunnyAgent 的回复质量。

## 快速开始

### 1. 环境配置

```bash
# 复制环境变量
cp .env.example .env

# 配置必要的环境变量
export LANGFUSE_PUBLIC_KEY="pk-lf-xxx"
export LANGFUSE_SECRET_KEY="sk-lf-xxx"
export LANGFUSE_HOST="http://localhost:3001"
export SUNNYAGENT_API_URL="http://localhost:8008"
export SUNNYAGENT_USERNAME="admin"
export SUNNYAGENT_PASSWORD="your-password"
```

### 2. 创建 Dataset

#### 方式一：使用示例数据集

```bash
# 使用 Langfuse Python SDK 导入示例数据集
python -c "
from langfuse import Langfuse
import json

langfuse = Langfuse()

# 加载示例数据集
with open('scripts/evaluation/sample_dataset.json') as f:
    data = json.load(f)

# 创建数据集
dataset = langfuse.create_dataset(
    name=data['name'],
    description=data['description']
)

# 添加测试用例
for item in data['items']:
    dataset.create_item(
        input=item['input'],
        expected_output=item.get('expected_output'),
        metadata=item.get('metadata')
    )

print(f'Created dataset: {dataset.name} with {len(data[\"items\"])} items')
"
```

#### 方式二：在 Langfuse UI 中创建

1. 打开 Langfuse 界面 (http://localhost:3001)
2. 进入 Datasets 页面
3. 点击 "New Dataset" 创建数据集
4. 手动添加测试用例

### 3. 运行评估实验

```bash
# 基本用法
python scripts/evaluation/run_experiment.py --dataset sunnyagent-basic-evaluation

# 指定实验名称
python scripts/evaluation/run_experiment.py --dataset sunnyagent-basic-evaluation --experiment my-experiment-v1

# 启用 LLM-as-a-Judge 评估
python scripts/evaluation/run_experiment.py --dataset sunnyagent-basic-evaluation --evaluators relevance correctness completeness
```

### 4. 查看结果

实验完成后，在 Langfuse 界面中查看：

1. **Traces**: 查看每个测试用例的执行详情
2. **Experiments**: 比较不同实验的结果
3. **Scores**: 查看 LLM-as-a-Judge 评分

## 评估指标

### LLM-as-a-Judge 评估器

| 指标 | 描述 | 范围 |
|------|------|------|
| relevance | 回复与问题的相关性 | 0-1 |
| correctness | 回复的正确性（需要预期答案） | 0-1 |
| completeness | 回复的完整性 | 0-1 |

### 自定义评估器

在 `evaluators.py` 中添加自定义评估逻辑：

```python
async def evaluate_custom(input_message: str, output_response: str) -> float:
    # 自定义评估逻辑
    return score
```

## 数据集格式

```json
{
  "name": "dataset-name",
  "description": "Dataset description",
  "items": [
    {
      "id": "unique-id",
      "input": {
        "message": "用户问题"
      },
      "expected_output": {
        "answer": 42,
        "contains": ["关键词1", "关键词2"]
      },
      "metadata": {
        "category": "math",
        "difficulty": "easy"
      }
    }
  ]
}
```

### 预期输出类型

| 字段 | 描述 | 用途 |
|------|------|------|
| `answer` | 预期的精确答案 | 数学、推理题 |
| `contains` | 回复应包含的关键词 | 知识问答 |
| `contains_code` | 是否应包含代码 | 编程题 |
| `type` | 问题类型 | 分类统计 |

## 最佳实践

### 数据集设计

1. **覆盖多种场景**: 包含问答、计算、编程、分析等不同类型
2. **难度分级**: 标注 easy/medium/hard 便于分析
3. **分类标签**: 使用 metadata.category 便于按类别统计

### 评估策略

1. **基准测试**: 定期运行相同数据集，跟踪性能变化
2. **A/B 测试**: 使用相同数据集比较不同模型/配置
3. **增量测试**: 添加新用例测试边界情况

### 结果分析

1. **查看低分用例**: 分析评分低的测试用例，找出问题
2. **按类别统计**: 查看不同类型问题的表现
3. **趋势跟踪**: 比较多次实验的结果趋势

## 文件说明

| 文件 | 描述 |
|------|------|
| `run_experiment.py` | 实验运行脚本 |
| `evaluators.py` | LLM-as-a-Judge 评估器 |
| `sample_dataset.json` | 示例数据集 |
| `README.md` | 本文档 |

## 故障排除

### 常见问题

1. **连接失败**
   - 检查 LANGFUSE_HOST 和 SUNNYAGENT_API_URL
   - 确保服务正在运行

2. **认证错误**
   - 检查 API 密钥配置
   - 检查 SunnyAgent 用户名密码

3. **评估超时**
   - 增加 httpx timeout 设置
   - 检查网络连接

### 日志级别

```bash
# 启用调试日志
LOG_LEVEL=DEBUG python scripts/evaluation/run_experiment.py --dataset test
```
