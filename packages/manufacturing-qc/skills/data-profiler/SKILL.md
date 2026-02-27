---
name: data-profiler
description: 数据探查技能，分析数据结构并根据用户问题查找关键词
---

# 数据探查技能

## ⚠️ 强制约束 - 必须遵守

1. **必须执行 Python 代码** - 使用 execute_python_with_input 工具读取真实数据
2. **禁止虚构数据** - 所有列名、数据类型、示例值必须来自代码执行结果
3. **禁止假设** - 不要输出 "(假设)"、"(示例)" 等字样
4. **禁止模仿** - 不要复制下面示例中的列名，必须使用真实数据中的列名

## 执行步骤

### 步骤 1：读取数据并输出结构

复制以下代码，替换 `FILE_PATH` 为上下文中的容器路径，然后执行：

```python
import pandas as pd

# 替换为上下文中的实际容器路径
df = pd.read_csv('FILE_PATH')

print("## 数据概要\n")
print(f"- **文件**: {df.shape}")
print(f"- **行数**: {len(df)}")
print(f"- **列数**: {len(df.columns)}\n")

print("## 列信息\n")
print("| 列名 | 数据类型 | 空值率 | 示例值 |")
print("|------|---------|--------|--------|")
for col in df.columns:
    dtype = str(df[col].dtype)
    null_pct = f"{df[col].isnull().sum() / len(df) * 100:.1f}%"
    samples = ", ".join(str(v)[:20] for v in df[col].dropna().head(3))
    print(f"| {col} | {dtype} | {null_pct} | {samples} |")

print("\n## 日期/时间列\n")
for col in df.columns:
    if '日期' in col or '时间' in col or 'date' in col.lower() or 'time' in col.lower():
        try:
            dates = pd.to_datetime(df[col], errors='coerce')
            valid = dates.notna().sum()
            if valid > 0:
                print(f"- **{col}**: {dates.min()} 至 {dates.max()} ({valid} 条有效)")
        except:
            pass

print("\n## 数据样本（前3行）\n")
print(df.head(3).to_markdown())
```

### 步骤 2：关键词查找

根据用户问题提取关键词（公司名、年份、编码等），执行查找代码：

```python
# 替换为从用户问题中提取的关键词
keywords = ["关键词1", "关键词2"]

print("## 用户关键词查找\n")
for kw in keywords:
    print(f'### "{kw}" 在数据中的位置\n')
    for col in df.columns:
        if df[col].dtype == 'object':
            mask = df[col].astype(str).str.contains(kw, case=False, na=False)
            if mask.sum() > 0:
                samples = df.loc[mask, col].head(3).tolist()
                print(f"- **{col}**: {mask.sum()} 行匹配, 示例: {samples}")
    # 检查日期列的年份
    if kw.isdigit() and len(kw) == 4:
        for col in df.columns:
            if '日期' in col or '时间' in col:
                try:
                    dates = pd.to_datetime(df[col], errors='coerce')
                    mask = dates.dt.year == int(kw)
                    if mask.sum() > 0:
                        print(f"- **{col}** (日期列): {mask.sum()} 行匹配 {kw} 年")
                except:
                    pass
    print()
```

## 重要 - 文件路径

- 查看上下文中的 "可用文件" 部分
- 使用提供的 **容器路径** 读取文件（如 `/data/project_files/xxx/file.csv`）
- **不要使用** `/input/xxx.csv` 这样的硬编码路径
