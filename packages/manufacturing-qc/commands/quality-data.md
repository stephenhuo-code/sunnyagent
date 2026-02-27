---
description: 分析质量数据并生成可视化图表
allowed-tools: Read, Write, Edit, Bash(python3:*, pip:*)
argument-hint: [数据文件路径]
---

对质量数据进行统计分析，生成专业的质量分析图表和报告。

## 执行步骤

1. 读取用户提供的数据文件（支持 CSV、Excel、TXT 等格式）

2. 数据预处理：
   - 检查数据完整性和格式
   - 识别异常值和缺失值
   - 确认数据类型（计量型/计数型）
   - 确认关键字段（日期、批次、测量值、规格限等）

3. 询问用户分析目标（如未明确指定）：
   - 过程能力分析（Cp/Cpk/Pp/Ppk）
   - 控制图分析（SPC）
   - 缺陷帕累托分析
   - 不良率趋势分析
   - 供应商质量对比
   - 其他自定义分析

4. 执行统计分析：

   **计量型数据分析：**
   - 描述性统计（均值、标准差、最大/最小值、中位数）
   - 正态性检验
   - 过程能力指数计算（参考 quality-analysis 技能的公式）
   - 控制图绘制（X̄-R / I-MR）
   - 直方图（含规格限和正态分布拟合）

   **计数型数据分析：**
   - 不合格率统计
   - 帕累托图
   - p 控制图 / c 控制图
   - 趋势分析

5. 使用 Python（matplotlib/pandas）生成图表：
   - 确保安装必要的库：`pip install matplotlib pandas openpyxl numpy scipy --break-system-packages`
   - 图表使用中文字体显示
   - 图表包含标题、轴标签、图例
   - 控制图标注控制限（UCL/CL/LCL）和规格限（USL/LSL）
   - 异常点使用红色标注

6. 生成分析报告，包含：
   - 数据概要
   - 统计分析结果
   - 图表
   - 过程能力评价
   - 异常点识别和可能原因
   - 改善建议

7. 将报告和图表保存输出

## 图表设置

生成 Python 图表时使用以下配置确保中文显示：
```python
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
```

## 注意事项

- 数据量较大时优先使用 pandas 进行批量处理
- 控制图至少需要 20-25 个数据点才有统计意义
- 过程能力分析前应先确认过程处于统计受控状态
- 自动标注超出控制限的异常数据点
- 建议同时提供数据表格和图表两种呈现方式
