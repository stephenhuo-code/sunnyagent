"""
代码执行沙箱工具 - 供 Agent 调用
"""
import asyncio
import io
import os
import tarfile
import uuid

from langchain_core.tools import tool

from .container_pool import get_pool

# 临时文件存储目录
TEMP_DIR = "/tmp/sunnyagent_files"
os.makedirs(TEMP_DIR, exist_ok=True)


@tool
async def execute_python(code: str) -> str:
    """
    在安全沙箱中执行 Python 代码。

    沙箱预装的包:
    - Office: python-pptx, python-docx, openpyxl
    - 数据: pandas, numpy
    - 图像: Pillow, matplotlib
    - PDF: pypdf, pdfplumber, reportlab

    Args:
        code: 要执行的 Python 代码

    Returns:
        代码执行的输出结果，包括 stdout 和 stderr
    """
    pool = await get_pool()
    pooled = await pool.acquire()

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: pooled.container.exec_run(
                ["python", "-c", code],
                stdout=True,
                stderr=True,
                demux=True,
            ),
        )

        stdout, stderr = result.output
        output_parts = []

        if stdout:
            output_parts.append(stdout.decode())
        if stderr:
            output_parts.append(f"[Stderr]: {stderr.decode()}")

        output = "\n".join(output_parts).strip()

        if result.exit_code != 0:
            return f"执行失败 (exit code {result.exit_code}):\n{output}"

        return output if output else "执行完成，无输出"

    except Exception as e:
        return f"执行异常: {str(e)}"
    finally:
        await pool.release(pooled)


@tool
async def execute_python_with_file(code: str, output_filename: str) -> str:
    """
    执行 Python 代码并生成可下载的文件。

    代码中应将输出文件保存到 /output/ 目录。
    例如: prs.save('/output/presentation.pptx')

    Args:
        code: Python 代码
        output_filename: 期望的输出文件名（如 "report.pptx"）

    Returns:
        成功时返回包含下载链接的 markdown 文本，失败时返回错误信息
    """
    pool = await get_pool()
    pooled = await pool.acquire()

    # 生成唯一文件 ID
    file_id = str(uuid.uuid4())[:8]
    host_output_dir = os.path.join(TEMP_DIR, file_id)
    os.makedirs(host_output_dir, exist_ok=True)

    try:
        # 执行代码
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: pooled.container.exec_run(
                ["python", "-c", code],
                stdout=True,
                stderr=True,
            ),
        )

        if result.exit_code != 0:
            return f"❌ 代码执行失败:\n```\n{result.output.decode()}\n```"

        # 从容器中复制输出文件
        try:
            bits, stat = await loop.run_in_executor(
                None,
                lambda: pooled.container.get_archive(f"/output/{output_filename}"),
            )

            # 解压 tar 包
            tar_data = b"".join(bits)
            tar = tarfile.open(fileobj=io.BytesIO(tar_data))
            tar.extractall(host_output_dir)
            tar.close()

        except Exception as e:
            if "NotFound" in str(type(e).__name__) or "404" in str(e):
                return f"❌ 文件 /output/{output_filename} 未生成，请检查代码中的保存路径"
            return f"❌ 获取文件失败: {str(e)}"

        # 验证文件存在
        local_path = os.path.join(host_output_dir, output_filename)
        if not os.path.exists(local_path):
            return f"❌ 文件 {output_filename} 提取失败"

        download_url = f"/api/files/{file_id}/{output_filename}"
        return f"✅ 文件已生成\n\n[📥 点击下载 {output_filename}]({download_url})"

    except Exception as e:
        return f"❌ 执行异常: {str(e)}"
    finally:
        await pool.release(pooled)
