---
name: data-visualization
description: 使用 Python（matplotlib、seaborn、plotly）创建有效的数据可视化。用于构建图表、为数据集选择合适的图表类型、创建出版级质量的图形，或应用可访问性和色彩理论等设计原则。
---

# 数据可视化技能

图表选择指南、Python 可视化代码模式、设计原则和无障碍考虑，用于创建有效的数据可视化。

## 图表选择指南

### 按数据关系选择

| 您要展示的内容 | 最佳图表 | 替代方案 |
|---|---|---|
| **时间趋势** | 折线图 | 面积图（显示累积或组成时） |
| **跨类别比较** | 垂直条形图 | 水平条形图（类别较多）、棒棒糖图 |
| **排名** | 水平条形图 | 点图、斜率图（比较两个时期） |
| **部分与整体的组成** | 堆叠条形图 | 树图（层次结构）、华夫饼图 |
| **随时间变化的组成** | 堆叠面积图 | 100% 堆叠条形图（关注比例时） |
| **分布** | 直方图 | 箱线图（比较组）、小提琴图、散点图 |
| **相关性（2 个变量）** | 散点图 | 气泡图（将第 3 个变量作为大小） |
| **相关性（多个变量）** | 热力图（相关矩阵） | 配对图 |
| **地理模式** | 分级统计图 | 气泡地图、六边形地图 |
| **流程 / 过程** | 桑基图 | 漏斗图（顺序阶段） |
| **关系网络** | 网络图 | 弦图 |
| **与目标的性能对比** | 子弹图 | 仪表盘（仅单个 KPI） |
| **一次显示多个 KPI** | 小多图 | 带有单独图表的仪表板 |

### 何时不使用某些图表

- **饼图**：除非类别 <6 个且精确比例不如粗略比较重要，否则避免使用。人类不擅长比较角度。改用条形图。
- **3D 图表**：永远不要使用。它们会扭曲感知且不增加任何信息。
- **双轴图表**：谨慎使用。它们可能通过暗示相关性来误导。如果使用，请清楚标记两个轴。
- **堆叠条形图（多类别）**：中间部分难以比较。改用小多图或分组条形图。
- **环形图**：比饼图略好，但存在相同的基本问题。最多用于单个 KPI 显示。

## Python 可视化代码模式

### 设置和样式

```python
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd
import numpy as np

# 专业样式设置
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'figure.figsize': (10, 6),
    'figure.dpi': 150,
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 16,
})

# 色盲友好调色板
PALETTE_CATEGORICAL = ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B3', '#937860']
PALETTE_SEQUENTIAL = 'YlOrRd'
PALETTE_DIVERGING = 'RdBu_r'
```

### 折线图（时间序列）

```python
fig, ax = plt.subplots(figsize=(10, 6))

for label, group in df.groupby('category'):
    ax.plot(group['date'], group['value'], label=label, linewidth=2)

ax.set_title('按类别的指标趋势', fontweight='bold')
ax.set_xlabel('日期')
ax.set_ylabel('值')
ax.legend(loc='upper left', frameon=True)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# 格式化 x 轴日期
fig.autofmt_xdate()

plt.tight_layout()
plt.savefig('trend_chart.png', dpi=150, bbox_inches='tight')
```

### 条形图（比较）

```python
fig, ax = plt.subplots(figsize=(10, 6))

# 按值排序以便阅读
df_sorted = df.sort_values('metric', ascending=True)

bars = ax.barh(df_sorted['category'], df_sorted['metric'], color=PALETTE_CATEGORICAL[0])

# 添加值标签
for bar in bars:
    width = bar.get_width()
    ax.text(width + 0.5, bar.get_y() + bar.get_height()/2,
            f'{width:,.0f}', ha='left', va='center', fontsize=10)

ax.set_title('按类别的指标（排名）', fontweight='bold')
ax.set_xlabel('指标值')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('bar_chart.png', dpi=150, bbox_inches='tight')
```

### 直方图（分布）

```python
fig, ax = plt.subplots(figsize=(10, 6))

ax.hist(df['value'], bins=30, color=PALETTE_CATEGORICAL[0], edgecolor='white', alpha=0.8)

# 添加均值和中位数线
mean_val = df['value'].mean()
median_val = df['value'].median()
ax.axvline(mean_val, color='red', linestyle='--', linewidth=1.5, label=f'均值: {mean_val:,.1f}')
ax.axvline(median_val, color='green', linestyle='--', linewidth=1.5, label=f'中位数: {median_val:,.1f}')

ax.set_title('值的分布', fontweight='bold')
ax.set_xlabel('值')
ax.set_ylabel('频率')
ax.legend()
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('histogram.png', dpi=150, bbox_inches='tight')
```

### 热力图

```python
fig, ax = plt.subplots(figsize=(10, 8))

# 为热力图格式化数据透视
pivot = df.pivot_table(index='row_dim', columns='col_dim', values='metric', aggfunc='sum')

sns.heatmap(pivot, annot=True, fmt=',.0f', cmap='YlOrRd',
            linewidths=0.5, ax=ax, cbar_kws={'label': '指标值'})

ax.set_title('按行维度和列维度的指标', fontweight='bold')
ax.set_xlabel('列维度')
ax.set_ylabel('行维度')

plt.tight_layout()
plt.savefig('heatmap.png', dpi=150, bbox_inches='tight')
```

### 小多图

```python
categories = df['category'].unique()
n_cats = len(categories)
n_cols = min(3, n_cats)
n_rows = (n_cats + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 4*n_rows), sharex=True, sharey=True)
axes = axes.flatten() if n_cats > 1 else [axes]

for i, cat in enumerate(categories):
    ax = axes[i]
    subset = df[df['category'] == cat]
    ax.plot(subset['date'], subset['value'], color=PALETTE_CATEGORICAL[i % len(PALETTE_CATEGORICAL)])
    ax.set_title(cat, fontsize=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

# 隐藏空的子图
for j in range(i+1, len(axes)):
    axes[j].set_visible(False)

fig.suptitle('按类别的趋势', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('small_multiples.png', dpi=150, bbox_inches='tight')
```

### 数字格式化辅助函数

```python
def format_number(val, format_type='number'):
    """格式化图表标签的数字。"""
    if format_type == 'currency':
        if abs(val) >= 1e9:
            return f'${val/1e9:.1f}B'
        elif abs(val) >= 1e6:
            return f'${val/1e6:.1f}M'
        elif abs(val) >= 1e3:
            return f'${val/1e3:.1f}K'
        else:
            return f'${val:,.0f}'
    elif format_type == 'percent':
        return f'{val:.1f}%'
    elif format_type == 'number':
        if abs(val) >= 1e9:
            return f'{val/1e9:.1f}B'
        elif abs(val) >= 1e6:
            return f'{val/1e6:.1f}M'
        elif abs(val) >= 1e3:
            return f'{val/1e3:.1f}K'
        else:
            return f'{val:,.0f}'
    return str(val)

# 与轴格式化器一起使用
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: format_number(x, 'currency')))
```

### 使用 Plotly 的交互式图表

```python
import plotly.express as px
import plotly.graph_objects as go

# 简单的交互式折线图
fig = px.line(df, x='date', y='value', color='category',
              title='交互式指标趋势',
              labels={'value': '指标值', 'date': '日期'})
fig.update_layout(hovermode='x unified')
fig.write_html('interactive_chart.html')
fig.show()

# 带悬停数据的交互式散点图
fig = px.scatter(df, x='metric_a', y='metric_b', color='category',
                 size='size_metric', hover_data=['name', 'detail_field'],
                 title='相关性分析')
fig.show()
```

## 设计原则

### 颜色

- **有目的地使用颜色**：颜色应该编码数据，而不是装饰
- **突出重点**：对关键洞察使用明亮的强调色；其他都用灰色
- **顺序数据**：对有序值使用单色渐变（从浅到深）
- **发散数据**：对具有有意义中心的数据使用双色渐变，中间为中性色
- **分类数据**：使用不同的色调，最多 6-8 种，否则会令人困惑
- **避免仅使用红/绿**：8% 的男性是红绿色盲。使用蓝/橙作为主要配对

### 排版

- **标题陈述洞察**："收入同比增长 23%" 优于 "按月收入"
- **副标题添加上下文**：日期范围、应用的筛选器、数据来源
- **轴标签可读**：如果可以避免，永远不要旋转 90 度。改为缩短或换行
- **数据标签增加精度**：用于关键点，而不是每个条形
- **注释突出**：用文字注释标注特定点

### 布局

- **减少图表垃圾**：删除不承载信息的网格线、边框、背景
- **有意义地排序**：类别按值排序（而不是按字母顺序），除非有自然顺序（月份、阶段）
- **适当的宽高比**：时间序列比高度宽（3:1 到 2:1）；比较可以更方正
- **留白很好**：不要把图表挤在一起。给每个可视化留出呼吸空间

### 准确性

- **条形图从零开始**：始终如此。从 95 到 100 的条形会夸大 5% 的差异
- **折线图可以有非零基线**：当变化范围有意义时
- **面板间比例一致**：比较多个图表时，使用相同的轴范围
- **显示不确定性**：当数据不确定时，使用误差条、置信区间或范围
- **标记您的轴**：永远不要让读者猜测数字代表什么

## 无障碍考虑

### 色盲

- 永远不要仅依靠颜色来区分数据系列
- 添加图案填充、不同的线条样式（实线、虚线、点线）或直接标签
- 使用色盲模拟器测试（如 Coblis、Sim Daltonism）
- 使用色盲友好调色板：`sns.color_palette("colorblind")`

### 屏幕阅读器

- 包含描述图表关键发现的替代文本
- 在可视化旁边提供数据表替代
- 使用语义化标题和标签

### 一般无障碍

- 数据元素与背景之间有足够的对比度
- 标签最小字号 10pt，标题 12pt
- 避免仅通过空间位置传达信息（添加标签）
- 考虑打印：图表在黑白下是否有效？

### 无障碍检查清单

分享可视化之前：
- [ ] 图表在没有颜色的情况下有效（图案、标签或线条样式区分系列）
- [ ] 文本在标准缩放级别下可读
- [ ] 标题描述洞察，而不仅仅是数据
- [ ] 轴标有单位
- [ ] 图例清晰且不遮挡数据
- [ ] 注明数据来源和日期范围
