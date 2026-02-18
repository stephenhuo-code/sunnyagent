"""
File context service for preparing project files as LLM conversation context.

This service handles:
1. Lazy extraction of file content when needed
2. Mixed token allocation strategy (budget 20k tokens)
3. Generating summaries for large files
4. Providing tool hints for complete file access
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.db import get_pool
from backend.services.file_extractor import ExtractedContent, FileExtractor

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """提取的文件信息"""

    file_id: str
    filename: str
    content: str
    tokens: int
    structured_data: dict | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class FileContextResult:
    """文件上下文准备结果"""

    injected_content: str  # 直接注入的内容（短文件 + 可能的长文件完整内容）
    file_summaries: list[dict]  # 文件摘要列表（长文件）
    tool_hint: str  # 工具调用提示
    total_tokens: int  # 总 token 数
    file_count: int  # 处理的文件数量


class FileContextService:
    """项目文件上下文服务

    与 ContextManager 协作但职责独立：
    - FileContextService: 静态文件上下文，在 /api/chat 入口处理
    - ContextManager: 动态任务上下文，在 AIME 任务执行中管理
    """

    # Token 分配策略参数（20k 预算）
    TOKEN_BUDGET = 20000  # 总预算
    SHORT_THRESHOLD = 4000  # 短文件阈值
    SUMMARY_TARGET = 500  # 摘要目标长度
    MIN_FILE_ALLOCATION = 800  # 每个文件最小分配

    # 提取缓存（简单的内存缓存）
    _extract_cache: dict[str, tuple[ExtractedContent, float]] = {}
    CACHE_TTL = 300  # 5 分钟

    def __init__(self):
        self.extractor = FileExtractor()
        self._llm = None  # Lazy load for summary generation

    async def prepare_context(
        self,
        file_ids: list[str],
        user_id: str,
        project_id: str,
    ) -> FileContextResult:
        """准备多文件上下文，使用混合分配策略

        调用时机：/api/chat 入口，在消息进入 AIMEPlanner 之前

        Args:
            file_ids: 项目文件 ID 列表
            user_id: 用户 ID
            project_id: 项目 ID

        Returns:
            FileContextResult: 包含注入内容、摘要和工具提示
        """
        if not file_ids:
            return FileContextResult(
                injected_content="",
                file_summaries=[],
                tool_hint="",
                total_tokens=0,
                file_count=0,
            )

        # 1. 按需提取所有文件内容（Lazy Extraction）
        files = await self._extract_all_files(file_ids, user_id, project_id)

        if not files:
            return FileContextResult(
                injected_content="",
                file_summaries=[],
                tool_hint="",
                total_tokens=0,
                file_count=0,
            )

        # 2. 分类：短文件 vs 长文件
        short_files, long_files = self._classify_files(files)

        # 3. 分配 token 预算
        injected, summaries, used_tokens = await self._allocate_budget(
            short_files, long_files
        )

        # 4. 构建工具提示（如有长文件需要摘要）
        tool_hint = ""
        if summaries:
            tool_hint = self._build_tool_hint(
                [s["file_id"] for s in summaries], project_id
            )

        return FileContextResult(
            injected_content=injected,
            file_summaries=summaries,
            tool_hint=tool_hint,
            total_tokens=used_tokens,
            file_count=len(files),
        )

    async def _extract_all_files(
        self, file_ids: list[str], user_id: str, project_id: str
    ) -> list[FileInfo]:
        """按需提取所有文件内容"""
        files = []

        # 查询项目文件信息
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT pf.file_id, pf.storage_path, pf.original_name
                FROM project_files pf
                JOIN projects p ON pf.project_id = p.id
                WHERE pf.file_id = ANY($1)
                  AND p.id = $2
                  AND p.user_id = $3
                  AND p.is_deleted = FALSE
                """,
                file_ids,
                project_id,
                user_id,
            )

        for row in rows:
            file_id = row["file_id"]
            storage_path = Path(row["storage_path"])
            original_name = row["original_name"]

            # 使用缓存或提取
            content = self._extract_with_cache(file_id, storage_path)

            files.append(
                FileInfo(
                    file_id=file_id,
                    filename=original_name,
                    content=content.raw_text,
                    tokens=content.estimated_tokens,
                    structured_data=content.structured_data,
                    metadata=content.metadata,
                )
            )

        return files

    def _extract_with_cache(
        self, file_id: str, file_path: Path
    ) -> ExtractedContent:
        """带缓存的文件提取"""
        cached = self._extract_cache.get(file_id)
        if cached:
            content, timestamp = cached
            if time.time() - timestamp < self.CACHE_TTL:
                return content

        content = self.extractor.extract(file_path)
        self._extract_cache[file_id] = (content, time.time())
        return content

    def _classify_files(
        self, files: list[FileInfo]
    ) -> tuple[list[FileInfo], list[FileInfo]]:
        """分类文件：短文件 vs 长文件"""
        short_files = []
        long_files = []

        for f in files:
            if f.tokens < self.SHORT_THRESHOLD:
                short_files.append(f)
            else:
                long_files.append(f)

        return short_files, long_files

    async def _allocate_budget(
        self, short_files: list[FileInfo], long_files: list[FileInfo]
    ) -> tuple[str, list[dict], int]:
        """混合分配策略实现（20k 预算）

        策略：
        1. 短文件优先完整注入（按 token 升序，贪心）
        2. 长文件：预算充足直接注入，否则生成摘要
        """
        budget = self.TOKEN_BUDGET
        injected_parts = []
        summaries = []

        # 短文件：按 token 升序，贪心注入
        for f in sorted(short_files, key=lambda x: x.tokens):
            if budget >= f.tokens:
                injected_parts.append(self._format_file_content(f))
                budget -= f.tokens
            else:
                # 预算不足，降级为长文件处理
                long_files.append(f)

        # 长文件：评估是否直接注入或生成摘要
        if long_files:
            # 计算每个文件的平均可用预算
            per_file = budget // len(long_files) if budget > 0 else 0

            for f in long_files:
                # 如果预算能覆盖 80% 以上的内容，直接注入
                if per_file >= f.tokens * 0.8:
                    injected_parts.append(self._format_file_content(f))
                    budget -= f.tokens
                else:
                    # 生成摘要
                    summary = await self._generate_summary(f)
                    summaries.append(
                        {
                            "file_id": f.file_id,
                            "filename": f.filename,
                            "summary": summary,
                            "total_tokens": f.tokens,
                        }
                    )
                    budget -= self.SUMMARY_TARGET

        used_tokens = self.TOKEN_BUDGET - max(budget, 0)
        return "\n\n".join(injected_parts), summaries, used_tokens

    def _format_file_content(self, file: FileInfo) -> str:
        """格式化文件内容用于注入"""
        # 根据文件类型选择最佳格式
        suffix = Path(file.filename).suffix.lower()

        # 代码文件使用代码块
        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h",
            ".go", ".rs", ".rb", ".php", ".sql", ".sh", ".css", ".scss",
        }

        if suffix in code_extensions:
            lang = suffix[1:]  # 去掉点号
            return f"### {file.filename}\n```{lang}\n{file.content}\n```"

        # Excel/CSV 使用结构化数据
        if file.structured_data and file.structured_data.get("type") in ("excel", "csv"):
            return f"### {file.filename}\n{file.content}"

        # 其他文件使用普通代码块
        return f"### {file.filename}\n```\n{file.content}\n```"

    async def _generate_summary(self, file: FileInfo) -> str:
        """为长文件生成摘要

        使用 LLM 生成摘要，如果 LLM 不可用则使用简单截取
        """
        try:
            # 懒加载 LLM
            if self._llm is None:
                from backend.llm import get_model

                self._llm = get_model("file_context")

            # 准备摘要提示
            truncated_content = file.content[:8000]  # 限制输入长度
            prompt = f"""请为以下文件内容生成简洁摘要（200-300字）：

文件名：{file.filename}
内容：
{truncated_content}

摘要要求：
1. 概述文件的主要内容和用途
2. 列出关键信息点（如表格的列名、代码的主要功能等）
3. 如有结构化数据，说明数据规模和格式

摘要："""

            response = await self._llm.ainvoke(prompt)
            content = response.content
            if isinstance(content, list):
                # Handle list of content blocks
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                return "".join(text_parts).strip()
            return str(content).strip()

        except Exception as e:
            logger.warning(f"生成摘要失败，使用简单截取: {e}")
            # 降级方案：简单截取
            return self._simple_summary(file)

    def _simple_summary(self, file: FileInfo) -> str:
        """简单摘要（LLM 不可用时的降级方案）"""
        # 从元数据构建摘要
        meta = file.metadata
        suffix = Path(file.filename).suffix.lower()

        if suffix in (".xlsx", ".xls"):
            sheet_count = meta.get("sheet_count", "未知")
            total_rows = meta.get("total_rows", "未知")
            return f"Excel 文件，包含 {sheet_count} 个工作表，共 {total_rows} 行数据。"
        elif suffix == ".csv":
            row_count = meta.get("row_count", "未知")
            col_count = meta.get("column_count", "未知")
            return f"CSV 文件，包含 {col_count} 列，{row_count} 行数据。"
        elif suffix == ".pdf":
            pages = meta.get("total_pages", "未知")
            return f"PDF 文档，共 {pages} 页。前 500 字：{file.content[:500]}..."
        elif suffix == ".docx":
            para_count = meta.get("paragraph_count", "未知")
            return f"Word 文档，共 {para_count} 段。前 500 字：{file.content[:500]}..."
        elif suffix == ".pptx":
            slide_count = meta.get("slide_count", "未知")
            return f"PowerPoint 演示文稿，共 {slide_count} 页幻灯片。"
        else:
            # 通用处理
            return f"文件内容概要：{file.content[:500]}..."

    def _build_tool_hint(self, file_ids: list[str], project_id: str) -> str:
        """构建工具调用提示"""
        return f"""
[工具提示]
以上大文件仅提供摘要。如需查看完整内容，可使用 read_project_file 工具：
- read_project_file(file_id="<文件ID>", project_id="{project_id}")
"""

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数（可复用方法）"""
        return len(text) // 3

    def clear_cache(self):
        """清理提取缓存"""
        self._extract_cache.clear()

    def clear_expired_cache(self):
        """清理过期缓存"""
        now = time.time()
        expired = [
            k for k, (_, ts) in self._extract_cache.items()
            if now - ts > self.CACHE_TTL
        ]
        for k in expired:
            del self._extract_cache[k]
