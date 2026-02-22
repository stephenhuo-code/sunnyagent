# Quickstart: 插件管理系统

**Feature**: 012-plugin-management
**Date**: 2026-02-21

## 测试场景

### 场景 1: 浏览已安装插件

**前置条件**: 用户已登录

**步骤**:
1. 导航到插件管理页面 (`/plugins`)
2. 查看左侧边栏插件列表
3. 点击某个插件查看详情

**预期结果**:
- 显示所有来源的插件（Preset、Package、Uploaded）
- 每个插件显示图标、名称、启用状态
- 详情面板显示 Commands、Skills、Description

**验证命令**:
```bash
# 获取插件列表
curl -X GET http://localhost:8008/api/plugins \
  -H "Cookie: access_token=<token>"

# 获取单个插件详情
curl -X GET http://localhost:8008/api/plugins/preset:research \
  -H "Cookie: access_token=<token>"
```

---

### 场景 2: 浏览插件市场

**前置条件**: 用户已登录

**步骤**:
1. 点击 "+" 按钮
2. 选择 "Browse plugins"
3. 切换 Preset / Package / Shared 标签
4. 搜索特定插件

**预期结果**:
- 显示所有公开可用的插件
- 搜索实时过滤结果
- 已安装插件显示 "Manage" 按钮

**验证命令**:
```bash
# 浏览插件市场
curl -X GET "http://localhost:8008/api/plugins/marketplace?source=package" \
  -H "Cookie: access_token=<token>"

# 搜索插件
curl -X GET "http://localhost:8008/api/plugins/marketplace?search=research" \
  -H "Cookie: access_token=<token>"
```

---

### 场景 3: 启用/禁用插件

**前置条件**: 用户已登录，存在可用插件

**步骤**:
1. 在插件详情面板找到启用开关
2. 关闭开关禁用插件
3. 在对话框输入 `/` 验证命令不出现
4. 重新开启开关

**预期结果**:
- 禁用后插件状态显示 "Disabled"
- /命令自动完成不显示该插件的 commands/skills
- 重新启用后立即生效

**验证命令**:
```bash
# 禁用插件
curl -X PATCH http://localhost:8008/api/plugins/package:content-writer \
  -H "Cookie: access_token=<token>" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# 验证插件列表（应显示 enabled: false）
curl -X GET http://localhost:8008/api/plugins/package:content-writer \
  -H "Cookie: access_token=<token>"
```

---

### 场景 4: 上传插件包

**前置条件**: 用户已登录，准备好有效的 ZIP 包

**步骤**:
1. 点击 "+" → "Upload plugin"
2. 选择或拖放 ZIP 文件
3. 等待上传和解析完成
4. 查看新插件出现在 Uploaded 分类

**预期结果**:
- 显示上传进度
- 成功后插件自动注册
- 出现在 Uploaded 分类中

**测试包结构**:
```
test-agent.zip
├── AGENTS.md
└── skills/
    └── test-skill/
        └── SKILL.md
```

**AGENTS.md 示例**:
```yaml
---
name: test-agent
description: A test agent for upload verification
version: 1.0.0
author: Test User
capabilities:
  - testing
---
# Test Agent

This is a test agent.
```

**验证命令**:
```bash
# 上传插件
curl -X POST http://localhost:8008/api/plugins/upload \
  -H "Cookie: access_token=<token>" \
  -F "file=@test-agent.zip"

# 验证已上传
curl -X GET "http://localhost:8008/api/plugins?source=uploaded" \
  -H "Cookie: access_token=<token>"
```

---

### 场景 5: /命令调用 Skill

**前置条件**: 用户已登录，存在已启用的 skill

**步骤**:
1. 在对话输入框输入 `/`
2. 从自动完成列表选择 skill
3. 输入请求内容
4. 发送消息

**预期结果**:
- 自动完成显示所有已启用的 skills
- 消息标记选中的 skill
- 后端注入 skill 指令执行

**验证命令**:
```bash
# 获取可用 skills 列表
curl -X GET http://localhost:8008/api/skills \
  -H "Cookie: access_token=<token>"

# 发送带 skill 的消息
curl -X POST http://localhost:8008/api/chat \
  -H "Cookie: access_token=<token>" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test123",
    "message": "Create a summary",
    "skill": "summarize"
  }'
```

---

### 场景 6: Workflow Skill 执行

**前置条件**: 存在 workflow 类型的 skill

**步骤**:
1. 调用 workflow skill
2. 观察多步骤执行进度
3. 查看汇总结果

**预期结果**:
- Planner 识别 workflow 类型
- 按步骤顺序执行
- 显示每个步骤进度
- 最终汇总所有步骤结果

**验证命令**:
```bash
# 调用 workflow skill
curl -X POST http://localhost:8008/api/chat \
  -H "Cookie: access_token=<token>" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test123",
    "message": "Generate a comprehensive report",
    "skill": "research-workflow"
  }'
```

---

### 场景 7: 插件评分

**前置条件**: 用户已登录，存在 Package 或 Shared 插件

**步骤**:
1. 打开 Package 插件详情
2. 点击评分区域
3. 选择 1-5 星
4. 查看平均评分更新

**预期结果**:
- 评分选择 UI 显示
- 提交后保存评分
- 平均评分实时更新

**验证命令**:
```bash
# 提交评分
curl -X PUT http://localhost:8008/api/plugins/package:content-writer/rating \
  -H "Cookie: access_token=<token>" \
  -H "Content-Type: application/json" \
  -d '{"rating": 4}'

# 获取评分
curl -X GET http://localhost:8008/api/plugins/package:content-writer/rating \
  -H "Cookie: access_token=<token>"
```

---

### 场景 8: 分享插件

**前置条件**: 用户已上传插件

**步骤**:
1. 打开 Uploaded 插件详情
2. 点击 "分享" 按钮
3. 确认分享
4. 验证插件出现在 Shared 分类

**预期结果**:
- 显示分享确认对话框
- 确认后状态变为 Shared
- 其他用户可在插件市场看到

**验证命令**:
```bash
# 分享插件
curl -X POST http://localhost:8008/api/plugins/uploaded:my-agent/share \
  -H "Cookie: access_token=<token>"

# 验证在市场中可见
curl -X GET "http://localhost:8008/api/plugins/marketplace?source=shared" \
  -H "Cookie: access_token=<token>"
```

---

## 边界条件测试

### 无效上传包

```bash
# 上传无 AGENTS.md/SKILL.md 的包
curl -X POST http://localhost:8008/api/plugins/upload \
  -H "Cookie: access_token=<token>" \
  -F "file=@invalid.zip"
# 预期: 400 Bad Request
```

### 同名插件冲突

```bash
# 上传与已有插件同名的包
curl -X POST http://localhost:8008/api/plugins/upload \
  -H "Cookie: access_token=<token>" \
  -F "file=@duplicate-name.zip"
# 预期: 200 OK（直接覆盖）
```

### 删除已分享插件

```bash
# 尝试删除已分享的插件
curl -X DELETE http://localhost:8008/api/plugins/shared:my-agent \
  -H "Cookie: access_token=<token>"
# 预期: 403 Forbidden
```

### 非所有者删除

```bash
# 用户 B 尝试删除用户 A 的插件
curl -X DELETE http://localhost:8008/api/plugins/uploaded:other-user-plugin \
  -H "Cookie: access_token=<token-user-b>"
# 预期: 404 Not Found（对用户 B 不可见）
```

---

## 集成测试检查点

1. **数据隔离**: 用户 A 的 Uploaded 插件对用户 B 不可见
2. **状态独立**: 用户 A 禁用插件不影响用户 B
3. **AIME 过滤**: 禁用的插件不参与路由
4. **/命令过滤**: 禁用的 skill 不出现在自动完成
5. **评分限制**: 仅 Package/Shared 可评分
6. **分享级联**: 分享后其他用户可启用
7. **下架保留**: 取消分享后已启用用户保留使用
