# SQL 方言参考

根据用户的数据仓库在生成的技能中包含适当的部分。

---

## BigQuery

```markdown
## SQL 方言：BigQuery

- **表引用**：使用反引号：\`project.dataset.table\`
- **安全除法**：`SAFE_DIVIDE(a, b)` 返回 NULL 而不是错误
- **日期函数**：
  - `DATE_TRUNC(date_col, MONTH)`
  - `DATE_SUB(date_col, INTERVAL 1 DAY)`
  - `DATE_DIFF(end_date, start_date, DAY)`
- **列排除**：`SELECT * EXCEPT(column_to_exclude)`
- **数组**：`UNNEST(array_column)` 展平
- **结构**：使用点表示法访问 `struct_col.field_name`
- **时间戳**：`TIMESTAMP_TRUNC()`，时间默认为 UTC
- **字符串匹配**：`LIKE`、`REGEXP_CONTAINS(col, r'pattern')`
- **聚合中的 NULL**：大多数函数忽略 NULL；使用 `IFNULL()` 或 `COALESCE()`
```

---

## Snowflake

```markdown
## SQL 方言：Snowflake

- **表引用**：`DATABASE.SCHEMA.TABLE` 或用引号表示大小写敏感：`"Column_Name"`
- **安全除法**：`DIV0(a, b)` 返回 0，`DIV0NULL(a, b)` 返回 NULL
- **日期函数**：
  - `DATE_TRUNC('MONTH', date_col)`
  - `DATEADD(DAY, -1, date_col)`
  - `DATEDIFF(DAY, start_date, end_date)`
- **列排除**：`SELECT * EXCLUDE (column_to_exclude)`
- **数组**：`FLATTEN(array_column)` 展平，用 `value` 访问
- **变体/JSON**：使用冒号表示法访问 `variant_col:field_name`
- **时间戳**：`TIMESTAMP_NTZ`（无时区），`TIMESTAMP_TZ`（带时区）
- **字符串匹配**：`LIKE`、`REGEXP_LIKE(col, 'pattern')`
- **大小写敏感性**：标识符默认大写，除非用引号
```

---

## PostgreSQL / Redshift

```markdown
## SQL 方言：PostgreSQL/Redshift

- **表引用**：`schema.table`（小写惯例）
- **安全除法**：`NULLIF(b, 0)` 模式：`a / NULLIF(b, 0)`
- **日期函数**：
  - `DATE_TRUNC('month', date_col)`
  - `date_col - INTERVAL '1 day'`
  - `DATE_PART('day', end_date - start_date)`
- **列选择**：没有 EXCEPT；必须明确列出列
- **数组**：`UNNEST(array_column)`（PostgreSQL），Redshift 中有限
- **JSON**：`json_col->>'field_name'` 获取文本，`json_col->'field_name'` 获取 JSON
- **时间戳**：`AT TIME ZONE 'UTC'` 进行时区转换
- **字符串匹配**：`LIKE`，`col ~ 'pattern'` 用于正则
- **布尔值**：原生 BOOLEAN 类型；使用 `TRUE`/`FALSE`
```

---

## Databricks / Spark SQL

```markdown
## SQL 方言：Databricks/Spark SQL

- **表引用**：`catalog.schema.table`（Unity Catalog）或 `schema.table`
- **安全除法**：使用 `NULLIF`：`a / NULLIF(b, 0)` 或 `TRY_DIVIDE(a, b)`
- **日期函数**：
  - `DATE_TRUNC('MONTH', date_col)`
  - `DATE_SUB(date_col, 1)`
  - `DATEDIFF(end_date, start_date)`
- **列排除**：`SELECT * EXCEPT (column_to_exclude)`（Databricks SQL）
- **数组**：`EXPLODE(array_column)` 展平
- **结构**：使用点表示法访问 `struct_col.field_name`
- **JSON**：`json_col:field_name` 或 `GET_JSON_OBJECT()`
- **字符串匹配**：`LIKE`，`RLIKE` 用于正则
- **Delta 特性**：`DESCRIBE HISTORY`，使用 `VERSION AS OF` 进行时间旅行
```

---

## MySQL

```markdown
## SQL 方言：MySQL

- **表引用**：用反引号 \`database\`.\`table\`
- **安全除法**：手动：`IF(b = 0, NULL, a / b)` 或 `a / NULLIF(b, 0)`
- **日期函数**：
  - `DATE_FORMAT(date_col, '%Y-%m-01')` 用于截断
  - `DATE_SUB(date_col, INTERVAL 1 DAY)`
  - `DATEDIFF(end_date, start_date)`
- **列选择**：没有 EXCEPT；必须明确列出列
- **数组**：有限的原生支持；通常存储为 JSON
- **JSON**：`JSON_EXTRACT(col, '$.field')` 或 `col->>'$.field'`
- **时间戳**：`CONVERT_TZ()` 进行时区转换
- **字符串匹配**：`LIKE`，`REGEXP` 用于正则
- **大小写敏感性**：表名在 Linux 上区分大小写，在 Windows 上不区分
```

---

## 跨方言常见模式

| 操作 | BigQuery | Snowflake | PostgreSQL | Databricks |
|-----------|----------|-----------|------------|------------|
| 当前日期 | `CURRENT_DATE()` | `CURRENT_DATE()` | `CURRENT_DATE` | `CURRENT_DATE()` |
| 当前时间戳 | `CURRENT_TIMESTAMP()` | `CURRENT_TIMESTAMP()` | `NOW()` | `CURRENT_TIMESTAMP()` |
| 字符串连接 | `CONCAT()` 或 `\|\|` | `CONCAT()` 或 `\|\|` | `CONCAT()` 或 `\|\|` | `CONCAT()` 或 `\|\|` |
| 合并 | `COALESCE()` | `COALESCE()` | `COALESCE()` | `COALESCE()` |
| 条件判断 | `CASE WHEN` | `CASE WHEN` | `CASE WHEN` | `CASE WHEN` |
| 唯一计数 | `COUNT(DISTINCT x)` | `COUNT(DISTINCT x)` | `COUNT(DISTINCT x)` | `COUNT(DISTINCT x)` |
