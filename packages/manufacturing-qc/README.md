# Manufacturing QC — 制造业质量保障插件

为制造业质量保障工作人员提供全流程质检支持工具，覆盖来料检验（IQC）、过程检验（IPQC）、成品检验（FQC）、出货检验（OQC）等关键环节。

## 功能概览

### 快捷命令

| 命令 | 功能 |
|------|------|
| `/inspection-report` | 生成标准化质检报告（IQC/IPQC/FQC/OQC） |
| `/8d-report` | 按 8D 方法论生成质量问题分析报告 |
| `/write-sop` | 编写或优化质检标准作业程序 |
| `/complaint-analysis` | 分析客户投诉，追溯原因并提出改善措施 |
| `/quality-data` | 对质量数据进行统计分析和可视化 |

### 知识技能

| 技能 | 说明 |
|------|------|
| quality-inspection | 质检领域知识库：ISO 9001 体系要求、检验标准、AQL 抽样方案、缺陷分类等 |
| quality-analysis | 统计质量分析知识：SPC 控制图、过程能力分析、8D 方法论、FMEA、MSA 等 |

## 使用示例

**生成来料检验报告：**
> /inspection-report IQC — 电阻 R001，供应商 XX，AQL 1.0，批量 5000

**分析质量数据：**
> /quality-data 附上 CSV 数据文件，分析 CPK 和控制图

**编写检验 SOP：**
> /write-sop 外观检验 — 手机壳注塑件

**处理客户投诉：**
> /complaint-analysis 客户反馈产品尺寸超差，批次号 LOT20260220

**生成 8D 报告：**
> /8d-report 焊接工序出现虚焊问题，影响 3 个批次

## 支持的质量标准

- ISO 9001:2015 质量管理体系
- GB/T 2828.1 (ISO 2859-1) 计数型抽样检验

## 系统集成

当前版本为独立使用，后续可扩展对接 ERP/MES/QMS 系统。
