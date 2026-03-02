"""
代码执行沙箱工具 - 供 Agent 调用
"""
import asyncio
import io
import logging
import mimetypes
import os
import re
import tarfile
import uuid
from pathlib import Path
from typing import Annotated

from typing import TYPE_CHECKING

from langchain_core.tools import tool, InjectedToolArg
from langgraph.prebuilt import ToolRuntime

from .container_pool import get_pool

if TYPE_CHECKING:
    from docker.models.containers import Container

logger = logging.getLogger(__name__)

# ============================================
# 自动安装缺失包相关常量和函数
# ============================================

# 运行时可安装的安全包白名单（需与 whitelist.txt 保持同步）
SAFE_PACKAGES_WHITELIST = {
    # pandas 可选依赖
    "xlrd", "xlsxwriter", "pyarrow", "fastparquet",
    "lxml", "beautifulsoup4", "html5lib",
    "sqlalchemy", "jinja2", "bottleneck", "numexpr",
    # 科学计算与统计
    "scipy", "scikit-learn", "statsmodels",
    # 数据可视化扩展
    "seaborn", "plotly",
    # 网络请求
    "requests",
    # 编码检测
    "chardet",
    # 日期时间处理
    "python-dateutil", "pytz",
}

# 模块名到包名映射（处理 import 名称与 pip 包名不同的情况）
MODULE_TO_PACKAGE = {
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
}


def _extract_missing_module(stderr: str) -> str | None:
    """从错误信息中提取缺失的模块名。

    Args:
        stderr: 标准错误输出

    Returns:
        缺失的模块名（顶层模块），如果无法提取返回 None
    """
    patterns = [
        r"No module named ['\"]([^'\"]+)['\"]",
        r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
        r"ImportError: cannot import name ['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, stderr)
        if match:
            # 返回顶层模块名（如 pandas.compat 返回 pandas）
            return match.group(1).split(".")[0]
    return None


async def _try_install_missing_package(
    container: "Container",
    module_name: str,
    loop: asyncio.AbstractEventLoop,
) -> tuple[bool, str]:
    """尝试从离线缓存安装缺失的包。

    Args:
        container: Docker 容器实例
        module_name: 缺失的模块名
        loop: 事件循环

    Returns:
        (成功标志, 消息)
    """
    # 将模块名转换为包名
    package_name = MODULE_TO_PACKAGE.get(module_name, module_name)

    # 检查是否在白名单中
    if package_name not in SAFE_PACKAGES_WHITELIST:
        return False, f"包 '{package_name}' 不在安全白名单中，无法自动安装"

    # 尝试从离线缓存安装
    install_cmd = f"pip install --no-index --find-links=/pip-cache {package_name}"
    result = await loop.run_in_executor(
        None,
        lambda: container.exec_run(
            ["sh", "-c", install_cmd],
            workdir="/workspace",
            stdout=True,
            stderr=True,
        ),
    )

    if result.exit_code != 0:
        output = result.output.decode() if result.output else ""
        return False, f"安装 {package_name} 失败: {output}"

    logger.info(f"Auto-installed missing package: {package_name}")
    return True, f"已自动安装 {package_name}"

# 临时文件存储目录
from backend.core.storage import get_temp_files_dir, get_project_files_dir
TEMP_DIR = str(get_temp_files_dir())


def _host_path_to_container_path(host_path: str) -> str | None:
    """将主机路径转换为容器内路径。

    主机路径:    /Users/.../data/project_files/abc123/file.csv
    容器内路径:  /data/project_files/abc123/file.csv

    Args:
        host_path: 主机上的文件绝对路径

    Returns:
        容器内路径，如果不在挂载目录中返回 None
    """
    host_path_obj = Path(host_path)

    # 项目文件
    project_files_dir = get_project_files_dir()
    try:
        relative = host_path_obj.relative_to(project_files_dir)
        return f"/data/project_files/{relative}"
    except ValueError:
        pass

    # 临时上传文件
    temp_files_dir = get_temp_files_dir()
    try:
        relative = host_path_obj.relative_to(temp_files_dir)
        return f"/data/tmp/{relative}"
    except ValueError:
        pass

    return None


async def _get_file_path(file_id: str, project_id: str | None = None) -> Path | None:
    """Get the actual storage path for a file (supports both upload files and project files).

    Args:
        file_id: The file ID to look up
        project_id: Project ID if this is a project file

    Returns:
        Path to the file if found, None otherwise
    """
    # 1. First check upload files
    upload_dir = Path(TEMP_DIR) / file_id
    if upload_dir.exists():
        files = list(upload_dir.iterdir())
        if files:
            return files[0]

    # 2. If project_id is provided, check project files
    if project_id:
        from backend.db import get_pool as get_db_pool

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT storage_path FROM project_files
                WHERE file_id = $1 AND project_id = $2
                """,
                file_id,
                project_id,
            )
            if row and row["storage_path"]:
                path = Path(row["storage_path"])
                if path.exists():
                    return path

    return None


async def _inject_file_to_container(
    container: "Container",
    file_path: Path,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """将文件注入到容器的 /input/ 目录

    Args:
        container: Docker 容器实例
        file_path: 要注入的文件路径
        loop: 事件循环
    """
    # 创建 tar 包
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        tar.add(str(file_path), arcname=file_path.name)
    tar_buffer.seek(0)

    # 确保 /input/ 目录存在
    await loop.run_in_executor(
        None,
        lambda: container.exec_run(["mkdir", "-p", "/input"]),
    )

    # 注入文件
    await loop.run_in_executor(
        None,
        lambda: container.put_archive("/input", tar_buffer),
    )


async def _extract_output_files(
    container: "Container",
    loop: asyncio.AbstractEventLoop,
    user_id: str | None,
) -> str:
    """检查并提取 /output/ 目录中的所有文件。

    Returns:
        包含下载链接的 markdown 字符串，无文件时返回空字符串
    """
    try:
        # 列出 /output/ 目录中的文件
        list_result = await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                ["ls", "-1", "/output/"],
                stdout=True,
                stderr=True,
            ),
        )

        if list_result.exit_code != 0:
            return ""  # /output/ 目录不存在或为空

        filenames = [
            f.strip()
            for f in list_result.output.decode().split("\n")
            if f.strip()
        ]

        if not filenames:
            return ""

        # 提取每个文件
        file_links: list[str] = []
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

        for filename in filenames:
            file_id = str(uuid.uuid4())[:8]
            host_output_dir = os.path.join(TEMP_DIR, file_id)
            os.makedirs(host_output_dir, exist_ok=True)

            try:
                # 从容器提取文件
                bits, stat = await loop.run_in_executor(
                    None,
                    lambda fn=filename: container.get_archive(f"/output/{fn}"),
                )

                tar_data = b"".join(bits)
                tar = tarfile.open(fileobj=io.BytesIO(tar_data))
                tar.extractall(host_output_dir)
                tar.close()

                local_path = os.path.join(host_output_dir, filename)
                if not os.path.exists(local_path):
                    continue

                # 注册到数据库
                if user_id:
                    try:
                        from uuid import UUID

                        from backend.files import database as files_db

                        content_type, _ = mimetypes.guess_type(filename)
                        file_size = os.path.getsize(local_path)
                        await files_db.create_file(
                            user_id=UUID(user_id),
                            file_id=file_id,
                            original_name=filename,
                            content_type=content_type or "application/octet-stream",
                            size_bytes=file_size,
                            storage_path=local_path,
                        )
                        logger.info(f"Registered generated file: {file_id}/{filename}")
                    except Exception as e:
                        logger.warning(f"Failed to register file {filename}: {e}")

                # 生成链接
                download_url = f"/api/files/{file_id}/{filename}"
                ext = Path(filename).suffix.lower()

                if ext in image_extensions:
                    # 图片: markdown 图片语法 + 下载链接
                    file_links.append(
                        f"![{filename}]({download_url})\n"
                        f"[📥 下载 {filename}]({download_url})"
                    )
                else:
                    # 其他文件: 下载链接
                    file_links.append(f"[📥 点击下载 {filename}]({download_url})")

            except Exception as e:
                logger.warning(f"Failed to extract {filename}: {e}")
                continue

        if file_links:
            return "✅ 文件已生成\n\n" + "\n\n".join(file_links)
        return ""

    except Exception as e:
        logger.warning(f"Failed to list /output/ directory: {e}")
        return ""


@tool
async def execute_python(
    code: str,
    tool_runtime: Annotated[ToolRuntime | None, InjectedToolArg] = None,
) -> str:
    """
    在安全沙箱中执行 Python 代码。

    如果代码生成文件到 /output/ 目录，系统会自动提取并返回下载链接。

    沙箱预装的包:
    - Office: python-pptx, python-docx, openpyxl
    - 数据: pandas, numpy
    - 图像: Pillow, matplotlib
    - PDF: pypdf, pdfplumber, reportlab

    示例:
        # 生成图表
        import matplotlib.pyplot as plt
        plt.plot([1,2,3], [1,4,9])
        plt.savefig('/output/chart.png')

        # 生成 Excel
        df.to_excel('/output/result.xlsx')

    Args:
        code: 要执行的 Python 代码

    Returns:
        代码执行的输出结果，包括 stdout 和 stderr。
        如果 /output/ 目录中有文件，会自动提取并返回下载链接。
    """
    pool = await get_pool()
    pooled = await pool.acquire()

    try:
        loop = asyncio.get_event_loop()

        # 定义执行代码的内部函数
        async def run_code():
            return await loop.run_in_executor(
                None,
                lambda: pooled.container.exec_run(
                    ["python", "-c", code],
                    stdout=True,
                    stderr=True,
                    demux=True,
                ),
            )

        result = await run_code()
        stdout, stderr = result.output

        # 如果执行失败，尝试自动安装缺失的包并重试
        if result.exit_code != 0 and stderr:
            stderr_text = stderr.decode()
            missing_module = _extract_missing_module(stderr_text)

            if missing_module:
                success, install_msg = await _try_install_missing_package(
                    pooled.container, missing_module, loop
                )
                if success:
                    logger.info(f"Retrying after installing {missing_module}")
                    # 重新执行代码
                    result = await run_code()
                    stdout, stderr = result.output

        output_parts = []

        if stdout:
            output_parts.append(stdout.decode())
        if stderr:
            output_parts.append(f"[Stderr]: {stderr.decode()}")

        text_output = "\n".join(output_parts).strip()

        if result.exit_code != 0:
            return f"执行失败 (exit code {result.exit_code}):\n{text_output}"

        # 获取 user_id
        user_id = None
        if tool_runtime and tool_runtime.config:
            user_id = tool_runtime.config.get("configurable", {}).get("user_id")

        # 检查并提取 /output/ 目录中的文件
        generated_files = await _extract_output_files(
            pooled.container, loop, user_id
        )

        # 组合返回结果
        if text_output and generated_files:
            return f"{text_output}\n\n{generated_files}"
        elif generated_files:
            return generated_files
        elif text_output:
            return text_output
        else:
            return "代码执行成功 (exit_code=0)。提示：如需查看计算结果，请在代码中使用 print() 输出。"

    except Exception as e:
        return f"执行异常: {str(e)}"
    finally:
        await pool.release(pooled)


@tool
async def execute_python_with_file(
    code: str,
    output_filename: str,
    tool_runtime: Annotated[ToolRuntime | None, InjectedToolArg] = None,
) -> str:
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

        async def run_code():
            return await loop.run_in_executor(
                None,
                lambda: pooled.container.exec_run(
                    ["python", "-c", code],
                    stdout=True,
                    stderr=True,
                ),
            )

        result = await run_code()

        # 如果执行失败，尝试自动安装缺失的包并重试
        if result.exit_code != 0:
            output_text = result.output.decode() if result.output else ""
            missing_module = _extract_missing_module(output_text)

            if missing_module:
                success, install_msg = await _try_install_missing_package(
                    pooled.container, missing_module, loop
                )
                if success:
                    logger.info(f"Retrying after installing {missing_module}")
                    result = await run_code()

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

        # 从 tool_runtime 的 config 中获取 user_id
        user_id = None
        if tool_runtime and tool_runtime.config:
            user_id = tool_runtime.config.get("configurable", {}).get("user_id")

        # 注册文件到数据库（需要 user_id）
        if user_id:
            try:
                from uuid import UUID
                from backend.files import database as files_db

                content_type, _ = mimetypes.guess_type(output_filename)
                file_size = os.path.getsize(local_path)
                await files_db.create_file(
                    user_id=UUID(user_id),
                    file_id=file_id,
                    original_name=output_filename,
                    content_type=content_type or "application/octet-stream",
                    size_bytes=file_size,
                    storage_path=local_path,
                )
                logger.info(f"Registered generated file: {file_id}/{output_filename}")
            except Exception as e:
                # 注册失败不影响下载链接返回，但记录日志
                logger.warning(f"Failed to register generated file: {e}")

        download_url = f"/api/files/{file_id}/{output_filename}"
        return f"✅ 文件已生成\n\n[📥 点击下载 {output_filename}]({download_url})"

    except Exception as e:
        return f"❌ 执行异常: {str(e)}"
    finally:
        await pool.release(pooled)


@tool
async def execute_python_with_input(
    code: str,
    input_file_paths: list[str] | None = None,
    input_file_ids: list[str] | None = None,
    project_id: str | None = None,
    output_filename: str | None = None,
    tool_runtime: Annotated[ToolRuntime | None, InjectedToolArg] = None,
) -> str:
    """
    执行 Python 代码，支持输入文件和可选的输出文件。

    **推荐**: 使用 input_file_paths 直接传入文件路径（从上下文中获取）。
    文件通过只读卷挂载访问，无需复制，性能更好。

    沙箱预装的包:
    - Office: python-pptx, python-docx, openpyxl
    - 数据: pandas, numpy
    - 图像: Pillow, matplotlib
    - PDF: pypdf, pdfplumber, reportlab

    Args:
        code: Python 代码
        input_file_paths: 文件路径列表（推荐，从上下文 [可用文件] 获取主机路径）
        input_file_ids: 文件 ID 列表（旧版，需要配合 project_id）
        project_id: 项目 ID（仅 input_file_ids 模式需要）
        output_filename: 可选，期望的输出文件名（保存到 /output/）

    Returns:
        执行结果，或如果指定了 output_filename 则返回下载链接

    示例:
        # 推荐用法 - 使用路径（代码中使用容器路径）
        execute_python_with_input(
            input_file_paths=["/Users/.../data/project_files/abc/sales.csv"],
            code="import pandas as pd\\ndf = pd.read_csv('/data/project_files/abc/sales.csv')\\nprint(df.head())"
        )

        # 旧版用法 - 使用 file_id（代码中使用 /input/ 路径）
        execute_python_with_input(
            input_file_ids=["abc123"],
            project_id="project-uuid",
            code="import pandas as pd\\ndf = pd.read_csv('/input/data.csv')\\nprint(df.head())"
        )
    """
    pool = await get_pool()
    pooled = await pool.acquire()
    loop = asyncio.get_event_loop()

    # 如果需要输出文件，准备目录
    file_id = None
    host_output_dir = None
    if output_filename:
        file_id = str(uuid.uuid4())[:8]
        host_output_dir = os.path.join(TEMP_DIR, file_id)
        os.makedirs(host_output_dir, exist_ok=True)

    use_legacy_injection = False
    try:
        container_input_paths: list[str] = []

        # 方式 A: 直接使用文件路径（推荐，通过挂载卷访问）
        if input_file_paths:
            for host_path in input_file_paths:
                container_path = _host_path_to_container_path(host_path)
                if container_path:
                    # 验证文件存在
                    if Path(host_path).exists():
                        container_input_paths.append(container_path)
                        logger.info(f"Mapped path: {host_path} -> {container_path}")
                    else:
                        logger.warning(f"File does not exist: {host_path}")
                else:
                    logger.warning(f"Cannot map path to container: {host_path}")

        # 方式 B: 通过 file_id 查找（向后兼容）
        if input_file_ids and not container_input_paths:
            for fid in input_file_ids:
                file_path = await _get_file_path(fid, project_id)
                if file_path:
                    # 尝试转换为容器路径
                    container_path = _host_path_to_container_path(str(file_path))
                    if container_path:
                        container_input_paths.append(container_path)
                        logger.info(f"Mapped file_id {fid}: {file_path} -> {container_path}")
                    else:
                        # Fallback: 使用原来的 tar/untar 方式
                        await _inject_file_to_container(pooled.container, file_path, loop)
                        container_input_paths.append(f"/input/{file_path.name}")
                        use_legacy_injection = True
                        logger.info(f"Injected file {file_path.name} to container /input/ (legacy mode)")

        if not container_input_paths:
            return (
                f"❌ 没有找到有效的输入文件。\n"
                f"input_file_paths: {input_file_paths}\n"
                f"input_file_ids: {input_file_ids}, project_id: {project_id}"
            )

        # 2. 执行代码
        async def run_code():
            return await loop.run_in_executor(
                None,
                lambda: pooled.container.exec_run(
                    ["python", "-c", code],
                    stdout=True,
                    stderr=True,
                    demux=True,
                ),
            )

        result = await run_code()
        stdout, stderr = result.output

        # 如果执行失败，尝试自动安装缺失的包并重试
        if result.exit_code != 0 and stderr:
            stderr_text = stderr.decode()
            missing_module = _extract_missing_module(stderr_text)

            if missing_module:
                success, install_msg = await _try_install_missing_package(
                    pooled.container, missing_module, loop
                )
                if success:
                    logger.info(f"Retrying after installing {missing_module}")
                    result = await run_code()
                    stdout, stderr = result.output

        output_parts = []

        if stdout:
            output_parts.append(stdout.decode())
        if stderr:
            output_parts.append(f"[Stderr]: {stderr.decode()}")

        output = "\n".join(output_parts).strip()

        if result.exit_code != 0:
            return f"❌ 执行失败 (exit code {result.exit_code}):\n{output}"

        # 3. 如果需要输出文件，从容器复制
        if output_filename and host_output_dir and file_id:
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
                    return f"执行输出:\n{output}\n\n❌ 文件 /output/{output_filename} 未生成，请检查代码中的保存路径"
                return f"执行输出:\n{output}\n\n❌ 获取文件失败: {str(e)}"

            # 验证文件存在
            local_path = os.path.join(host_output_dir, output_filename)
            if not os.path.exists(local_path):
                return f"执行输出:\n{output}\n\n❌ 文件 {output_filename} 提取失败"

            # 从 tool_runtime 的 config 中获取 user_id
            user_id = None
            if tool_runtime and tool_runtime.config:
                user_id = tool_runtime.config.get("configurable", {}).get("user_id")

            # 注册文件到数据库
            if user_id:
                try:
                    from uuid import UUID
                    from backend.files import database as files_db

                    content_type, _ = mimetypes.guess_type(output_filename)
                    file_size = os.path.getsize(local_path)
                    await files_db.create_file(
                        user_id=UUID(user_id),
                        file_id=file_id,
                        original_name=output_filename,
                        content_type=content_type or "application/octet-stream",
                        size_bytes=file_size,
                        storage_path=local_path,
                    )
                    logger.info(f"Registered generated file: {file_id}/{output_filename}")
                except Exception as e:
                    logger.warning(f"Failed to register generated file: {e}")

            download_url = f"/api/files/{file_id}/{output_filename}"
            result_text = output if output else "执行完成"
            return f"{result_text}\n\n✅ 文件已生成\n\n[📥 点击下载 {output_filename}]({download_url})"

        return output if output else "代码执行成功 (exit_code=0)。提示：如需查看计算结果，请在代码中使用 print() 输出。"

    except Exception as e:
        return f"❌ 执行异常: {str(e)}"
    finally:
        # 只有使用旧版注入方式时才需要清理 /input/ 目录
        if use_legacy_injection:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: pooled.container.exec_run(["rm", "-rf", "/input/*"]),
                )
            except Exception as e:
                logger.warning(f"Failed to clean input dir: {e}")
        await pool.release(pooled)
