# Data Model: Langfuse 可观测性集成

**Branch**: `007-langfuse-integration` | **Date**: 2026-02-19

## Overview

本功能主要使用 Langfuse 托管的实体（Trace、Span、Dataset 等），SunnyAgent 侧只需增加少量配置和映射。

## Langfuse 托管实体（参考）

以下实体由 Langfuse 服务管理，SunnyAgent 通过 SDK/API 交互：

### Trace

表示一次完整的 Agent 执行记录。

| Field | Type | Description |
|-------|------|-------------|
| id | string | 唯一标识符 |
| name | string | Trace 名称（如 "chat-request"） |
| user_id | string | 关联的 SunnyAgent 用户 ID |
| session_id | string | 对话会话 ID（thread_id） |
| input | object | 用户输入 |
| output | object | Agent 输出 |
| metadata | object | 自定义元数据 |
| created_at | datetime | 创建时间 |

### Span

表示执行链路中的一个阶段。

| Field | Type | Description |
|-------|------|-------------|
| id | string | 唯一标识符 |
| trace_id | string | 所属 Trace ID |
| parent_span_id | string | 父 Span ID（可选） |
| name | string | Span 名称（如 "intent-analyzer"） |
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |
| input | object | 输入参数 |
| output | object | 输出结果 |
| status | string | 状态（success/error） |
| status_message | string | 错误信息（如有） |
| metadata | object | 自定义元数据 |

### Dataset

Langfuse 测试数据集。

| Field | Type | Description |
|-------|------|-------------|
| id | string | 唯一标识符 |
| name | string | 数据集名称 |
| description | string | 描述 |
| created_at | datetime | 创建时间 |
| items | DatasetItem[] | 数据集项列表 |

### DatasetItem

数据集中的单个测试用例。

| Field | Type | Description |
|-------|------|-------------|
| id | string | 唯一标识符 |
| dataset_id | string | 所属数据集 ID |
| input | object | 测试输入 |
| expected_output | object | 期望输出 |
| metadata | object | 元数据 |

### Experiment

一次评估运行记录。

| Field | Type | Description |
|-------|------|-------------|
| id | string | 唯一标识符 |
| name | string | 实验名称 |
| dataset_id | string | 关联数据集 ID |
| created_at | datetime | 创建时间 |
| runs | ExperimentRun[] | 运行记录列表 |

### Score

评估得分。

| Field | Type | Description |
|-------|------|-------------|
| id | string | 唯一标识符 |
| trace_id | string | 关联 Trace ID |
| name | string | 评分名称（如 "accuracy"） |
| value | float | 得分值 |
| comment | string | 评语 |
| source | string | 来源（llm/human/custom） |

---

## SunnyAgent 新增实体

### LangfuseUserMapping

SunnyAgent 用户与 Langfuse 用户的映射关系。

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | integer | PK, auto | 主键 |
| sunnyagent_user_id | integer | FK → users.id, unique | SunnyAgent 用户 ID |
| langfuse_user_id | string | not null | Langfuse 用户 ID |
| langfuse_email | string | not null | Langfuse 用户邮箱 |
| status | string | enum(active, disabled) | 同步状态 |
| created_at | datetime | not null | 创建时间 |
| updated_at | datetime | not null | 更新时间 |

**Relationships**:
- `sunnyagent_user_id` → `users.id` (one-to-one)

**Lifecycle**:
- Created: 当 SunnyAgent 创建新用户时，自动调用 Langfuse Admin API 创建对应用户
- Updated: 当 SunnyAgent 禁用/启用用户时，同步更新 Langfuse 用户状态
- Deleted: 当 SunnyAgent 删除用户时，从 Langfuse 组织中移除用户

---

## 配置扩展

### 环境变量

| Variable | Required | Description |
|----------|----------|-------------|
| LANGFUSE_PUBLIC_KEY | Yes | Langfuse 公钥 |
| LANGFUSE_SECRET_KEY | Yes | Langfuse 私钥 |
| LANGFUSE_BASE_URL | Yes | Langfuse 服务地址 |
| LANGFUSE_ORG_PUBLIC_KEY | Yes | Langfuse 组织公钥（Admin API） |
| LANGFUSE_ORG_SECRET_KEY | Yes | Langfuse 组织私钥（Admin API） |
| LANGFUSE_SAMPLE_RATE | No | Trace 采样率（默认 1.0） |

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    SunnyAgent Database                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐      1:1      ┌─────────────────────────┐     │
│  │   users     │──────────────▶│  langfuse_user_mapping  │     │
│  └─────────────┘               └─────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Langfuse Database                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐      1:N      ┌─────────┐                         │
│  │  Trace  │──────────────▶│  Span   │                         │
│  └────┬────┘               └─────────┘                         │
│       │                                                         │
│       │ 1:N                                                     │
│       ▼                                                         │
│  ┌─────────┐                                                    │
│  │  Score  │                                                    │
│  └─────────┘                                                    │
│                                                                 │
│  ┌─────────────┐    1:N    ┌───────────────┐                   │
│  │   Dataset   │──────────▶│  DatasetItem  │                   │
│  └──────┬──────┘           └───────────────┘                   │
│         │                                                       │
│         │ 1:N                                                   │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │  Experiment │                                                │
│  └─────────────┘                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Migration Plan

### New Table: langfuse_user_mapping

```sql
-- Migration: 005_create_langfuse_user_mapping.py

CREATE TABLE langfuse_user_mapping (
    id SERIAL PRIMARY KEY,
    sunnyagent_user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    langfuse_user_id VARCHAR(255) NOT NULL,
    langfuse_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_langfuse_user_mapping_langfuse_id ON langfuse_user_mapping(langfuse_user_id);
```
