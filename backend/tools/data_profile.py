"""数据探查工具 - 分析 CSV 文件的数据结构、统计信息、值分布"""

import asyncio
import logging
from pathlib import Path

from langchain_core.tools import tool

from .container_pool import get_pool

logger = logging.getLogger(__name__)

# 数据探查脚本模板（基于 profile_all.py）
_PROFILE_SCRIPT = '''\
# 数据探查脚本 - 自动生成
# 确保 tabulate 可用（pandas to_markdown 依赖）
try:
    import tabulate
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'tabulate', '-q'])
    import tabulate

import pandas as pd
import numpy as np
import re

# ========== 配置参数 ==========
FILE_PATH = {file_path!r}
KEYWORDS = {keywords!r}

# ========== 读取数据 ==========
try:
    df = pd.read_csv(FILE_PATH)
    print(f"✅ 成功读取文件：{{len(df)}} 行, {{len(df.columns)}} 列\\n")
except Exception as e:
    print(f"❌ 读取文件失败：{{e}}")
    exit(1)

# ========== 第一阶段：数据集概要 ==========
print("=" * 60)
print("## 1. 数据集概要")
print("=" * 60)
print(f"- **行数**: {{len(df)}}")
print(f"- **列数**: {{len(df.columns)}}")
print(f"- **内存占用**: {{df.memory_usage(deep=True).sum() / 1024:.1f}} KB")
print(f"- **列名**: {{list(df.columns)}}\\n")

# 列分类
dimensions, metrics, time_cols, text_cols = [], [], [], []

for col in df.columns:
    try:
        series = df[col]
        if series.dtype == 'object' and len(series.dropna()) > 0:
            sample = str(series.dropna().iloc[0])
            if re.search(r'\\d{{4}}[-/]\\d{{2}}[-/]\\d{{2}}', sample):
                time_cols.append(col)
                continue
        if any(kw in col.lower() for kw in ['日期', '时间', 'date', 'time', 'year', 'month']):
            time_cols.append(col)
            continue
        if np.issubdtype(series.dtype, np.number):
            metrics.append(col)
        elif series.nunique() <= 50:
            dimensions.append(col)
        else:
            text_cols.append(col)
    except Exception as e:
        print(f"- ⚠️ 列 '{{col}}' 分类失败: {{e}}")

print("**列分类结果**:")
print(f"- **维度列** ({{len(dimensions)}}): {{dimensions}}")
print(f"- **指标列** ({{len(metrics)}}): {{metrics}}")
print(f"- **时间列** ({{len(time_cols)}}): {{time_cols}}")
print(f"- **文本列** ({{len(text_cols)}}): {{text_cols}}\\n")

# ========== 第二阶段：关键列分析 ==========
print("=" * 60)
print("## 2. 关键列分析")
print("=" * 60)

key_cols = dimensions + time_cols
for col in key_cols[:15]:
    try:
        series = df[col]
        null_pct = series.isna().sum() / len(df) * 100 if len(df) > 0 else 0
        unique_count = series.nunique()
        print(f"\\n### {{col}}")
        print(f"- **类型**: {{series.dtype}}, **空值**: {{null_pct:.1f}}%, **唯一值**: {{unique_count}}")
        if unique_count <= 20 and unique_count > 0:
            dist = {{str(k): int(v) for k, v in series.value_counts().head(10).items()}}
            print(f"- **值分布**: {{dist}}")
        if series.dtype == 'object' and len(series.dropna()) > 0:
            sample = str(series.dropna().iloc[0])
            if re.search(r'\\d{{4}}[-/]\\d{{2}}[-/]\\d{{2}}', sample):
                dates = pd.to_datetime(series, errors='coerce').dropna()
                if len(dates) > 0:
                    print(f"- **日期范围**: {{dates.min()}} 至 {{dates.max()}}")
    except Exception as e:
        print(f"\\n### {{col}}\\n- ❌ 分析失败: {{e}}")

for col in metrics[:10]:
    try:
        series = df[col]
        null_pct = series.isna().sum() / len(df) * 100 if len(df) > 0 else 0
        non_null = series.dropna()
        print(f"\\n### {{col}}")
        print(f"- **类型**: {{series.dtype}}, **空值**: {{null_pct:.1f}}%")
        if len(non_null) > 0:
            stats = f"min={{non_null.min():.2f}}, max={{non_null.max():.2f}}, mean={{non_null.mean():.2f}}"
            print(f"- **统计**: {{stats}}")
    except Exception as e:
        print(f"\\n### {{col}}\\n- ❌ 分析失败: {{e}}")

print()

# ========== 第三阶段：数据样本 ==========
print("=" * 60)
print("## 3. 数据样本（前5行）")
print("=" * 60)
print(df.head(5).to_markdown(index=False))
print()

# ========== 第四阶段：关键词匹配 ==========
print("=" * 60)
print("## 4. 关键词匹配结果")
print("=" * 60)

if KEYWORDS:
    for kw in KEYWORDS:
        print(f'\\n### 关键词: "{{kw}}"')
        found = False
        # 搜索所有列，不限 dtype
        for col in df.columns:
            try:
                col_str = df[col].astype(str)
                mask = col_str.str.contains(kw, case=False, na=False)
                if mask.sum() > 0:
                    samples = df.loc[mask, col].head(3).tolist()
                    print(f"- **{{col}}**: {{mask.sum()}} 行匹配, 示例: {{samples}}")
                    found = True
            except Exception:
                continue
        # 年份处理
        if kw.isdigit() and len(kw) == 4:
            for col in df.columns:
                if '日期' in col or '时间' in col or 'date' in col.lower():
                    try:
                        dates = pd.to_datetime(df[col], errors='coerce')
                        mask = dates.dt.year == int(kw)
                        if mask.sum() > 0:
                            print(f"- **{{col}}** (日期列): {{mask.sum()}} 行属于 {{kw}} 年")
                            found = True
                    except Exception:
                        continue
        # 年月格式处理
        year_month_match = re.match(r'(\\d{{4}})年(\\d{{1,2}})月', kw)
        if year_month_match:
            year, month = int(year_month_match.group(1)), int(year_month_match.group(2))
            for col in df.columns:
                if '日期' in col or '时间' in col or 'date' in col.lower():
                    try:
                        dates = pd.to_datetime(df[col], errors='coerce')
                        mask = (dates.dt.year == year) & (dates.dt.month == month)
                        if mask.sum() > 0:
                            print(f"- **{{col}}** (日期列): {{mask.sum()}} 行属于 {{year}}年{{month}}月")
                            found = True
                    except Exception:
                        continue
        if not found:
            print(f"- ⚠️ 未找到匹配数据")
else:
    print("\\n- 未提供关键词，跳过关键词匹配")

print()
print("=" * 60)
print("✅ 数据探查完成")
print("=" * 60)
'''


def _host_path_to_container_path(host_path: str) -> str | None:
    """将主机路径转换为容器内路径。

    主机路径:    /Users/.../data/project_files/abc123/file.csv
    容器内路径:  /data/project_files/abc123/file.csv
    """
    from backend.core.storage import get_project_files_dir, get_temp_files_dir

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

    # 如果已经是容器路径格式，直接返回
    if host_path.startswith("/data/"):
        return host_path

    return None


@tool
async def data_profile(
    file_path: str,
    keywords: list[str] | None = None,
) -> str:
    """
    数据探查工具 - 分析 CSV 文件的数据结构、统计信息、值分布。

    此工具会自动执行完整的数据探查，包括：
    - 数据集概要（行数、列数、内存占用）
    - 列分类（维度、指标、时间、文本）
    - 关键列分析（空值率、唯一值、值分布）
    - 数据样本（前5行）
    - 关键词匹配结果

    Args:
        file_path: 文件路径，支持以下格式：
            - 容器路径：/data/project_files/xxx/file.csv
            - 主机路径：/Users/.../data/project_files/xxx/file.csv
        keywords: 要搜索的关键词列表，如 ['小米', '2025年11月']
            注意：时间词需要转换为具体值，如"今年"→"2026年"

    Returns:
        探查结果，包含数据概要、列分析、样本、关键词匹配
        成功时会包含 "✅ 数据探查完成" 标记
    """
    # 转换路径为容器路径
    container_path = _host_path_to_container_path(file_path)
    if not container_path:
        return f"❌ 无法识别文件路径: {file_path}\n请使用上下文中 [可用文件] 部分的容器路径"

    # 验证主机文件是否存在（如果是主机路径）
    if not file_path.startswith("/data/"):
        if not Path(file_path).exists():
            return f"❌ 文件不存在: {file_path}"

    # 准备关键词
    kw_list = keywords or []

    # 生成探查脚本
    code = _PROFILE_SCRIPT.format(
        file_path=container_path,
        keywords=kw_list,
    )

    logger.info(f"[data_profile] Executing profile for: {container_path}, keywords={kw_list}")

    # 在容器中执行
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
            stderr_text = stderr.decode()
            # 只显示非空的 stderr
            if stderr_text.strip():
                output_parts.append(f"[Stderr]: {stderr_text}")

        output = "\n".join(output_parts).strip()

        if result.exit_code != 0:
            return f"❌ 数据探查失败 (exit code {result.exit_code}):\n{output}"

        return output if output else "❌ 数据探查未产生输出"

    except Exception as e:
        logger.exception(f"[data_profile] Error: {e}")
        return f"❌ 数据探查异常: {str(e)}"
    finally:
        await pool.release(pooled)
