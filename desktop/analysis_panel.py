"""
数据分析面板 - 桌面版
提供数据加载、清洗、可视化预览等功能
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QGroupBox,
    QSplitter, QHeaderView, QFileDialog, QMessageBox,
    QComboBox, QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
import matplotlib
matplotlib.use("Agg")

from analyzer import DataProcessor, DataVisualizer

logger = logging.getLogger(__name__)


class AnalysisPanel(QWidget):
    """数据分析面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processor = DataProcessor()
        self.visualizer = DataVisualizer()
        self._current_df: Optional[pd.DataFrame] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        load_btn = QPushButton("📂 加载数据")
        load_btn.clicked.connect(self._load_data)
        toolbar.addWidget(load_btn)

        clean_btn = QPushButton("🧹 清洗数据")
        clean_btn.clicked.connect(self._clean_data)
        toolbar.addWidget(clean_btn)

        self.chart_combo = QComboBox()
        self.chart_combo.addItems(["折线图", "柱状图", "饼图", "直方图", "散点图", "热力图", "箱线图"])
        toolbar.addWidget(QLabel("图表:"))
        toolbar.addWidget(self.chart_combo)

        chart_btn = QPushButton("📊 生成图表")
        chart_btn.clicked.connect(self._generate_chart)
        toolbar.addWidget(chart_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 主内容区
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧: 数据表格
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel("请加载数据文件 (CSV/JSON)")
        left_layout.addWidget(self.info_label)

        self.table_widget = QTableWidget()
        left_layout.addWidget(self.table_widget)
        splitter.addWidget(left_widget)

        # 右侧: 统计信息 + 图表
        right_tabs = QTabWidget()

        # 统计信息
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        right_tabs.addTab(self.stats_text, "统计信息")

        # 图表
        chart_scroll = QScrollArea()
        chart_scroll.setWidgetResizable(True)
        self.chart_label = QLabel("生成图表后将在这里显示")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_label.setMinimumHeight(300)
        chart_scroll.setWidget(self.chart_label)
        right_tabs.addTab(chart_scroll, "图表")

        splitter.addWidget(right_tabs)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)

    def _load_data(self):
        """加载数据文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", "",
            "数据文件 (*.csv *.json);;CSV文件 (*.csv);;JSON文件 (*.json);;所有文件 (*)"
        )
        if not file_path:
            return

        try:
            path = Path(file_path)
            if path.suffix == ".csv":
                self._current_df = self.processor.load_csv(path)
            elif path.suffix == ".json":
                self._current_df = self.processor.load_json(path)
            else:
                QMessageBox.warning(self, "不支持", f"不支持的文件格式: {path.suffix}")
                return

            self._display_dataframe(self._current_df)
            self.info_label.setText(
                f"📁 {path.name} | 行: {len(self._current_df)} | 列: {len(self._current_df.columns)}"
            )

            # 显示统计摘要
            summary = self.processor.summary()
            self.stats_text.setText(
                f"数据概况:\n"
                f"  行数: {summary.get('行数', '?')}\n"
                f"  列数: {summary.get('列数', '?')}\n"
                f"  内存占用: {summary.get('内存占用', '?')}\n\n"
                f"列信息:\n"
            )
            for col, info in summary.get("各列信息", {}).items():
                self.stats_text.append(f"  • {col}: {info.get('类型', '?')} | "
                                       f"非空: {info.get('非空值', '?')} | "
                                       f"唯一值: {info.get('唯一值', '?')}")

        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def _display_dataframe(self, df: pd.DataFrame):
        """在表格控件中显示DataFrame"""
        self.table_widget.setRowCount(len(df))
        self.table_widget.setColumnCount(len(df.columns))
        self.table_widget.setHorizontalHeaderLabels(list(df.columns))

        for row_idx in range(min(len(df), 100)):  # 最多显示100行
            for col_idx, col in enumerate(df.columns):
                val = df.iloc[row_idx, col_idx]
                item = QTableWidgetItem(str(val) if val is not None else "")
                self.table_widget.setItem(row_idx, col_idx, item)

        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if len(df) > 100:
            self.info_label.setText(
                self.info_label.text() + f" (显示前100行，共{len(df)}行)"
            )

    def _clean_data(self):
        """清洗数据"""
        if self._current_df is None:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return

        try:
            self.processor.load_dataframe(self._current_df)
            cleaned_df = self.processor.clean()
            self._current_df = cleaned_df
            self._display_dataframe(cleaned_df)
            QMessageBox.information(self, "完成", "数据清洗完成！")
        except Exception as e:
            QMessageBox.critical(self, "清洗失败", str(e))

    def _generate_chart(self):
        """生成图表"""
        if self._current_df is None:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return

        chart_type = self.chart_combo.currentText()
        try:
            img_base64 = self._create_chart(chart_type)
            if img_base64:
                pixmap = QPixmap()
                import base64
                img_data = base64.b64decode(img_base64.split(",")[1])
                pixmap.loadFromData(img_data)
                self.chart_label.setPixmap(
                    pixmap.scaledToWidth(500, Qt.TransformationMode.SmoothTransformation)
                )
        except Exception as e:
            QMessageBox.critical(self, "图表生成失败", str(e))

    def _create_chart(self, chart_type: str) -> Optional[str]:
        """根据类型创建图表"""
        df = self._current_df
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            QMessageBox.warning(self, "提示", "数据中没有数值列")
            return None

        if chart_type == "折线图":
            if "date" in df.columns:
                return self.visualizer.line_chart(df, "date", numeric_cols[0])
            return self.visualizer.line_chart(df, df.index, numeric_cols[0])

        elif chart_type == "柱状图":
            cat_cols = df.select_dtypes(include="object").columns.tolist()
            x_col = cat_cols[0] if cat_cols else df.index
            return self.visualizer.bar_chart(df, x_col, numeric_cols[0])

        elif chart_type == "饼图":
            value_counts = df[numeric_cols[0]].value_counts().head(10)
            return self.visualizer.pie_chart(value_counts)

        elif chart_type == "直方图":
            return self.visualizer.histogram(df[numeric_cols[0]])

        elif chart_type == "散点图":
            if len(numeric_cols) >= 2:
                return self.visualizer.scatter(df, numeric_cols[0], numeric_cols[1])
            return self.visualizer.scatter(df, df.index, numeric_cols[0])

        elif chart_type == "热力图":
            return self.visualizer.correlation_heatmap(df)

        elif chart_type == "箱线图":
            return self.visualizer.box_plot(df)

        return None

    def load_file(self, file_path: str):
        """外部接口：加载文件"""
        if Path(file_path).suffix == ".csv":
            self._current_df = self.processor.load_csv(file_path)
        elif Path(file_path).suffix == ".json":
            self._current_df = self.processor.load_json(file_path)

        if self._current_df is not None:
            self._display_dataframe(self._current_df)

    def get_current_data(self) -> Optional[pd.DataFrame]:
        """获取当前数据"""
        return self._current_df
