# 数据探查 - 一体化脚本
# 用法：替换 FILE_PATH 和 KEYWORDS 后执行

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

# ========== 配置参数（执行前必须替换） ==========
FILE_PATH = 'FILE_PATH'  # 替换为实际容器路径，如 '/data/project_files/xxx/file.csv'
KEYWORDS = []  # 替换为用户问题中的关键词列表，如 ['小米', '2025年11月']

# ========== 参数验证 ==========
if FILE_PATH == 'FILE_PATH':
    print("❌ 错误：FILE_PATH 未被替换为实际路径")
    print("请将 FILE_PATH = 'FILE_PATH' 改为实际的文件路径")
    exit(1)

# ========== 读取数据 ==========
try:
    df = pd.read_csv(FILE_PATH)
    print(f"✅ 成功读取文件：{len(df)} 行, {len(df.columns)} 列\n")
except Exception as e:
    print(f"❌ 读取文件失败：{e}")
    exit(1)

# ========== 第一阶段：数据集概要 ==========
print("=" * 60)
print("## 1. 数据集概要")
print("=" * 60)
print(f"- **行数**: {len(df)}")
print(f"- **列数**: {len(df.columns)}")
print(f"- **内存占用**: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
print(f"- **列名**: {list(df.columns)}\n")

# 列分类
dimensions = []  # 维度列（分类变量）
metrics = []     # 指标列（数值变量）
time_cols = []   # 时间列
text_cols = []   # 文本列

for col in df.columns:
    try:
        series = df[col]

        # 检测时间列 - 通过内容
        if series.dtype == 'object' and len(series.dropna()) > 0:
            sample = str(series.dropna().iloc[0])
            if re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', sample):
                time_cols.append(col)
                continue

        # 检测时间列 - 通过列名
        if any(kw in col.lower() for kw in ['日期', '时间', 'date', 'time', 'year', 'month']):
            time_cols.append(col)
            continue

        # 数值列 → 指标
        if np.issubdtype(series.dtype, np.number):
            metrics.append(col)
        # 分类变量（低基数）→ 维度
        elif series.nunique() <= 50:
            dimensions.append(col)
        # 高基数文本 → 文本列
        else:
            text_cols.append(col)
    except Exception as e:
        print(f"- ⚠️ 列 '{col}' 分类失败: {e}")

print("**列分类结果**:")
print(f"- **维度列** ({len(dimensions)}): {dimensions}")
print(f"- **指标列** ({len(metrics)}): {metrics}")
print(f"- **时间列** ({len(time_cols)}): {time_cols}")
print(f"- **文本列** ({len(text_cols)}): {text_cols}\n")

# ========== 第二阶段：关键列分析 ==========
print("=" * 60)
print("## 2. 关键列分析")
print("=" * 60)

# 优先分析维度列和时间列（与用户问题最相关）
key_cols = dimensions + time_cols
for col in key_cols[:15]:  # 最多分析15列
    try:
        series = df[col]
        null_count = series.isna().sum()
        null_pct = null_count / len(df) * 100 if len(df) > 0 else 0
        unique_count = series.nunique()

        print(f"\n### {col}")
        print(f"- **类型**: {series.dtype}")
        print(f"- **空值**: {null_count} ({null_pct:.1f}%)")
        print(f"- **唯一值**: {unique_count}")

        # 值分布（低基数列）
        if unique_count <= 20 and unique_count > 0:
            value_counts = series.value_counts().head(10)
            dist = {str(k): int(v) for k, v in value_counts.items()}
            print(f"- **值分布**: {dist}")

        # 日期范围检测
        if series.dtype == 'object':
            non_null = series.dropna()
            if len(non_null) > 0:
                sample = str(non_null.iloc[0])
                if re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', sample):
                    dates = pd.to_datetime(series, errors='coerce')
                    valid_dates = dates.dropna()
                    if len(valid_dates) > 0:
                        print(f"- **日期范围**: {valid_dates.min()} 至 {valid_dates.max()}")
    except Exception as e:
        print(f"\n### {col}")
        print(f"- ❌ 分析失败: {e}")

# 分析指标列（数值统计）
for col in metrics[:10]:  # 最多分析10个指标列
    try:
        series = df[col]
        null_count = series.isna().sum()
        null_pct = null_count / len(df) * 100 if len(df) > 0 else 0

        print(f"\n### {col}")
        print(f"- **类型**: {series.dtype}")
        print(f"- **空值**: {null_count} ({null_pct:.1f}%)")

        non_null = series.dropna()
        if len(non_null) > 0:
            stats = [
                f"min={non_null.min():.2f}",
                f"max={non_null.max():.2f}",
                f"mean={non_null.mean():.2f}",
                f"median={non_null.median():.2f}"
            ]
            if len(non_null) > 1:
                stats.append(f"std={non_null.std():.2f}")
            print(f"- **统计**: {', '.join(stats)}")
    except Exception as e:
        print(f"\n### {col}")
        print(f"- ❌ 分析失败: {e}")

print()

# ========== 第三阶段：数据样本 ==========
print("=" * 60)
print("## 3. 数据样本（前5行）")
print("=" * 60)
print(df.head(5).to_markdown(index=False))
print()

# ========== 第四阶段：关键词匹配 ==========
if KEYWORDS and len(KEYWORDS) > 0 and KEYWORDS != ["关键词1", "关键词2"]:
    print("=" * 60)
    print("## 4. 关键词匹配结果")
    print("=" * 60)

    for kw in KEYWORDS:
        print(f'\n### 关键词: "{kw}"')
        found = False

        # 搜索所有列，不限 dtype
        for col in df.columns:
            try:
                col_str = df[col].astype(str)
                mask = col_str.str.contains(kw, case=False, na=False)
                if mask.sum() > 0:
                    samples = df.loc[mask, col].head(3).tolist()
                    print(f"- **{col}**: {mask.sum()} 行匹配")
                    print(f"  示例值: {samples}")
                    found = True
            except Exception:
                continue

        # 年份特殊处理
        if kw.isdigit() and len(kw) == 4:
            for col in df.columns:
                if '日期' in col or '时间' in col or 'date' in col.lower():
                    try:
                        dates = pd.to_datetime(df[col], errors='coerce')
                        mask = dates.dt.year == int(kw)
                        if mask.sum() > 0:
                            print(f"- **{col}** (日期列): {mask.sum()} 行属于 {kw} 年")
                            found = True
                    except Exception:
                        continue

        # 年月格式处理，如 "2025年11月"
        year_month_match = re.match(r'(\d{4})年(\d{1,2})月', kw)
        if year_month_match:
            year, month = int(year_month_match.group(1)), int(year_month_match.group(2))
            for col in df.columns:
                if '日期' in col or '时间' in col or 'date' in col.lower():
                    try:
                        dates = pd.to_datetime(df[col], errors='coerce')
                        mask = (dates.dt.year == year) & (dates.dt.month == month)
                        if mask.sum() > 0:
                            print(f"- **{col}** (日期列): {mask.sum()} 行属于 {year}年{month}月")
                            found = True
                    except Exception:
                        continue

        if not found:
            print(f"- ⚠️ 未找到匹配数据")

    print()
else:
    print("=" * 60)
    print("## 4. 关键词匹配")
    print("=" * 60)
    print("- 未提供关键词，跳过关键词匹配阶段")
    print("- 如需查找特定数据，请在 KEYWORDS 列表中添加关键词")
    print()

print("=" * 60)
print("✅ 数据探查完成")
print("=" * 60)
