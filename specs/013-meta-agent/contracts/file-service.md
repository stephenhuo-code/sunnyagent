# Contract: File Service

**Module**: `meta_agent/services/file_service.py`
**Version**: 1.0.0
**Date**: 2026-03-04

## Overview

文件操作服务，负责读写 Plugin 文件。强制执行 `packages/` 目录限制。

## Configuration

```python
PACKAGES_DIR: str = "packages"  # 相对于仓库根目录
ALLOWED_EXTENSIONS: list[str] = [".md", ".json"]
```

## Interface

### Path Validation

```python
class FileService:
    """文件操作服务"""

    def __init__(self, repo_root: str):
        """
        初始化

        Args:
            repo_root: 仓库根目录的绝对路径
        """

    def is_allowed_path(self, file_path: str) -> bool:
        """
        检查路径是否在允许范围内

        Args:
            file_path: 相对或绝对路径

        Returns:
            是否允许操作
        """

    def validate_path(self, file_path: str) -> str:
        """
        验证并规范化路径

        Args:
            file_path: 文件路径

        Returns:
            规范化的绝对路径

        Raises:
            PathNotAllowedError: 路径不在 packages/ 内
            InvalidPathError: 路径格式无效
        """
```

### Read Operations

```python
    def read_file(self, file_path: str) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容

        Raises:
            FileNotFoundError: 文件不存在
            PathNotAllowedError: 路径不允许
        """

    def read_command(self, plugin_name: str, command_name: str) -> Command:
        """
        读取 Command 定义

        Args:
            plugin_name: Plugin 名称
            command_name: Command 名称

        Returns:
            Command 对象
        """

    def read_skill(self, plugin_name: str, skill_name: str) -> Skill:
        """
        读取 Skill 定义

        Args:
            plugin_name: Plugin 名称
            skill_name: Skill 名称

        Returns:
            Skill 对象
        """

    def list_commands(self, plugin_name: str) -> list[str]:
        """列出 Plugin 的所有 Command"""

    def list_skills(self, plugin_name: str) -> list[str]:
        """列出 Plugin 的所有 Skill"""
```

### Write Operations

```python
    def write_file(
        self,
        file_path: str,
        content: str,
        create_dirs: bool = True
    ) -> None:
        """
        写入文件

        Args:
            file_path: 文件路径
            content: 文件内容
            create_dirs: 是否自动创建目录

        Raises:
            PathNotAllowedError: 路径不在 packages/ 内
        """

    def write_command(
        self,
        plugin_name: str,
        command: Command
    ) -> str:
        """
        写入 Command 定义

        Returns:
            写入的文件路径
        """

    def write_skill(
        self,
        plugin_name: str,
        skill: Skill
    ) -> str:
        """
        写入 Skill 定义

        Returns:
            写入的文件路径
        """

    def backup_file(self, file_path: str) -> str:
        """
        备份文件

        Returns:
            备份文件路径
        """
```

### Directory Operations

```python
    def ensure_plugin_structure(self, plugin_name: str) -> None:
        """
        确保 Plugin 目录结构存在

        Creates:
            packages/{plugin}/
            packages/{plugin}/.plugin/
            packages/{plugin}/commands/
            packages/{plugin}/skills/
        """

    def plugin_exists(self, plugin_name: str) -> bool:
        """检查 Plugin 是否存在"""

    def get_plugin_path(self, plugin_name: str) -> str:
        """获取 Plugin 目录路径"""
```

## Error Handling

```python
class FileServiceError(Exception):
    """文件服务错误"""
    pass

class PathNotAllowedError(FileServiceError):
    """路径不在允许范围内

    这是安全关键错误，必须记录并拒绝操作。
    """
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Path not allowed: {path} - {reason}")

class InvalidPathError(FileServiceError):
    """路径格式无效"""
    pass

class PluginNotFoundError(FileServiceError):
    """Plugin 不存在"""
    pass
```

## Security Rules

1. **白名单目录**: 只允许操作 `packages/` 目录下的文件
2. **路径遍历防护**: 禁止 `..` 和符号链接跳出限制
3. **扩展名限制**: 只允许 `.md` 和 `.json` 文件
4. **审计日志**: 记录所有写操作

```python
# 路径验证逻辑
def validate_path(self, file_path: str) -> str:
    # 1. 转换为绝对路径
    abs_path = os.path.abspath(file_path)

    # 2. 解析符号链接
    real_path = os.path.realpath(abs_path)

    # 3. 检查是否在 packages/ 目录内
    packages_dir = os.path.join(self.repo_root, "packages")
    if not real_path.startswith(packages_dir):
        raise PathNotAllowedError(
            file_path,
            f"Path must be within {packages_dir}"
        )

    # 4. 检查扩展名
    _, ext = os.path.splitext(real_path)
    if ext not in ALLOWED_EXTENSIONS:
        raise PathNotAllowedError(
            file_path,
            f"Extension {ext} not allowed"
        )

    return real_path
```

## Usage Example

```python
service = FileService(repo_root="/path/to/sunnyagent")

# 读取 Command
command = service.read_command("manufacturing-qc", "complaint-analysis")
print(f"Description: {command.frontmatter.description}")

# 修改并写入
command.frontmatter.description = "分析客户投诉并生成改善报告（优化版）"
service.write_command("manufacturing-qc", command)

# 尝试非法路径（会抛出异常）
try:
    service.write_file("../backend/main.py", "hacked!")
except PathNotAllowedError as e:
    print(f"Blocked: {e}")  # 预期行为

# 检查 Plugin 是否存在
if not service.plugin_exists("new-plugin"):
    service.ensure_plugin_structure("new-plugin")
```

## Audit Logging

```python
# 所有写操作记录到审计日志
{
    "timestamp": "2026-03-04T10:30:00Z",
    "operation": "write_file",
    "path": "packages/manufacturing-qc/commands/complaint-analysis.md",
    "user": "meta-agent",
    "result": "success"
}
```
