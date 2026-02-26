# 数据分析师插件

为设计的数据分析师设计的Agent，可以支持SQL 查询、数据探索、可视化、仪表板和洞察生成。支持任何数据仓库、任何 SQL 方言和任何分析技术栈。



## 功能介绍

该Agent转变为您的数据分析协作伙伴。它帮助您探索数据集、编写优化的 SQL、构建可视化图表、创建交互式仪表板，并在与利益相关者分享之前验证分析结果。

### 连接数据仓库时

连接您的数据仓库 MCP 服务器（如 Snowflake、Databricks、BigQuery 或任何兼容 SQL 的数据库）以获得最佳体验。

- 直接查询您的数据仓库
- 探索模式和表元数据
- 端到端执行分析，无需复制粘贴
- 根据结果迭代优化查询

### 未连接数据仓库时

没有数据仓库连接的情况下，您可以粘贴 SQL 结果或上传 CSV/Excel 文件进行分析和可视化。Claude 也可以为您编写 SQL 查询供您手动执行，然后分析您提供的结果。

## 命令

| 命令 | 描述 |
|---------|-------------|
| `/analyze` | 回答数据问题——从快速查询到完整分析 |
| `/explore-data` | 分析和探索数据集以了解其结构、质量和模式 |
| `/write-query` | 使用最佳实践为您的方言编写优化的 SQL |
| `/create-viz` | 使用 Python 创建出版级质量的可视化图表 |
| `/build-dashboard` | 构建带有筛选器和图表的交互式 HTML 仪表板 |
| `/validate` | 在分享前对分析进行质量保证——方法论、准确性和偏差检查 |

## 技能

| 技能 | 描述 |
|-------|-------------|
| `sql-queries` | 跨方言的 SQL 最佳实践、常见模式和性能优化 |
| `data-exploration` | 数据分析、质量评估和模式发现 |
| `data-visualization` | 图表选择、Python 可视化代码模式和设计原则 |
| `statistical-analysis` | 描述性统计、趋势分析、异常值检测和假设检验 |
| `data-validation` | 交付前质量保证、完整性检查和文档标准 |
| `interactive-dashboard-builder` | 使用 Chart.js、筛选器和样式构建 HTML/JS 仪表板 |

## 示例工作流程

### 即席分析

```
您：/analyze 过去12个月按产品线划分的月收入趋势是什么？

Claude：[编写 SQL 查询] → [对数据仓库执行] → [生成趋势图表]
       → [识别关键模式："产品线 A 同比增长 23%，而 B 持平"]
       → [通过完整性检查验证结果]
```

### 数据探索

```
您：/explore-data users 表

Claude：[分析表：230万行，47列]
       → [报告：created_at 有 0.2% 空值，email 有 99.8% 基数]
       → [标记：status 列在 340 行中有意外值 "UNKNOWN"]
       → [建议："值得探索的高价值维度：plan_type、signup_source、country"]
```

### 查询编写

```
您：/write-query 我需要一个群组留存分析——按注册月份分组的用户，
     显示 1、3、6 和 12 个月后仍然活跃的百分比。我们使用 Snowflake。

Claude：[编写带 CTE 的优化 Snowflake SQL]
       → [添加解释每个步骤的注释]
       → [包含关于分区裁剪的性能说明]
```

### 仪表板构建

```
您：/build-dashboard 创建一个销售仪表板，包含月收入、热门产品
     和区域分布。这是数据：[粘贴 CSV]

Claude：[生成独立的 HTML 文件]
       → [包含交互式 Chart.js 可视化]
       → [添加区域和时间段的下拉筛选器]
       → [在浏览器中打开以供审查]
```

### 分享前验证

```
您：/validate [分享分析文档]

Claude：[审查方法论] → [检查流失分析中的生存偏差]
       → [验证聚合逻辑] → [标记："分母排除了试用用户，
          这可能使转化率高估约 5 个百分点"]
       → [置信度："准备好分享，但需注明注意事项"]
```

## 连接您的数据技术栈

> 如果您看到不熟悉的占位符或需要检查已连接的工具，请参阅 [CONNECTORS.md](CONNECTORS.md)。

此插件在连接到您的数据基础设施时效果最佳。为以下内容添加 MCP 服务器：

- **数据仓库**：Snowflake、Databricks、BigQuery 或任何兼容 SQL 的数据库
- **分析/BI**：Amplitude、Looker、Tableau 等
- **Notebook**：Jupyter、Hex 等
- **电子表格**：Google Sheets、Excel
- **数据编排**：Airflow、dbt、Dagster、Prefect
- **数据摄入**：Fivetran、Airbyte、Stitch

在您的 `.mcp.json` 或 Claude Code 设置中配置 MCP 服务器以启用直接数据访问。
