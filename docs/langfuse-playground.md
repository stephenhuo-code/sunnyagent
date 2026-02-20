# Langfuse Prompt Playground 使用指南

Langfuse Prompt Playground 支持在浏览器中直接测试 LLM 和 Tool Calling，便于快速迭代 Prompt 和调试工具调用。

## 快速开始

### 1. 访问 Playground

1. 打开 Langfuse 界面 (http://localhost:3001)
2. 进入 **Playground** 页面
3. 选择 LLM Provider

### 2. 配置 LLM Provider

Langfuse Playground 支持多种 LLM Provider。根据 SunnyAgent 的 LLM 配置选择对应的 Provider：

#### OpenAI

```
Provider: OpenAI
Model: gpt-4o / gpt-4o-mini
API Key: 在 Settings > API Keys 中配置
```

#### Anthropic

```
Provider: Anthropic
Model: claude-3-opus-20240229 / claude-3-sonnet-20240229
API Key: 在 Settings > API Keys 中配置
```

#### DeepSeek (通过 OpenAI Compatible)

```
Provider: OpenAI Compatible
Base URL: https://api.deepseek.com/v1
Model: deepseek-chat
API Key: DeepSeek API Key
```

### 3. 测试 Prompt

在 Playground 中输入 Prompt 并测试 LLM 响应：

```
System Prompt:
你是一个有帮助的 AI 助手。请直接、简洁地回复用户消息。
你必须始终用中文回复用户。

User Message:
你好，请介绍一下自己
```

## Tool Calling 测试

### 添加工具

在 Playground 中可以添加工具定义来测试 Tool Calling：

1. 点击 **Add Tool** 按钮
2. 粘贴工具的 JSON Schema
3. 发送消息测试工具调用

### 示例工具 Schema

#### execute_python

```json
{
  "name": "execute_python",
  "description": "Execute Python code in a sandboxed environment",
  "parameters": {
    "type": "object",
    "properties": {
      "code": {
        "type": "string",
        "description": "Python code to execute"
      }
    },
    "required": ["code"]
  }
}
```

#### read_file

```json
{
  "name": "read_file",
  "description": "Read content from a file",
  "parameters": {
    "type": "object",
    "properties": {
      "file_id": {
        "type": "string",
        "description": "File ID to read"
      },
      "project_id": {
        "type": "string",
        "description": "Optional project ID"
      }
    },
    "required": ["file_id"]
  }
}
```

#### web_search

```json
{
  "name": "web_search",
  "description": "Search the web for information",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query"
      },
      "max_results": {
        "type": "integer",
        "description": "Maximum number of results",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
```

## Prompt 模板

### SunnyAgent 标准 System Prompt

```
你是一个通用 AI 助手，能够处理各种任务。

**重要：你必须始终用中文回复用户。**

## 能力

1. **代码执行**：使用 execute_python 运行 Python 代码
2. **文件读取**：使用 read_file 读取文件内容
3. **网络搜索**：使用 web_search 搜索网络信息

## 指南

- 将复杂任务分解为步骤
- 使用代码执行进行计算和数据处理
- 如果任务不清楚，请要求澄清
```

### 数据分析 Prompt

```
你是一个数据分析专家。

**重要：你必须始终用中文回复用户。**

## 数据结构

{file_structure}

## 任务

分析用户提供的数据并回答问题。使用 Python 代码进行数据处理和分析。

## 注意事项

- 先了解数据结构再编写代码
- 使用 pandas 进行数据处理
- 输出清晰的分析结果
```

## 最佳实践

### Prompt 迭代流程

1. **初始测试**: 使用简单消息测试基本功能
2. **边界测试**: 测试边界情况和异常输入
3. **工具测试**: 验证工具调用是否正确
4. **优化调整**: 根据结果调整 Prompt

### 调试技巧

1. **查看完整响应**: 展开 API 响应查看详细信息
2. **比较不同模型**: 同一 Prompt 测试不同模型
3. **保存 Prompt**: 使用 Prompt Management 保存有效的 Prompt

## 与 SunnyAgent 集成

### 从 Trace 复制 Prompt

1. 在 Langfuse Traces 中找到感兴趣的调用
2. 复制 System Prompt 和 User Message
3. 在 Playground 中粘贴并测试

### 导出 Prompt 到代码

在 Playground 中测试完成后，可以将 Prompt 应用到 SunnyAgent：

1. 复制测试通过的 Prompt
2. 更新对应的 Prompt 模板文件
3. 重启服务生效

## 参考资源

- [Langfuse Playground 文档](https://langfuse.com/docs/playground)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use](https://docs.anthropic.com/en/docs/tool-use)
