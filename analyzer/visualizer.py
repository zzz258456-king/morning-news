"""
数据可视化引擎
提供丰富的图表绘制功能，支持保存为图片和base64输出
"""
import io
import base64
import logging
from pathlib import Path
from typing import Optional, List, Union

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 非交互式后端，支持无GUI环境
import matplotlib.pyplot as plt
import seaborn as sns

from config import PROCESSED_DATA_DIR, DEFAULT_CHART_DPI, DEFAULT_CHART_FIGSIZE

logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_style("whitegrid")


class DataVisualizer:
    """
    数据可视化引擎
    支持多种图表类型，可输出为图片文件或base64字符串
    """

    def __init__(self, title: str = ""):
        self.title = title
        self.figsize = DEFAULT_CHART_FIGSIZE
        self.dpi = DEFAULT_CHART_DPI

    def _setup_plot(self, title: str = "", figsize: tuple = None):
        """初始化图表"""
        if figsize is None:
            figsize = self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        if title or self.title:
            ax.set_title(title or self.title, fontsize=14, pad=15)
        return fig, ax

    @staticmethod
    def _to_base64(fig) -> str:
        """将matplotlib图像转为base64"""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=DEFAULT_CHART_DPI, bbox_inches="tight")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"

    def _save_fig(self, fig, name: str) -> str:
        """保存图片到文件，返回路径"""
        output_path = PROCESSED_DATA_DIR / f"{name}.png"
        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"图表已保存: {output_path}")
        return str(output_path)

    # ==================== 基础图表 ====================

    def line_chart(self, data: pd.DataFrame, x: str, y: Union[str, List[str]],
                   title: str = "", output: str = "base64") -> Optional[str]:
        """折线图"""
        fig, ax = self._setup_plot(title)
        if isinstance(y, str):
            y = [y]
        for col in y:
            ax.plot(data[x], data[col], marker="o", label=col, linewidth=2)
        ax.set_xlabel(x)
        ax.legend()
        fig.tight_layout()
        return self._output(fig, "line_chart", output)

    def bar_chart(self, data: pd.DataFrame, x: str, y: str,
                  title: str = "", horizontal: bool = False,
                  output: str = "base64") -> Optional[str]:
        """柱状图 / 横向柱状图"""
        fig, ax = self._setup_plot(title)
        if horizontal:
            ax.barh(data[x], data[y], color="steelblue")
            ax.set_ylabel(x)
            ax.set_xlabel(y)
        else:
            ax.bar(data[x], data[y], color="steelblue")
            ax.set_xlabel(x)
            ax.set_ylabel(y)
        plt.xticks(rotation=45)
        fig.tight_layout()
        return self._output(fig, "bar_chart", output)

    def pie_chart(self, data: pd.Series, title: str = "",
                  output: str = "base64") -> Optional[str]:
        """饼图"""
        fig, ax = self._setup_plot(title)
        wedges, texts, autotexts = ax.pie(
            data.values, labels=data.index, autopct="%1.1f%%",
            startangle=90, pctdistance=0.85
        )
        ax.axis("equal")
        fig.tight_layout()
        return self._output(fig, "pie_chart", output)

    def histogram(self, data: pd.Series, bins: int = 20,
                  title: str = "", output: str = "base64") -> Optional[str]:
        """直方图"""
        fig, ax = self._setup_plot(title)
        ax.hist(data.dropna(), bins=bins, color="steelblue", edgecolor="white", alpha=0.7)
        ax.set_xlabel(data.name)
        ax.set_ylabel("频次")
        fig.tight_layout()
        return self._output(fig, "histogram", output)

    def scatter(self, data: pd.DataFrame, x: str, y: str,
                color_col: str = None, title: str = "",
                output: str = "base64") -> Optional[str]:
        """散点图"""
        fig, ax = self._setup_plot(title)
        scatter = ax.scatter(
            data[x], data[y],
            c=data[color_col] if color_col else "steelblue",
            alpha=0.6, cmap="viridis" if color_col else None
        )
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        if color_col:
            plt.colorbar(scatter, ax=ax, label=color_col)
        fig.tight_layout()
        return self._output(fig, "scatter", output)

    def correlation_heatmap(self, data: pd.DataFrame,
                            title: str = "相关系数热力图",
                            output: str = "base64") -> Optional[str]:
        """相关系数热力图"""
        fig, ax = self._setup_plot(title)
        corr = data.select_dtypes(include=[np.number]).corr()
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(
            corr, mask=mask, annot=True, fmt=".2f",
            cmap="RdBu_r", center=0, square=True,
            ax=ax, cbar_kws={"shrink": 0.8}
        )
        fig.tight_layout()
        return self._output(fig, "correlation_heatmap", output)

    def box_plot(self, data: pd.DataFrame, columns: List[str] = None,
                 title: str = "", output: str = "base64") -> Optional[str]:
        """箱线图"""
        if columns is None:
            columns = data.select_dtypes(include=[np.number]).columns.tolist()
        fig, ax = self._setup_plot(title)
        data[columns].boxplot(ax=ax)
        plt.xticks(rotation=45)
        fig.tight_layout()
        return self._output(fig, "box_plot", output)

    def _output(self, fig, name: str, output: str) -> Optional[str]:
        """统一输出处理"""
        if output == "base64":
            return self._to_base64(fig)
        elif output == "file":
            return self._save_fig(fig, name)
        elif output == "both":
            self._save_fig(fig, name)
            return self._to_base64(fig)
        else:
            plt.close(fig)
            return None

    def multi_plot(self, plots: List[dict]) -> str:
        """
        多图组合
        plots: [{"data": df, "type": "line", "x":..., "y":...}, ...]
        """
        n = len(plots)
        cols = min(3, n)
        rows = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
        if rows == 1:
            axes = [axes] if cols == 1 else axes
        else:
            axes = axes.flatten()

        for i, plot_spec in enumerate(plots):
            ax = axes[i]
            plot_type = plot_spec.get("type", "line")
            data = plot_spec.get("data", pd.DataFrame())

            if plot_type == "line" and "x" in plot_spec and "y" in plot_spec:
                y_cols = plot_spec["y"]
                if isinstance(y_cols, str):
                    y_cols = [y_cols]
                for yc in y_cols:
                    ax.plot(data[plot_spec["x"]], data[yc], marker="o", label=yc)
                ax.legend()
            elif plot_type == "bar" and "x" in plot_spec and "y" in plot_spec:
                ax.bar(data[plot_spec["x"]], data[plot_spec["y"]])
            elif plot_type == "hist" and "column" in plot_spec:
                ax.hist(data[plot_spec["column"]].dropna(), bins=20)

            ax.set_title(plot_spec.get("title", ""))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        for j in range(i + 1, len(axes)):
            axes[j].set_visible(False)

        fig.tight_layout()
        return self._to_base64(fig)
