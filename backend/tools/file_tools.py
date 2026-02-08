"""File reading tools for uploaded files."""

from pathlib import Path

from langchain_core.tools import tool

MAX_TEXT_SIZE = 50 * 1024  # 50KB 文本截断限制
MAX_PDF_PAGES = 20  # PDF 最多读取 20 页
MAX_EXCEL_ROWS = 500  # Excel 最多读取 500 行


@tool
def read_uploaded_file(file_id: str) -> str:
    """读取用户上传的文件内容。

    支持的文件类型：
    - 文本文件：txt, md, json, csv（直接读取，超过50KB截断）
    - PDF 文件：提取文本内容（最多读取前20页）
    - Word 文件：docx（提取文本内容）
    - Excel 文件：xlsx, xls（提取表格数据，最多500行）
    - PowerPoint 文件：pptx（提取幻灯片文本）

    Args:
        file_id: 文件 ID（从用户消息的附件信息中获取）

    Returns:
        文件内容的文本形式
    """
    file_dir = Path(f"/tmp/sunnyagent_files/{file_id}")
    if not file_dir.exists():
        return f"错误：找不到文件 ID {file_id}"

    files = list(file_dir.iterdir())
    if not files:
        return f"错误：文件 ID {file_id} 目录为空"

    file_path = files[0]
    ext = file_path.suffix.lower()

    # 文本文件
    if ext in {".txt", ".md", ".json", ".csv"}:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > MAX_TEXT_SIZE:
                return (
                    content[:MAX_TEXT_SIZE]
                    + f"\n\n[... 内容已截断，原文件共 {len(content)} 字符 ...]"
                )
            return content
        except Exception as e:
            return f"读取文件失败：{e}"

    # PDF 文件
    if ext == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)
            pages_to_read = min(total_pages, MAX_PDF_PAGES)

            pages_text = []
            for i in range(pages_to_read):
                text = reader.pages[i].extract_text() or ""
                pages_text.append(f"[Page {i+1}]\n{text}")

            result = "\n\n".join(pages_text)
            if total_pages > MAX_PDF_PAGES:
                result += f"\n\n[... 仅显示前 {MAX_PDF_PAGES} 页，原文件共 {total_pages} 页 ...]"
            return result
        except Exception as e:
            return f"读取 PDF 失败：{e}"

    # Word 文件 (docx)
    if ext == ".docx":
        try:
            from docx import Document

            doc = Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            content = "\n\n".join(paragraphs)
            if len(content) > MAX_TEXT_SIZE:
                return (
                    content[:MAX_TEXT_SIZE]
                    + f"\n\n[... 内容已截断，原文件共 {len(content)} 字符 ...]"
                )
            return content
        except Exception as e:
            return f"读取 Word 文件失败：{e}"

    # 旧版 Word 文件 (doc) - 不支持直接读取
    if ext == ".doc":
        return (
            f"文件 '{file_path.name}' 是旧版 Word 格式 (.doc)，无法直接读取。\n"
            "建议：请将文件另存为 .docx 格式后重新上传，或使用 activate_skill('docx') 获取处理指南。"
        )

    # Excel 文件 (xlsx, xls)
    if ext in {".xlsx", ".xls"}:
        try:
            from openpyxl import load_workbook

            wb = load_workbook(str(file_path), read_only=True, data_only=True)
            result_parts = []

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                result_parts.append(f"=== Sheet: {sheet_name} ===")

                rows = []
                row_count = 0
                for row in sheet.iter_rows(values_only=True):
                    if row_count >= MAX_EXCEL_ROWS:
                        result_parts.append(f"\n[... 仅显示前 {MAX_EXCEL_ROWS} 行 ...]")
                        break
                    # Convert row to string, handling None values
                    row_str = "\t".join(str(cell) if cell is not None else "" for cell in row)
                    if row_str.strip():  # Skip empty rows
                        rows.append(row_str)
                        row_count += 1

                result_parts.append("\n".join(rows))

            wb.close()
            return "\n\n".join(result_parts)
        except Exception as e:
            return f"读取 Excel 文件失败：{e}"

    # PowerPoint 文件 (pptx)
    if ext == ".pptx":
        try:
            from pptx import Presentation

            prs = Presentation(str(file_path))
            slides_text = []

            for i, slide in enumerate(prs.slides, 1):
                slide_content = [f"[Slide {i}]"]
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_content.append(shape.text)
                slides_text.append("\n".join(slide_content))

            return "\n\n".join(slides_text)
        except Exception as e:
            return f"读取 PowerPoint 文件失败：{e}"

    # 旧版 PowerPoint 文件 (ppt) - 不支持直接读取
    if ext == ".ppt":
        return (
            f"文件 '{file_path.name}' 是旧版 PowerPoint 格式 (.ppt)，无法直接读取。\n"
            "建议：请将文件另存为 .pptx 格式后重新上传。"
        )

    return f"不支持的文件类型：{ext}"
