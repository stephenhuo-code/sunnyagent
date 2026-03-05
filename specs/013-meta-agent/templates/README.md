# Meta-Agent 测试数据集模板

本目录包含用于创建 Plugin 优化测试数据集的模板文件。

## 模板文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `dataset-template.csv` | CSV | 适合在 Excel/Google Sheets 中编辑，不支持多轮对话 |
| `dataset-template.jsonl` | JSONL | 功能完整，支持多轮对话测试 |

## Command 调用方式

**重要**：Command 是用户**显式调用**的，不是系统自动路由的。

```
用户输入: "/complaint-analysis 分析这批客户投诉"
           ↑ 显式调用 complaint-analysis 命令
```

- Command 通过 `/command-name` 格式包含在 `input` 字段中
- `command` 字段仅用于元数据标记（便于按 Command 分组分析结果）
- 系统评估的是 Command 执行后的 **Skill 触发** 和 **输出质量**

## 测试执行上下文

每个测试用例在 SunnyAgent 中运行时需要完整的执行上下文：

```
┌─────────────────────────────────────────────────┐
│              测试执行上下文                       │
├─────────────────────────────────────────────────┤
│  Project (测试项目)                              │
│      ↓                                          │
│  Sources (项目文件) ← context_files 指定         │
│      ↓                                          │
│  Conversation (对话) ← conversation_history      │
│      ↓                                          │
│  Message (用户消息) ← input (含 /command)        │
│                       + 选中的文件               │
└─────────────────────────────────────────────────┘
```

## 字段说明

### 基础字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `case_id` | string | 是 | 唯一标识，建议格式: `plugin_001` |
| `input` | string | 是 | 用户输入消息（含 `/command-name` 显式调用） |
| `command` | string | 否 | Command 名称（元数据，用于分组统计） |
| `expected_skill` | string | 否 | 期望触发的 Skill 名称 |
| `expected_output_contains` | array | 否 | 输出应包含的关键词列表 |
| `expected_behavior` | string | 是 | 期望行为的自然语言描述（用于 LLM 评估） |
| `tags` | array | 否 | 标签，用于过滤和分组分析 |

### 上下文字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `context_files` | array | 否 | 测试时需要选中的文件路径（相对于 `test-resources/files/`） |
| `project_config` | object | 否 | 测试项目配置 |
| `conversation_history` | array | 否 | 多轮对话的历史消息（仅 JSONL 支持） |

### project_config 子字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | string | `meta-agent-test` | 测试项目名称 |
| `reuse` | boolean | `true` | 是否复用已存在的同名项目 |
| `cleanup` | boolean | `false` | 测试后是否清理项目 |

### conversation_history 结构

```json
[
  {"role": "user", "content": "/quality-data 之前的数据分析"},
  {"role": "assistant", "content": "数据已加载，包含 500 条记录..."}
]
```

## 评估维度

系统会对每个 case 计算以下维度的分数：

| 维度 | 说明 | 评估方式 |
|------|------|---------|
| `correctness` | 输出正确性 | 检查 `expected_output_contains` 中的关键词 |
| `skill_trigger` | Skill 触发 | Command 执行时是否正确触发了 `expected_skill` |
| `response_quality` | 回复质量 | LLM 根据 `expected_behavior` 评估 |
| `file_context_usage` | 文件上下文使用 | 检查是否正确使用了 `context_files` 中的文件 |

## 测试资源目录结构

测试文件需要放到指定目录：

```
meta-agent/
├── test-resources/
│   ├── datasets/           # 测试数据集文件
│   │   ├── qc-plugin.jsonl
│   │   └── data-plugin.jsonl
│   └── files/              # 测试所需的上下文文件
│       ├── test-data/
│       │   ├── quality-sample.csv
│       │   ├── defect-report.xlsx
│       │   └── complaints.csv
│       └── documents/
│           ├── sop-template.docx
│           └── spec-sample.pdf
```

## 使用步骤

### 1. 准备测试文件

将测试需要的文件放到 `test-resources/files/` 目录：

```bash
# 示例
mkdir -p meta-agent/test-resources/files/test-data
cp your-test-data.csv meta-agent/test-resources/files/test-data/
```

### 2. 选择模板格式

- **CSV 格式**：简单场景，单轮对话
- **JSONL 格式**：复杂场景，多轮对话，推荐使用

### 3. 填写测试用例

**JSONL 示例（显式调用 Command + 文件上下文）**：
```jsonl
{
  "case_id": "qc_001",
  "input": "/quality-data 分析这批产品的质量数据",
  "command": "quality-data",
  "expected_skill": "data-profiler",
  "expected_output_contains": ["CPK", "合格率"],
  "expected_behavior": "应该分析数据并返回统计指标",
  "tags": ["quality", "data"],
  "context_files": ["test-data/quality-sample.csv"]
}
```

**JSONL 示例（多轮对话）**：
```jsonl
{
  "case_id": "qc_002",
  "input": "这个数据有什么异常",
  "expected_skill": "quality-analysis",
  "expected_output_contains": ["异常", "建议"],
  "expected_behavior": "应该识别数据异常并给出改进建议",
  "context_files": ["test-data/defect-report.xlsx"],
  "conversation_history": [
    {"role": "user", "content": "/quality-data 帮我分析产品质量"},
    {"role": "assistant", "content": "数据已加载，包含 500 条记录，请问您想了解什么？"}
  ]
}
```

### 4. 验证数据集

系统会自动验证：
- `case_id` 唯一性
- 必填字段完整性
- JSON 格式正确性
- **context_files 中的文件是否存在**

### 5. 同步到 Langfuse

验证通过后，系统会自动：
1. 创建测试项目（如果需要）
2. 上传 context_files 到项目 Sources
3. 在 Langfuse 创建 Dataset
4. 为每个 case 创建 Dataset Item

## 最佳实践

1. **case_id 命名规范**：使用 `plugin_序号` 格式，如 `qc_001`, `qc_002`
2. **input 中包含 Command**：显式调用格式 `/command-name 参数`
3. **expected_behavior 要具体**：描述应该发生什么，而不是不应该发生什么
4. **合理使用 tags**：便于按功能分组分析失败原因
5. **从简单开始**：先创建 10-20 个核心用例，验证流程后再扩展
6. **覆盖边界情况**：包含正常、异常、边界输入
7. **测试文件要有代表性**：使用真实或接近真实的测试数据
8. **多轮对话测试**：对于复杂流程，使用 conversation_history 测试多轮交互

## 常见问题

### Q: context_files 找不到文件怎么办？

确保文件已放到 `test-resources/files/` 目录，并且路径正确：
```
context_files: ["test-data/file.csv"]
→ 实际位置: meta-agent/test-resources/files/test-data/file.csv
```

### Q: 如何测试不需要文件的场景？

省略 `context_files` 字段即可：
```jsonl
{"case_id": "qc_003", "input": "/8d-report 写一份8D报告", "expected_behavior": "生成8D报告"}
```

### Q: 如何测试多个文件的场景？

在 `context_files` 数组中列出所有文件：
```jsonl
{"context_files": ["test-data/report-a.pdf", "test-data/report-b.pdf"]}
```

### Q: CSV 和 JSONL 选哪个？

- 简单测试用 CSV（Excel 友好）
- 需要多轮对话或复杂配置用 JSONL

### Q: command 字段有什么用？

`command` 字段是元数据，用于：
- 按 Command 分组查看评估结果
- 生成按 Command 分类的分析报告
- 优化特定 Command 时筛选相关 case
