"""
Data Profiler Agent - 数据探查Agent
负责分析数据结构、字段类型、值分布等
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.factory import BaseLLM
from prompts.templates import (
    DATA_PROFILER_SYSTEM, 
    DATA_PROFILER_PROMPT,
    format_columns_info,
    format_sample_data
)


class DataProfilerAgent:
    """数据探查Agent"""
    
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.name = "DataProfiler"
    
    def profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析DataFrame并生成数据概要
        
        Args:
            df: pandas DataFrame
        
        Returns:
            数据概要字典
        """
        # 基本信息
        row_count = len(df)
        column_count = len(df.columns)
        
        # 分析每一列
        columns_info = []
        for col in df.columns:
            col_info = self._analyze_column(df, col)
            columns_info.append(col_info)
        
        # 获取样本数据
        sample_data = df.head(5).to_dict('records')
        
        # 使用LLM生成描述
        summary = self._generate_summary(row_count, column_count, columns_info, sample_data)
        
        return {
            "row_count": row_count,
            "column_count": column_count,
            "columns": columns_info,
            "sample_data": sample_data,
            "summary": summary
        }
    
    def _analyze_column(self, df: pd.DataFrame, col: str) -> Dict[str, Any]:
        """分析单个列"""
        series = df[col]
        dtype = str(series.dtype)
        
        # 基本统计
        non_null = series.count()
        null_count = series.isna().sum()
        null_pct = null_count / len(df) * 100 if len(df) > 0 else 0
        unique_count = series.nunique()
        
        col_info = {
            "name": col,
            "dtype": dtype,
            "non_null_count": int(non_null),
            "null_count": int(null_count),
            "null_percentage": round(null_pct, 2),
            "unique_count": int(unique_count),
            "sample_values": [],
            "value_distribution": None,
            "statistics": None
        }
        
        # 样本值
        non_null_values = series.dropna()
        if len(non_null_values) > 0:
            col_info["sample_values"] = [
                self._safe_value(v) for v in non_null_values.head(5).tolist()
            ]
        
        # 数值类型的统计信息
        if np.issubdtype(series.dtype, np.number):
            col_info["statistics"] = {
                "min": self._safe_value(series.min()),
                "max": self._safe_value(series.max()),
                "mean": self._safe_value(series.mean()),
                "median": self._safe_value(series.median()),
                "std": self._safe_value(series.std())
            }
        
        # 分类变量的分布（唯一值少于20个）
        if unique_count <= 20 and unique_count > 0:
            value_counts = series.value_counts().head(10)
            col_info["value_distribution"] = {
                self._safe_value(k): int(v) for k, v in value_counts.items()
            }
        
        # 检测时间类型
        if dtype == 'object' and len(non_null_values) > 0:
            sample = non_null_values.iloc[0]
            if self._is_datetime_like(sample):
                col_info["dtype"] = "datetime-like"
        
        return col_info
    
    def _safe_value(self, value) -> Any:
        """安全转换值，处理NaN等特殊值"""
        if pd.isna(value):
            return None
        if isinstance(value, (np.integer, np.int64)):
            return int(value)
        if isinstance(value, (np.floating, np.float64)):
            if np.isnan(value) or np.isinf(value):
                return None
            return round(float(value), 4)
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, pd.Timestamp):
            return str(value)
        return str(value) if not isinstance(value, (str, int, float, bool)) else value
    
    def _is_datetime_like(self, value) -> bool:
        """检测是否像日期时间"""
        if not isinstance(value, str):
            return False
        import re
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{4}/\d{2}/\d{2}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{2}/\d{2}/\d{4}',
        ]
        return any(re.search(p, str(value)) for p in date_patterns)
    
    def _generate_summary(self, row_count: int, column_count: int, 
                         columns_info: List[Dict], sample_data: List[Dict]) -> str:
        """使用LLM生成数据概要描述"""
        
        columns_text = format_columns_info(columns_info)
        sample_text = format_sample_data(sample_data)
        
        prompt = DATA_PROFILER_PROMPT.format(
            row_count=row_count,
            column_count=column_count,
            columns_info=columns_text,
            sample_data=sample_text
        )
        
        try:
            summary = self.llm.invoke(prompt, DATA_PROFILER_SYSTEM)
            return summary
        except Exception as e:
            # 降级到基本描述
            return f"数据集包含{row_count}行、{column_count}列。"
    
    def get_profile_text(self, profile: Dict) -> str:
        """获取用于其他Agent的概要文本"""
        lines = []
        lines.append(f"数据集: {profile['row_count']}行 x {profile['column_count']}列")
        lines.append("")
        lines.append("## 列信息")
        lines.append(format_columns_info(profile['columns']))
        lines.append("")
        lines.append("## 数据概要")
        lines.append(profile['summary'])
        return "\n".join(lines)


def create_data_profiler(llm: BaseLLM) -> DataProfilerAgent:
    """创建数据探查Agent"""
    return DataProfilerAgent(llm)
