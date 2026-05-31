"""
桌面应用主窗口
集成爬虫、数据分析、仪表盘等多标签页功能
"""
import sys
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QMessageBox, QStatusBar, QMenuBar, QMenu, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon

from .crawler_panel import CrawlerPanel
from .analysis_panel import AnalysisPanel
from .dashboard_panel import DashboardPanel

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """桌面应用主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("全能数据平台 - 桌面版")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        self._setup_menu()
        self._setup_ui()
        self._setup_status_bar()

        # 状态刷新定时器
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(5000)

    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        import_action = QAction("导入数据...", self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(self._import_data)
        file_menu.addAction(import_action)

        export_action = QAction("导出数据...", self)
        export_action.setShortcut("Ctrl+S")
        export_action.triggered.connect(self._export_data)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        run_crawler_action = QAction("运行爬虫...", self)
        run_crawler_action.triggered.connect(self._focus_tab)
        tools_menu.addAction(run_crawler_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_ui(self):
        """设置主界面"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setDocumentMode(True)

        self.crawler_panel = CrawlerPanel()
        self.analysis_panel = AnalysisPanel()
        self.dashboard_panel = DashboardPanel()

        self.tabs.addTab(self.crawler_panel, "🕷️ 爬虫")
        self.tabs.addTab(self.analysis_panel, "📊 数据分析")
        self.tabs.addTab(self.dashboard_panel, "📈 仪表盘")

        layout.addWidget(self.tabs)

    def _setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _import_data(self):
        """导入数据文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "",
            "数据文件 (*.csv *.json *.xlsx);;所有文件 (*)"
        )
        if file_path:
            self.analysis_panel.load_file(file_path)
            self.tabs.setCurrentWidget(self.analysis_panel)
            self.status_bar.showMessage(f"已加载: {Path(file_path).name}")

    def _export_data(self):
        """导出数据"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "export.csv",
            "CSV文件 (*.csv);;JSON文件 (*.json)"
        )
        if file_path:
            try:
                import pandas as pd
                df = self.analysis_panel.get_current_data()
                if df is not None:
                    if file_path.endswith(".csv"):
                        df.to_csv(file_path, index=False, encoding="utf-8-sig")
                    else:
                        df.to_json(file_path, orient="records", force_ascii=False)
                    self.status_bar.showMessage(f"数据已导出: {Path(file_path).name}")
                else:
                    QMessageBox.warning(self, "导出失败", "没有可导出的数据")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def _focus_tab(self):
        """切换到指定标签页"""
        self.tabs.setCurrentWidget(self.crawler_panel)

    def _update_status(self):
        """定时更新状态栏"""
        crawler_count = self.crawler_panel.get_crawl_count()
        self.status_bar.showMessage(
            f"爬取记录: {crawler_count} | "
            f"就绪"
        )

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于 全能数据平台",
            "<h2>全能数据平台 v1.0</h2>"
            "<p>集爬虫、数据分析、机器学习、可视化于一体的综合性数据工具</p>"
            "<p>基于 Python + PyQt6 + FastAPI</p>"
        )

    def closeEvent(self, event):
        """关闭事件"""
        reply = QMessageBox.question(
            self, "确认退出", "确定要退出程序吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


def run_desktop_app():
    """启动桌面应用"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
