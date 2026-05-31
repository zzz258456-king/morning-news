"""
数据处理与分析核心模块
提供数据加载、清洗、转换、统计分析功能
"""
import json
import logging
from pathlib import Path
from typing import Union, List, Optional, Any

import numpy as np
import pandas as pd

from config import RAW_DATA_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    数据处理引擎
    支持CSV/JSON/Excel数据加载、清洗、统计分析
    """

    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.source_name: str = ""

    # ==================== 数据加载 ====================

    def load_csv(self, path: Union[str, Path], **kwargs) -> pd.DataFrame:
        """从CSV文件加载数据"""
        path = Path(path)
        self.data = pd.read_csv(path, encoding=kwargs.pop("encoding", "utf-8-sig"), **kwargs)
        self.source_name = path.stem
        logger.info(f"加载CSV: {path} ({self.data.shape})")
        return self.data

    def load_json(self, path: Union[str, Path]) -> pd.DataFrame:
        """从JSON文件加载数据"""
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            self.data = pd.DataFrame(raw)
        elif isinstance(raw, dict):
            self.data = pd.DataFrame([raw])
        else:
            raise ValueError(f"不支持的JSON格式: {type(raw)}")
        self.source_name = path.stem
        logger.info(f"加载JSON: {path} ({self.data.shape})")
        return self.data

    def load_excel(self, path: Union[str, Path], sheet_name: str = 0) -> pd.DataFrame:
        """从Excel文件加载数据"""
        path = Path(path)
        self.data = pd.read_excel(path, sheet_name=sheet_name)
        self.source_name = path.stem
        logger.info(f"加载Excel: {path} ({self.data.shape})")
        return self.data

    def load_dataframe(self, df: pd.DataFrame, name: str = "dataframe"):
        """直接加载已有DataFrame"""
        self.data = df.copy()
        self.source_name = name
        return self.data

    def from_dict(self, data: List[dict]) -> pd.DataFrame:
        """从字典列表加载数据"""
        self.data = pd.DataFrame(data)
        self.source_name = "dict_data"
        return self.data

    # ==================== 数据清洗 ====================

    def clean(self) -> pd.DataFrame:
        """
        自动数据清洗
        处理缺失值、重复值、异常类型
        """
        if self.data is None:
            raise ValueError("请先加载数据")

        df = self.data.copy()
        initial_rows = len(df)

        # 1. 删除完全重复的行
        df = df.drop_duplicates()

        # 2. 删除全为空的行
        df = df.dropna(how="all")

        # 3. 自动识别并转换数值列
        for col in df.columns:
            df[col] = self._auto_convert_column(df[col])

        # 4. 填充数值列的缺失值（使用中位数）
        num_cols = df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            if df[col].isna().any():
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                logger.info(f"列 '{col}' 缺失值已用中位数 {median_val:.2f} 填充")

        # 5. 填充类别列的缺失值（使用众数）
        cat_cols = df.select_dtypes(include=["object", "category"]).columns
        for col in cat_cols:
            if df[col].isna().any():
                mode_val = df[col].mode()
                if not mode_val.empty:
                    df[col] = df[col].fillna(mode_val[0])

        removed = initial_rows - len(df)
        if removed > 0:
            logger.info(f"清洗完成: 删除了 {removed} 行数据")

        self.data = df
        return self.data

    @staticmethod
    def _auto_convert_column(series: pd.Series) -> pd.Series:
        """自动转换列的数据类型"""
        # 尝试转换为数值
        if series.dtype == object:
            try:
                converted = pd.to_numeric(series, errors="raise")
                return converted
            except (ValueError, TypeError):
                pass

            # 尝试解析日期
            try:
                converted = pd.to_datetime(series, errors="raise")
                return converted
            except (ValueError, TypeError):
                pass
        return series

    # ==================== 统计分析 ====================

    def describe(self) -> pd.DataFrame:
        """获取数据统计摘要"""
        if self.data is None:
            raise ValueError("请先加载数据")
        return self.data.describe(include="all")

    def summary(self) -> dict:
        """获取数据整体概况"""
        if self.data is None:
            return {"error": "请先加载数据"}

        info = {
            "名称": self.source_name,
            "行数": len(self.data),
            "列数": len(self.data.columns),
            "列名": list(self.data.columns),
            "内存占用": f"{self.data.memory_usage(deep=True).sum() / 1024:.1f} KB",
            "各列信息": {},
        }
        for col in self.data.columns:
            col_info = {
                "类型": str(self.data[col].dtype),
                "非空值": int(self.data[col].count()),
                "空值数": int(self.data[col].isna().sum()),
                "唯一值": self.data[col].nunique(),
            }
            if self.data[col].dtype in [np.int64, np.float64]:
                col_info.update({
                    "最小值": float(self.data[col].min()) if not self.data[col].isna().all() else None,
                    "最大值": float(self.data[col].max()) if not self.data[col].isna().all() else None,
                    "均值": float(self.data[col].mean()) if not self.data[col].isna().all() else None,
                    "中位数": float(self.data[col].median()) if not self.data[col].isna().all() else None,
                })
            info["各列信息"][col] = col_info
        return info

    def correlation(self, method: str = "pearson") -> pd.DataFrame:
        """计算数值列的相关系数矩阵"""
        if self.data is None:
            raise ValueError("请先加载数据")
        return self.data.select_dtypes(include=[np.number]).corr(method=method)

    def query(self, expr: str) -> pd.DataFrame:
        """使用表达式查询数据"""
        if self.data is None:
            raise ValueError("请先加载数据")
        try:
            return self.data.query(expr)
        except Exception as e:
            logger.error(f"查询失败: {expr} -> {e}")
            return pd.DataFrame()

    def group_and_aggregate(self, group_col: str, agg_col: str,
                            agg_func: Union[str, list] = "mean") -> pd.DataFrame:
        """分组聚合统计"""
        if self.data is None:
            raise ValueError("请先加载数据")
        if group_col not in self.data.columns or agg_col not in self.data.columns:
            raise ValueError(f"列不存在: {group_col} 或 {agg_col}")
        return self.data.groupby(group_col)[agg_col].agg(agg_func).reset_index()

    # ==================== 数据导出 ====================

    def export_csv(self, filename: str = None) -> str:
        """导出处理后的数据为CSV"""
        if self.data is None:
            raise ValueError("无数据可导出")
        if filename is None:
            filename = f"{self.source_name}_processed.csv"
        output_path = PROCESSED_DATA_DIR / filename
        self.data.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"数据已导出: {output_path}")
        return str(output_path)

    def export_json(self, filename: str = None) -> str:
        """导出为JSON"""
        if self.data is None:
            raise ValueError("无数据可导出")
        if filename is None:
            filename = f"{self.source_name}_processed.json"
        output_path = PROCESSED_DATA_DIR / filename
        output_path.write_text(
            self.data.to_json(orient="records", force_ascii=False),
            encoding="utf-8"
        )
        return str(output_path)
