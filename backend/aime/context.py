"""Agent Context - Structured context model for LLM Agent execution.

This module defines the structured context model for AIME agents based on
the 6-layer LLM context architecture:

Layer 1: System Prompt (定义在代码中)
Layer 2: Tool Schemas (工具定义)
Layer 3: System Metadata - SessionMetadata
Layer 4: Memory Blocks (由 ContextManager 管理)
Layer 5: Files & Artifacts - FileContext
Layer 6: Message Buffer (由 LangGraph 管理)

Key design principle:
- Files are passed as metadata only (not content) to avoid intent pollution
- Agent uses read_file tool to get actual content when needed
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from backend.core.storage import get_project_files_dir, get_temp_files_dir


def _get_container_path(storage_path: str) -> str:
    """将存储路径转换为容器内路径显示。

    Args:
        storage_path: 主机上的存储路径

    Returns:
        容器内路径，如果无法转换则返回原路径
    """
    path = Path(storage_path)

    # 项目文件
    try:
        relative = path.relative_to(get_project_files_dir())
        return f"/data/project_files/{relative}"
    except ValueError:
        pass

    # 临时文件
    try:
        relative = path.relative_to(get_temp_files_dir())
        return f"/data/tmp/{relative}"
    except ValueError:
        pass

    return storage_path  # fallback


@dataclass
class FileInfo:
    """File metadata (Layer 5: Files & Artifacts).

    Only contains metadata - actual content is retrieved via read_file tool.
    This prevents file content from polluting intent analysis.

    Attributes:
        file_id: Unique file identifier
        filename: Original filename for display
        file_type: File type (pdf, excel, word, text, markdown, etc.)
        project_id: Project ID if this is a project file (None for uploads)
        storage_path: Absolute path to the file on disk
    """
    file_id: str
    filename: str
    file_type: str
    project_id: str | None = None
    storage_path: str | None = None


@dataclass
class SessionMetadata:
    """Session metadata (Layer 3: System Metadata).

    Provides current session context to the LLM.

    Attributes:
        user_id: Current user ID
        thread_id: Conversation thread ID
        project_id: Associated project ID (optional)
        project_name: Project name for display (optional)
        timestamp: Request timestamp
    """
    user_id: str
    thread_id: str
    project_id: str | None = None
    project_name: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FileContext:
    """File context (Layer 5: Files & Artifacts).

    Manages file metadata and generates prompts for LLM.
    Only contains metadata - agents must use read_file tool for content.

    Attributes:
        files: List of FileInfo metadata objects
    """
    files: list[FileInfo] = field(default_factory=list)

    def to_prompt(self) -> str:
        """Generate file prompt for LLM.

        Returns:
            Formatted prompt listing available files with tool hints.
            Empty string if no files.
        """
        if not self.files:
            return ""

        lines = ["[可用文件]"]
        for f in self.files:
            # 显示两个路径：主机路径（用于 read_file）和容器路径（用于 execute_python）
            container_path = _get_container_path(f.storage_path) if f.storage_path else "N/A"
            lines.append(f"- {f.filename}")
            lines.append(f"  - 类型: {f.file_type}")
            lines.append(f"  - 主机路径: {f.storage_path}")
            lines.append(f"  - 容器路径: {container_path}")

        lines.append("")
        lines.append("**文件使用方式**:")
        lines.append("- 读取文件内容: `read_file(file_path=\"主机路径\")`")
        lines.append("- Python 数据处理: `execute_python_with_input(input_file_paths=[\"主机路径\"], code=...)`")
        lines.append("  - 代码中使用容器路径读取，例如:")
        lines.append("    `df = pd.read_csv('容器路径')`")

        return "\n".join(lines)


@dataclass
class AgentContext:
    """Agent execution context.

    Combines all context layers that are passed to the agent at execution time.
    This is the main context object used throughout the AIME pipeline.

    Attributes:
        session: Session metadata (Layer 3)
        files: File context (Layer 5)
        memory_ids: References to Memory Blocks (Layer 4)
        explicit_agent: Force routing to specific agent (skip intent analysis)
        skill: Skill name to inject instructions
    """
    session: SessionMetadata
    files: FileContext = field(default_factory=FileContext)
    memory_ids: list[str] = field(default_factory=list)

    # Routing control
    explicit_agent: str | None = None
    skill: str | None = None

    def build_context_prompt(self) -> str:
        """Build context prompt for injection into message.

        Generates a formatted prompt containing:
        - Current date (critical for time-related queries)
        - Session information (user, project)
        - Available files (metadata only)

        Returns:
            Formatted context prompt, or empty string if no context.
        """
        parts = []

        # Current date (critical for time-related queries)
        current_date = self.session.timestamp.strftime("%Y年%m月%d日")
        parts.append(f"[当前日期]\n今天是 {current_date}")

        # Session info
        session_info = f"[会话信息]\nUser: {self.session.user_id}"
        if self.session.project_id:
            project_display = self.session.project_name or self.session.project_id
            session_info += f"\nProject: {project_display}"
        parts.append(session_info)

        # Files
        file_prompt = self.files.to_prompt()
        if file_prompt:
            parts.append(file_prompt)

        return "\n\n".join(parts) if parts else ""


def get_file_type(filename: str) -> str:
    """Determine file type from filename extension.

    Args:
        filename: The filename to analyze

    Returns:
        File type string (pdf, excel, word, text, etc.)
    """
    from pathlib import Path

    ext = Path(filename).suffix.lower()

    type_map = {
        ".pdf": "pdf",
        ".xlsx": "excel",
        ".xls": "excel",
        ".docx": "word",
        ".doc": "word",
        ".pptx": "powerpoint",
        ".ppt": "powerpoint",
        ".txt": "text",
        ".md": "markdown",
        ".json": "json",
        ".csv": "csv",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
        ".sh": "shell",
    }

    return type_map.get(ext, "unknown")
