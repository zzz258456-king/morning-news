"""
仪表盘面板 - 桌面版
展示系统状态和数据概览
"""
import logging
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QGridLayout, QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
import io
import base64

from config import RAW_DATA_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class DashboardPanel(QWidget):
    """仪表盘面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(10000)  # 每10秒刷新
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 统计卡片
        cards_layout = QGridLayout()
        self.stat_labels = {}

        stats = [
            ("raw_files", "📄 原始文件", "0"),
            ("processed_files", "📊 已处理文件", "0"),
            ("status", "🔧 系统状态", "运行中"),
            ("runtime", "🕐 运行时间", "刚刚启动"),
        ]

        for i, (key, title, value) in enumerate(stats):
            group = QGroupBox(title)
            group.setStyleSheet(
                "QGroupBox { font-weight: bold; border: 1px solid #ddd; "
                "border-radius: 8px; padding: 16px; margin: 4px; }"
            )
            vbox = QVBoxLayout()
            label = QLabel(value)
            label.setStyleSheet("font-size: 28px; font-weight: bold; color: #1890ff;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stat_labels[key] = label
            vbox.addWidget(label)
            group.setLayout(vbox)
            cards_layout.addWidget(group, i // 4, i % 4)

        layout.addLayout(cards_layout)

        # 图表区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)

        self.chart_label = QLabel()
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_label.setMinimumHeight(350)
        chart_layout.addWidget(self.chart_label)

        scroll.setWidget(chart_widget)
        layout.addWidget(scroll)

        # 系统信息
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        layout.addWidget(self.info_text)

    def _refresh(self):
        """刷新仪表盘数据"""
        try:
            # 统计文件
            raw_count = len(list(RAW_DATA_DIR.glob("*"))) if RAW_DATA_DIR.exists() else 0
            proc_count = len(list(PROCESSED_DATA_DIR.glob("*"))) if PROCESSED_DATA_DIR.exists() else 0

            self.stat_labels["raw_files"].setText(str(raw_count))
            self.stat_labels["processed_files"].setText(str(proc_count))

            # 生成迷你图表
            self._generate_dashboard_chart()

            # 系统信息
            self.info_text.setText(
                f"📁 原始数据目录: {RAW_DATA_DIR}\n"
                f"📁 已处理数据目录: {PROCESSED_DATA_DIR}\n"
                f"📄 原始文件数: {raw_count}\n"
                f"📄 已处理文件数: {proc_count}\n"
                f"🕐 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

        except Exception as e:
            logger.error(f"仪表盘刷新失败: {e}")

    def _generate_dashboard_chart(self):
        """生成仪表盘图表"""
        fig, ax = plt.subplots(figsize=(8, 3.5))
        fig.patch.set_facecolor('white')

        # 示例数据：模拟7天的数据量
        days = 7
        categories = ['爬取数据', '分析结果', '模型输出']
        data = {
            '爬取数据': np.random.randint(5, 20, days),
            '分析结果': np.random.randint(3, 15, days),
            '模型输出': np.random.randint(1, 8, days),
        }

        x = np.arange(days)
        width = 0.25
        colors = ['#1890ff', '#52c41a', '#faad14']

        for i, (cat, values) in enumerate(data.items()):
            bars = ax.bar(x + i * width, values, width, label=cat, color=colors[i], alpha=0.85)

        ax.set_xlabel('近7天')
        ax.set_ylabel('数据量')
        ax.set_title('📈 数据量趋势')
        ax.set_xticks(x + width)
        ax.set_xticklabels([f'第{i+1}天' for i in range(days)])
        ax.legend(loc='upper left')
        ax.set_facecolor('#fafafa')
        fig.tight_layout()

        # 转为QPixmap
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())
        self.chart_label.setPixmap(
            pixmap.scaledToWidth(700, Qt.TransformationMode.SmoothTransformation)
        )
