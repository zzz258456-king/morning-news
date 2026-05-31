"""
回测系统 GUI 主窗口
PyQt6 实现 — 简洁、暗色、专业
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QDateEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QSplitter, QStatusBar, QScrollArea,
    QFrame, QTextEdit, QFileDialog, QMessageBox, QGridLayout,
    QProgressBar, QCheckBox,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use('QtAgg')
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

from config import LOG_LEVEL, LOG_FORMAT
from strategy.base import StrategyFactory, BaseStrategy
from strategy.board_chaser import BoardChaserStrategy

logger = logging.getLogger(__name__)

# ---- 暗色主题配色 ----
THEME = {
    "bg": "#1a1a2e",
    "bg2": "#16213e",
    "card": "#1e2a4a",
    "card_hover": "#253a5e",
    "accent": "#64ffda",
    "accent2": "#1890ff",
    "text": "#e0e0e0",
    "text2": "#8892b0",
    "green": "#52c41a",
    "red": "#ff4d4f",
    "yellow": "#faad14",
    "border": "#2d3a5e",
}


# ============================================================
# 回测工作线程 (异步执行)
# ============================================================

class BacktestWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self, strategy: BaseStrategy, params: dict):
        super().__init__()
        self.strategy = strategy
        self.params = params

    def run(self):
        try:
            self.progress.emit("🚀 开始回测...")
            engine = self.strategy.run(**self.params)
            result = self.strategy.engine.summary()
            self.finished.emit(result)
        except Exception as e:
            self.progress.emit(f"❌ 回测失败: {e}")
            self.finished.emit(None)


# ============================================================
# 指标卡片
# ============================================================

class MetricCard(QFrame):
    def __init__(self, title: str, value: str, color: str = THEME["accent"]):
        super().__init__()
        self.setStyleSheet(f"""
            MetricCard {{
                background: {THEME['card']};
                border: 1px solid {THEME['border']};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {THEME['text2']}; font-size: 12px; border: none;")

        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; border: none;")

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, value: str, color: str = THEME["accent"]):
        self.value_lbl.setText(value)
        self.value_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; border: none;")


# ============================================================
# Matplotlib 图表
# ============================================================

class EquityCurveCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(8, 3), dpi=100, facecolor=THEME["bg2"])
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.fig.tight_layout(pad=2)

    def plot(self, equity_curve: list[float], trades: list):
        self.ax.clear()
        self.ax.set_facecolor(THEME["bg2"])
        self.fig.patch.set_facecolor(THEME["bg2"])

        if not equity_curve or len(equity_curve) < 2:
            self.ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                        color=THEME["text2"], fontsize=14, transform=self.ax.transAxes)
            self.draw()
            return

        # 归一化到初始资金
        initial = equity_curve[0]
        curve = [v / initial * 100 for v in equity_curve]

        x = range(len(curve))
        self.ax.plot(x, curve, color=THEME["accent"], linewidth=2, label="净值")
        self.ax.fill_between(x, 100, curve, alpha=0.1, color=THEME["accent"])

        # 基准线
        self.ax.axhline(y=100, color=THEME["text2"], linestyle="--", linewidth=0.5, alpha=0.5)

        # 标注买卖点
        if trades:
            for t in trades:
                if hasattr(t, 'buy_date') and t.stock_code:
                    # 找对应x位置（简化标注）
                    pass

        self.ax.set_xlabel("交易日", color=THEME["text2"], fontsize=10)
        self.ax.set_ylabel("净值%", color=THEME["text2"], fontsize=10)
        self.ax.tick_params(colors=THEME["text2"], labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color(THEME["border"])

        pnl = curve[-1] - 100
        color = THEME["green"] if pnl >= 0 else THEME["red"]
        self.ax.set_title(f"净值曲线 (总收益 {pnl:+.2f}%)",
                         color=THEME["text"], fontsize=12, fontweight="bold")

        self.ax.legend(loc="upper left", facecolor=THEME["card"],
                      edgecolor=THEME["border"], labelcolor=THEME["text"])
        self.draw()


# ============================================================
# 主窗口
# ============================================================

class BacktestMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = None
        self.result = None
        self.trades = []
        self.worker = None

        # 注册策略
        StrategyFactory.register(BoardChaserStrategy)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        self.setWindowTitle("🔬 量化回测系统 v3")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(f"background: {THEME['bg']}; color: {THEME['text']};")

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ===== 左面板：策略配置 =====
        left = QWidget()
        left.setFixedWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # 策略选择
        config_box = QGroupBox("策略配置")
        config_box.setStyleSheet(f"""
            QGroupBox {{
                background: {THEME['bg2']}; border: 1px solid {THEME['border']};
                border-radius: 8px; margin-top: 12px; padding: 16px 12px 12px;
                font-weight: bold; color: {THEME['accent']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 6px;
            }}
        """)
        cfg_layout = QVBoxLayout(config_box)
        cfg_layout.setSpacing(8)

        # 策略名称
        cfg_layout.addWidget(QLabel("策略类型"))
        self.cmb_strategy = QComboBox()
        self.cmb_strategy.addItems(StrategyFactory.list_strategies())
        self.cmb_strategy.setStyleSheet(self._input_style())
        cfg_layout.addWidget(self.cmb_strategy)

        # 评分门槛
        cfg_layout.addWidget(QLabel("最低评分 (14/40)"))
        self.spin_score = QSpinBox()
        self.spin_score.setRange(6, 35)
        self.spin_score.setValue(14)
        self.spin_score.setStyleSheet(self._input_style())
        cfg_layout.addWidget(self.spin_score)

        # 每日买入
        cfg_layout.addWidget(QLabel("每日买入上限"))
        self.spin_max_buy = QSpinBox()
        self.spin_max_buy.setRange(1, 10)
        self.spin_max_buy.setValue(3)
        self.spin_max_buy.setStyleSheet(self._input_style())
        cfg_layout.addWidget(self.spin_max_buy)

        # 仓位比例
        cfg_layout.addWidget(QLabel("单票仓位%"))
        self.spin_pos = QDoubleSpinBox()
        self.spin_pos.setRange(5, 30)
        self.spin_pos.setValue(10)
        self.spin_pos.setSuffix("%")
        self.spin_pos.setStyleSheet(self._input_style())
        cfg_layout.addWidget(self.spin_pos)

        # 初始资金
        cfg_layout.addWidget(QLabel("初始资金"))
        self.spin_capital = QSpinBox()
        self.spin_capital.setRange(100000, 100000000)
        self.spin_capital.setValue(1000000)
        self.spin_capital.setSingleStep(100000)
        self.spin_capital.setStyleSheet(self._input_style())
        cfg_layout.addWidget(self.spin_capital)

        cfg_layout.addStretch()
        left_layout.addWidget(config_box)

        # 运行按钮
        self.btn_run = QPushButton("🚀  运行回测")
        self.btn_run.setMinimumHeight(44)
        self.btn_run.setStyleSheet(f"""
            QPushButton {{
                background: {THEME['accent2']}; color: white;
                border: none; border-radius: 8px;
                font-size: 16px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #40a9ff; }}
            QPushButton:pressed {{ background: #096dd9; }}
            QPushButton:disabled {{ background: {THEME['border']}; color: {THEME['text2']}; }}
        """)
        self.btn_run.clicked.connect(self.run_backtest)
        left_layout.addWidget(self.btn_run)

        # 导出按钮
        self.btn_export = QPushButton("💾 导出CSV")
        self.btn_export.setMinimumHeight(36)
        self.btn_export.setStyleSheet(f"""
            QPushButton {{
                background: {THEME['card']}; color: {THEME['text']};
                border: 1px solid {THEME['border']}; border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {THEME['card_hover']}; }}
        """)
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_export.setEnabled(False)
        left_layout.addWidget(self.btn_export)

        left_layout.addStretch()

        # ===== 右面板：结果展示 =====
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # 状态和进度
        self.status_lbl = QLabel("就绪 — 配置参数后点击「运行回测」")
        self.status_lbl.setStyleSheet(f"color: {THEME['text2']}; font-size: 13px; padding: 4px 0;")
        right_layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background: {THEME['bg2']}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {THEME['accent2']}; border-radius: 2px; }}
        """)
        right_layout.addWidget(self.progress_bar)
        self.progress_bar.hide()

        # Tab 面板
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {THEME['bg2']}; border: 1px solid {THEME['border']};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {THEME['card']}; color: {THEME['text2']};
                border: none; padding: 8px 18px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {THEME['bg2']}; color: {THEME['accent']};
                border-bottom: 2px solid {THEME['accent']};
            }}
            QTabBar::tab:hover {{ color: {THEME['text']}; }}
        """)

        # Tab 1: 绩效指标
        self.tab_metrics = QWidget()
        self._init_metrics_tab()
        self.tabs.addTab(self.tab_metrics, "📊 绩效指标")

        # Tab 2: 净值曲线
        self.tab_chart = QWidget()
        self._init_chart_tab()
        self.tabs.addTab(self.tab_chart, "📈 净值曲线")

        # Tab 3: 交易流水
        self.tab_trades = QWidget()
        self._init_trades_tab()
        self.tabs.addTab(self.tab_trades, "📋 交易流水")

        # Tab 4: 评级分析
        self.tab_analysis = QWidget()
        self._init_analysis_tab()
        self.tabs.addTab(self.tab_analysis, "📊 评级分析")

        right_layout.addWidget(self.tabs)

        # 分割
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)
        main_layout.addWidget(splitter)

        # 状态栏
        self.sb = QStatusBar()
        self.sb.setStyleSheet(f"background: {THEME['bg2']}; color: {THEME['text2']}; border-top: 1px solid {THEME['border']};")
        self.setStatusBar(self.sb)
        self.sb.showMessage("就绪")

    def _input_style(self):
        return f"""
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background: {THEME['bg']}; color: {THEME['text']};
                border: 1px solid {THEME['border']};
                border-radius: 6px; padding: 6px 10px; font-size: 13px;
                min-height: 20px;
            }}
            QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
                border-color: {THEME['accent2']};
            }}
            QComboBox::drop-down {{
                border: none; width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none; border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {THEME['text']};
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background: {THEME['bg2']}; color: {THEME['text']};
                selection-background-color: {THEME['accent2']};
                border: 1px solid {THEME['border']};
            }}
        """

    def _apply_theme(self):
        """应用全局暗色主题"""
        pass  # 样式已内联

    def _init_metrics_tab(self):
        layout = QVBoxLayout(self.tab_metrics)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 指标网格
        grid = QGridLayout()
        grid.setSpacing(10)

        metrics = [
            ("总收益率", "total_return", THEME["green"]),
            ("年化收益率", "annual_return", THEME["accent2"]),
            ("最大回撤", "max_drawdown", THEME["red"]),
            ("夏普比率", "sharpe_ratio", THEME["yellow"]),
            ("胜率", "win_rate", THEME["green"]),
            ("交易次数", "total_trades", THEME["accent"]),
            ("盈亏比", "profit_loss_ratio", THEME["accent2"]),
            ("盈利/亏损", "win_lose", THEME["green"]),
            ("平均持仓", "avg_hold_days", THEME["text"]),
            ("最终权益", "final_equity", THEME["accent"]),
        ]

        self.metric_cards = {}
        for i, (title, key, color) in enumerate(metrics):
            card = MetricCard(title, "—", color)
            row, col = i // 4, i % 4
            grid.addWidget(card, row, col)
            self.metric_cards[key] = card

        layout.addLayout(grid)
        layout.addStretch()

        # 空状态
        self.empty_metrics = QLabel("运行回测后展示绩效指标")
        self.empty_metrics.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_metrics.setStyleSheet(f"color: {THEME['text2']}; font-size: 16px; border: none;")
        layout.addWidget(self.empty_metrics)

    def _init_chart_tab(self):
        layout = QVBoxLayout(self.tab_chart)
        layout.setContentsMargins(20, 16, 20, 16)
        self.chart_canvas = EquityCurveCanvas()
        layout.addWidget(self.chart_canvas)

        # 累计收益表
        self.chart_metrics_lbl = QLabel("运行回测后查看净值曲线")
        self.chart_metrics_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_metrics_lbl.setStyleSheet(f"color: {THEME['text2']}; font-size: 14px; border: none;")
        layout.addWidget(self.chart_metrics_lbl)

    def _init_trades_tab(self):
        layout = QVBoxLayout(self.tab_trades)
        layout.setContentsMargins(12, 12, 12, 12)

        self.trade_table = QTableWidget()
        self.trade_table.setStyleSheet(f"""
            QTableWidget {{
                background: {THEME['bg']}; color: {THEME['text']};
                border: 1px solid {THEME['border']}; border-radius: 6px;
                gridline-color: {THEME['border']}; font-size: 12px;
            }}
            QHeaderView::section {{
                background: {THEME['bg2']}; color: {THEME['accent']};
                padding: 8px; border: none; font-weight: bold;
            }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background: {THEME['accent2']}; }}
        """)
        self.trade_table.setAlternatingRowColors(True)
        self.trade_table.setStyleSheet(self.trade_table.styleSheet() + f"""
            QTableWidget::item:alternate {{ background: {THEME['bg2']}; }}
        """)
        self.trade_table.horizontalHeader().setStretchLastSection(True)
        self.trade_table.verticalHeader().setVisible(False)
        self.trade_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.trade_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        headers = ["代码", "名称", "买入日", "收益率%", "评分", "级别", "板型", "卖出原因"]
        self.trade_table.setColumnCount(len(headers))
        self.trade_table.setHorizontalHeaderLabels(headers)

        layout.addWidget(self.trade_table)

    def _init_analysis_tab(self):
        layout = QVBoxLayout(self.tab_analysis)
        layout.setContentsMargins(16, 12, 16, 12)

        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setStyleSheet(f"""
            QTextEdit {{
                background: {THEME['bg']}; color: {THEME['text']};
                border: 1px solid {THEME['border']}; border-radius: 6px;
                padding: 12px; font-size: 13px;
            }}
        """)
        self.analysis_text.setText("运行回测后展示评级分析和月度统计")
        layout.addWidget(self.analysis_text)

    # ============================================================
    # 运行回测
    # ============================================================

    def run_backtest(self):
        self.btn_run.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_lbl.setText("🔄 正在获取数据...")
        self.sb.showMessage("回测进行中...")

        strategy_name = self.cmb_strategy.currentText()
        params = {
            "min_score": self.spin_score.value(),
            "max_daily_buy": self.spin_max_buy.value(),
            "single_pct": self.spin_pos.value() / 100,
            "initial_capital": self.spin_capital.value(),
        }

        try:
            strategy = StrategyFactory.create(strategy_name, initial_capital=params.pop("initial_capital"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"策略创建失败: {e}")
            self._reset_ui()
            return

        self.worker = BacktestWorker(strategy, params)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, msg: str):
        self.status_lbl.setText(msg)

    def _on_finished(self, result):
        if result is None:
            self.status_lbl.setText("❌ 回测失败")
            self.sb.showMessage("回测失败")
            self._reset_ui()
            return

        self.result = result
        self.trades = result.trades if hasattr(result, 'trades') else []
        self.engine = self.worker.strategy.engine if self.worker else None

        self._update_metrics(result)
        self._update_chart(result)
        self._update_trades(result)
        self._update_analysis(result)

        line = f"✅ 回测完成! {result.total_trades}笔交易, 收益{result.total_return:+.2f}%"
        self.status_lbl.setText(line)
        self.sb.showMessage(line)
        self.btn_export.setEnabled(len(self.trades) > 0)
        self._reset_ui()

    def _reset_ui(self):
        self.btn_run.setEnabled(True)
        self.progress_bar.hide()

    def _update_metrics(self, r):
        self.empty_metrics.hide()

        color_pnl = THEME["green"] if r.total_return >= 0 else THEME["red"]
        self.metric_cards["total_return"].set_value(f"{r.total_return:+.2f}%", color_pnl)
        self.metric_cards["annual_return"].set_value(f"{r.annual_return:+.2f}%", color_pnl)
        self.metric_cards["max_drawdown"].set_value(f"-{abs(r.max_drawdown):.2f}%", THEME["red"])
        self.metric_cards["sharpe_ratio"].set_value(f"{r.sharpe_ratio:.2f}", THEME["yellow"])
        self.metric_cards["win_rate"].set_value(f"{r.win_rate:.1f}%", THEME["green"])
        self.metric_cards["total_trades"].set_value(f"{r.total_trades}", THEME["accent"])
        self.metric_cards["profit_loss_ratio"].set_value(f"{r.profit_loss_ratio:.2f}", THEME["accent2"])
        self.metric_cards["win_lose"].set_value(f"{r.win_trades}/{r.lose_trades}",
                                                THEME["green"] if r.win_trades >= r.lose_trades else THEME["red"])
        self.metric_cards["avg_hold_days"].set_value(f"{r.avg_hold_days:.1f}天", THEME["text"])
        self.metric_cards["final_equity"].set_value(f"¥{r.trades[0].profit_amount + r.trades[0].buy_price * r.trades[0].volume if r.trades else 0:,.0f}".replace("¥0", "¥—"),
                                                    THEME["accent"])

        # 修正最终权益显示
        if self.engine:
            self.metric_cards["final_equity"].set_value(f"¥{self.engine.equity:,.0f}", THEME["accent"])

    def _update_chart(self, r):
        if self.engine:
            self.chart_canvas.plot(self.engine.equity_curve, r.trades)
            ret = r.total_return
            dd = r.max_drawdown
            self.chart_metrics_lbl.setText(
                f"总收益 {ret:+.2f}%   |   最大回撤 {dd:.2f}%   |   夏普 {r.sharpe_ratio:.2f}"
            )
            self.chart_metrics_lbl.setStyleSheet(f"color: {THEME['text']}; font-size: 13px; border: none;")

    def _update_trades(self, r):
        self.trade_table.setRowCount(len(r.trades))
        for i, t in enumerate(r.trades):
            level = t.signal_detail.get("level", "")
            color = THEME["green"] if level == "A" else THEME["yellow"] if level == "B" else THEME["red"] if level == "D" else THEME["text"]

            items = [
                t.stock_code, t.stock_name, t.buy_date,
                f"{t.profit_pct:+.2f}%", str(t.rating),
                level, t.board_type, t.exit_reason,
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(val)
                if j == 3:  # 收益率
                    item.setForeground(QColor(THEME["green"] if t.profit_pct >= 0 else THEME["red"]))
                elif j == 5:  # 级别
                    item.setForeground(QColor(color))
                    item.setFont(QFont("", 10, QFont.Weight.Bold))
                self.trade_table.setItem(i, j, item)

        self.trade_table.resizeColumnsToContents()

    def _update_analysis(self, r):
        lines = []
        lines.append("═" * 40)
        lines.append("  评 级 分 析")
        lines.append("═" * 40)

        # 评分收益
        from collections import Counter
        levels = Counter(t.signal_detail.get("level", "?") for t in r.trades)
        lines.append("")
        for lv in ["A", "B", "C", "D"]:
            sub = [t for t in r.trades if t.signal_detail.get("level") == lv]
            if not sub:
                continue
            wr = sum(1 for t in sub if t.profit_pct > 0) / len(sub) * 100
            avg = np.mean([t.profit_pct for t in sub])
            lines.append(f"  {lv}级: {len(sub):>2}次  胜率{wr:>5.1f}%  均收益{avg:>+6.2f}%")

        # 子策略
        stypes = Counter(t.signal_detail.get("board_type", "?") for t in r.trades)
        lines.append("")
        lines.append("  子策略分布:")
        for st, _ in stypes.most_common():
            sub = [t for t in r.trades if t.signal_detail.get("board_type") == st]
            wr = sum(1 for t in sub if t.profit_pct > 0) / len(sub) * 100
            avg = np.mean([t.profit_pct for t in sub])
            lines.append(f"  {st:<6} {len(sub):>2}次  胜率{wr:>5.1f}%  均{avg:>+6.2f}%")

        # 月度
        from collections import defaultdict
        monthly = defaultdict(list)
        for t in r.trades:
            monthly[t.buy_date[:6]].append(t.profit_pct)
        if monthly:
            lines.append("")
            lines.append("  月度统计:")
            for m in sorted(monthly):
                sub = monthly[m]
                wr = sum(1 for p in sub if p > 0) / len(sub) * 100
                avg = np.mean(sub)
                lines.append(f"  {m}: {len(sub):>2}次  胜率{wr:>4.0f}%  均{avg:>+5.2f}%")

        lines.append("")
        lines.append("═" * 40)

        self.analysis_text.setText("\n".join(lines))

    # ============================================================
    # 导出
    # ============================================================

    def export_csv(self):
        if not self.trades:
            QMessageBox.information(self, "提示", "没有交易记录可导出")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出交易记录", f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV文件 (*.csv)")
        if not path:
            return

        records = []
        for t in self.trades:
            records.append({
                "代码": t.stock_code, "名称": t.stock_name,
                "买入日": t.buy_date, "卖出日": t.sell_date,
                "买入价": round(t.buy_price, 2), "卖出价": round(t.sell_price, 2),
                "收益率%": round(t.profit_pct, 2), "盈亏额": round(t.profit_amount, 2),
                "评分": t.rating, "级别": t.signal_detail.get("level", ""),
                "板型": t.board_type, "卖出原因": t.exit_reason,
            })

        pd.DataFrame(records).to_csv(path, index=False, encoding="utf-8-sig")
        QMessageBox.information(self, "导出成功", f"已导出 {len(records)} 条记录\n{path}")


# ============================================================
# 启动入口
# ============================================================

def run_ui():
    """启动回测系统 GUI"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = BacktestMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_ui()
