# Quickstart: Project Management

**Feature**: 006-project-management
**Date**: 2026-02-17

本文档提供项目管理功能的快速测试场景和验证步骤。

---

## 前置条件

1. 数据库迁移已执行: `cd infra && uv run alembic upgrade head`
2. 后端已启动: `uv run uvicorn backend.main:app --reload --port 8008`
3. 前端已启动: `cd frontend && npm run dev`
4. 已登录用户账号

---

## 场景 1: 创建第一个项目

### 步骤

1. 登录后查看左侧导航,确认看到 "PROJECTS" section (初始为空)
2. 点击 "PROJECTS" 右侧的 `+` 按钮
3. 在弹出的对话框中输入项目名称: "研究笔记"
4. 点击 "创建项目"

### 预期结果

- ✅ 新项目 "研究笔记" 出现在 PROJECTS 列表中
- ✅ 项目列表按更新时间排序 (最新在前)
- ✅ Toast 提示 "项目创建成功"

### API 验证

```bash
# 获取项目列表
curl -X GET http://localhost:8008/api/projects \
  -H "Cookie: access_token=<token>"

# 预期响应 (示例)
[
  {
    "id": "xxx-xxx-xxx",
    "name": "研究笔记",
    "file_count": 0,
    "conversation_count": 0,
    "created_at": "2026-02-17T10:00:00Z",
    "updated_at": "2026-02-17T10:00:00Z"
  }
]
```

---

## 场景 2: 上传文件到项目

### 步骤

1. 点击 "研究笔记" 项目,进入项目工作区
2. 在左侧 Sources 面板,点击 "+ Add sources" 按钮
3. 选择一个 PDF 文件 (如 `AIME.pdf`, <10MB)
4. 等待上传完成

### 预期结果

- ✅ 文件出现在 Sources 列表中,显示文件名和图标
- ✅ 文件可勾选 (checkbox)
- ✅ 刷新页面后文件仍然存在

### 边界条件测试

| 测试 | 预期 |
|------|------|
| 上传 >10MB 文件 | 显示错误: "文件大小不能超过 10MB" |
| 上传 .exe 文件 | 显示错误: "不支持的文件类型" |
| 上传同名文件 | 显示错误: "文件名已存在" |
| 上传第 51 个文件 | 显示错误: "项目文件数量已达上限 (50)" |

---

## 场景 3: 使用文件作为对话上下文

### 步骤

1. 在项目工作区,勾选一个或多个文件
2. 观察 Chat 输入框显示 "X source(s)"
3. 输入问题: "总结这些文件的主要内容"
4. 发送消息

### 预期结果

- ✅ Chat 输入框显示选中文件数量
- ✅ 对话正常进行,AI 能访问选中文件内容
- ✅ 取消勾选文件后,显示 "0 sources" 或隐藏

### 验证文件上下文

```bash
# 发送带文件的消息
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=<token>" \
  -d '{
    "thread_id": "xxx",
    "message": "总结文件内容",
    "file_ids": ["file-id-1", "file-id-2"]
  }'
```

---

## 场景 4: 将对话添加到项目

### 步骤

1. 在左侧导航,展开 "HISTORY" section
2. 右键点击一个现有对话
3. 选择 "添加到项目" → "研究笔记"

### 预期结果

- ✅ 对话从 History 移动到 "研究笔记" 项目下
- ✅ 展开项目可看到该对话
- ✅ History 中不再显示该对话

### API 验证

```bash
# 关联对话到项目
curl -X POST http://localhost:8008/api/conversations/{id}/project \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=<token>" \
  -d '{"project_id": "project-uuid"}'
```

---

## 场景 5: 从项目移除对话

### 步骤

1. 展开 "研究笔记" 项目
2. 右键点击项目下的一个对话
3. 选择 "从项目移除"

### 预期结果

- ✅ 对话从项目中移除
- ✅ 对话回到 History 列表
- ✅ 对话内容不受影响

---

## 场景 6: 重命名项目

### 步骤

1. 右键点击 "研究笔记" 项目
2. 选择 "重命名"
3. 输入新名称: "AI 研究"
4. 确认

### 预期结果

- ✅ 项目名称更新为 "AI 研究"
- ✅ 项目关联的文件和对话不受影响

### 边界条件测试

| 测试 | 预期 |
|------|------|
| 重命名为已存在的名称 | 显示错误: "项目名称已存在" |
| 重命名为空字符串 | 显示错误: "项目名称不能为空" |
| 重命名为 >100 字符 | 显示错误: "项目名称长度超过限制" |

---

## 场景 7: 删除项目

### 步骤

1. 右键点击 "AI 研究" 项目
2. 选择 "删除项目"
3. 在确认对话框中点击 "确认删除"

### 预期结果

- ✅ 项目从列表中移除
- ✅ 项目关联的文件从存储中删除
- ✅ 项目关联的对话回到 History (不删除)
- ✅ 确认对话框防止误操作

### API 验证

```bash
# 删除前检查文件
ls /data/project_files/{user_id}/{project_id}/

# 删除项目
curl -X DELETE http://localhost:8008/api/projects/{id} \
  -H "Cookie: access_token=<token>"

# 删除后确认文件已清理
ls /data/project_files/{user_id}/{project_id}/  # 应该不存在
```

---

## 场景 8: 权限隔离测试

### 步骤

1. 用户 A 创建项目 "私密项目"
2. 用户 B 尝试访问该项目

### 预期结果

- ✅ 用户 B 看不到用户 A 的项目
- ✅ 用户 B 直接访问项目 API 返回 403 Forbidden

### API 验证

```bash
# 用户 B 尝试访问用户 A 的项目
curl -X GET http://localhost:8008/api/projects/{user_a_project_id} \
  -H "Cookie: access_token=<user_b_token>"

# 预期响应
{"detail": "无权限访问该项目"}
```

---

## 场景 9: Sources 面板收起/展开

### 步骤

1. 进入项目工作区
2. 点击 Sources 面板右上角的收起按钮
3. 观察 Chat 面板扩展
4. 点击左侧展开按钮恢复

### 预期结果

- ✅ 收起动画 <300ms
- ✅ Chat 面板平滑扩展占满宽度
- ✅ 收起状态下出现展开触发按钮
- ✅ 展开后文件选择状态保持

---

## 性能验收标准

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 项目列表加载 | <500ms | 浏览器 Network 面板 |
| 项目创建 | <10s | 端到端计时 |
| 文件上传 (10MB) | <30s | 端到端计时 |
| Sources 收起/展开 | <300ms | 动画时间 |
| 50 项目 UI 响应 | 无明显卡顿 | 手动滚动测试 |
