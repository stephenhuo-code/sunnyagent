# 示例：生成的技能

这是引导过程后生成的技能示例。此示例是一家名为 "ShopCo" 的虚拟电商公司，使用 Snowflake。

---

## 示例 SKILL.md

```markdown
---
name: shopco-data-analyst
description: "ShopCo Snowflake 数据分析技能。提供查询电商数据的上下文，包括客户、订单和产品分析。用于分析 ShopCo 数据：(1) 收入和订单指标，(2) 客户行为和留存，(3) 产品表现，或任何需要 ShopCo 特定上下文的数据问题。"
---

# ShopCo 数据分析

## SQL 方言：Snowflake

- **表引用**：`SHOPCO_DW.SCHEMA.TABLE` 或用引号表示大小写敏感：`"Column_Name"`
- **安全除法**：`DIV0(a, b)` 返回 0，`DIV0NULL(a, b)` 返回 NULL
- **日期函数**：
  - `DATE_TRUNC('MONTH', date_col)`
  - `DATEADD(DAY, -1, date_col)`
  - `DATEDIFF(DAY, start_date, end_date)`
- **列排除**：`SELECT * EXCLUDE (column_to_exclude)`

---

## 实体消歧

**"客户" 可能指：**
- **用户**：可以浏览和保存商品的登录账户（CORE.DIM_USERS: user_id）
- **客户**：至少完成一次购买的用户（CORE.DIM_CUSTOMERS: customer_id）
- **账户**：计费实体，B2B 中可以有多个用户（CORE.DIM_ACCOUNTS: account_id）

**关系：**
- 用户 → 客户：1:1（customer_id = user_id 对于购买者）
- 账户 → 用户：1:多（通过 account_id 关联）

---

## 业务术语

| 术语 | 定义 | 说明 |
|------|------------|-------|
| GMV | 商品交易总额 - 退货/折扣前的订单总值 | 用于顶线报告 |
| NMV | 净商品交易额 - GMV 减去退货和折扣 | 用于实际收入 |
| AOV | 平均订单价值 - NMV / 订单数 | 排除 $0 订单 |
| LTV | 生命周期价值 - 客户首次订单以来的总 NMV | 滚动计算，每日更新 |
| CAC | 客户获取成本 - 营销支出 / 新客户数 | 按群组月份 |

---

## 标准筛选

除非明确告知，否则始终应用这些筛选：

```sql
-- 排除测试和内部订单
WHERE order_status != 'TEST'
  AND customer_type != 'INTERNAL'
  AND is_employee_order = FALSE

-- 收入指标排除取消的订单
  AND order_status NOT IN ('CANCELLED', 'FRAUDULENT')
```

---

## 关键指标

### 商品交易总额 (GMV)
- **定义**：所有下单订单的总价值
- **公式**：`SUM(order_total_gross)`
- **来源**：`CORE.FCT_ORDERS.order_total_gross`
- **时间粒度**：每日，聚合到每周/每月
- **注意事项**：包含可能稍后被取消或退货的订单

### 净收入
- **定义**：退货和折扣后的实际收入
- **公式**：`SUM(order_total_gross - return_amount - discount_amount)`
- **来源**：`CORE.FCT_ORDERS`
- **注意事项**：退货可能在订单后 90 天内发生；使用 settled_revenue 获取最终数字

---

## 知识库导航

| 领域 | 参考文件 | 用途 |
|--------|----------------|---------|
| 订单 | `references/orders.md` | 订单表、GMV/NMV 计算 |
| 客户 | `references/customers.md` | 用户/客户实体、LTV、群组 |
| 产品 | `references/products.md` | 目录、库存、类别 |

---

## 常见查询模式

### 按渠道的每日 GMV
```sql
SELECT
    DATE_TRUNC('DAY', order_timestamp) AS order_date,
    channel,
    SUM(order_total_gross) AS gmv,
    COUNT(DISTINCT order_id) AS order_count
FROM SHOPCO_DW.CORE.FCT_ORDERS
WHERE order_status NOT IN ('TEST', 'CANCELLED', 'FRAUDULENT')
  AND order_timestamp >= DATEADD(DAY, -30, CURRENT_DATE())
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
```

### 客户群组留存
```sql
WITH cohorts AS (
    SELECT
        customer_id,
        DATE_TRUNC('MONTH', first_order_date) AS cohort_month
    FROM SHOPCO_DW.CORE.DIM_CUSTOMERS
)
SELECT
    c.cohort_month,
    DATEDIFF(MONTH, c.cohort_month, DATE_TRUNC('MONTH', o.order_timestamp)) AS months_since_first,
    COUNT(DISTINCT c.customer_id) AS active_customers
FROM cohorts c
JOIN SHOPCO_DW.CORE.FCT_ORDERS o ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('TEST', 'CANCELLED')
GROUP BY 1, 2
ORDER BY 1, 2
```
```

---

## 示例 references/orders.md

```markdown
# 订单表

ShopCo 的订单和交易数据。

---

## 关键表

### FCT_ORDERS
**位置**：`SHOPCO_DW.CORE.FCT_ORDERS`
**描述**：所有订单的事实表。每个订单一行。
**主键**：`order_id`
**更新频率**：每小时（15 分钟延迟）
**分区依据**：`order_date`

| 列 | 类型 | 描述 | 说明 |
|--------|------|-------------|-------|
| **order_id** | VARCHAR | 唯一订单标识符 | |
| **customer_id** | VARCHAR | FK 到 DIM_CUSTOMERS | 访客结账为 NULL |
| **order_timestamp** | TIMESTAMP_NTZ | 下单时间 | UTC |
| **order_date** | DATE | order_timestamp 的日期部分 | 分区列 |
| **order_status** | VARCHAR | 当前状态 | PENDING、SHIPPED、DELIVERED、CANCELLED、RETURNED |
| **channel** | VARCHAR | 获客渠道 | WEB、APP、MARKETPLACE |
| **order_total_gross** | DECIMAL(12,2) | 折扣前总额 | |
| **discount_amount** | DECIMAL(12,2) | 应用的总折扣 | |
| **return_amount** | DECIMAL(12,2) | 退货商品价值 | 异步更新 |

**关系**：
- 通过 `customer_id` 关联到 `DIM_CUSTOMERS`
- 通过 `order_id` 作为 `FCT_ORDER_ITEMS` 的父表

---

## 示例查询

### 带退货率的订单
```sql
SELECT
    DATE_TRUNC('WEEK', order_date) AS week,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN return_amount > 0 THEN 1 ELSE 0 END) AS orders_with_returns,
    DIV0(SUM(CASE WHEN return_amount > 0 THEN 1 ELSE 0 END), COUNT(*)) AS return_rate
FROM SHOPCO_DW.CORE.FCT_ORDERS
WHERE order_status NOT IN ('TEST', 'CANCELLED')
  AND order_date >= DATEADD(MONTH, -3, CURRENT_DATE())
GROUP BY 1
ORDER BY 1
```
```

---

此示例演示：
- 带触发描述的完整前言
- 方言特定的 SQL 说明
- 清晰的实体消歧
- 术语表
- 作为可复制粘贴 SQL 的标准筛选
- 带公式的指标定义
- 导航到参考文件
- 真实、可运行的查询示例
