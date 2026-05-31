"""
爬虫控制面板 - 桌面版
提供URL输入、爬取控制、结果预览等功能
"""
import json
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QGroupBox, QSplitter, QHeaderView, QMessageBox, QProgressBar,
    QCheckBox, QSpinBox, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from crawler import WebScraper, CrawlResult

logger = logging.getLogger(__name__)


class CrawlWorker(QThread):
    """爬虫工作线程"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.scraper = WebScraper()

    def run(self):
        try:
            self.progress.emit("正在爬取...")
            result = self.scraper.crawl(self.url)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CrawlerPanel(QWidget):
    """爬虫控制面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._crawl_count = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 顶部控制区
        control_group = QGroupBox("爬虫控制")
        control_layout = QVBoxLayout()

        # URL输入行
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setText("https://httpbin.org/html")
        url_layout.addWidget(self.url_input)
        control_layout.addLayout(url_layout)

        # 选项行
        options_layout = QHBoxLayout()
        self.table_check = QCheckBox("提取表格")
        self.table_check.setChecked(True)
        self.article_check = QCheckBox("提取文章")
        options_layout.addWidget(self.table_check)
        options_layout.addWidget(self.article_check)
        options_layout.addStretch()

        self.crawl_btn = QPushButton("🚀 开始爬取")
        self.crawl_btn.clicked.connect(self._start_crawl)
        self.crawl_btn.setStyleSheet(
            "background:#1890ff; color:white; padding:8px 24px; font-size:14px;"
        )
        options_layout.addWidget(self.crawl_btn)
        control_layout.addLayout(options_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 结果显示区
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 结果文本
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("爬取结果将显示在这里...")
        splitter.addWidget(self.result_text)

        # 表格结果
        result_tabs = QTabWidget()
        self.table_widget = QTableWidget()
        self.table_widget.setVisible(False)
        result_tabs.addTab(self.table_widget, "表格数据")

        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setPlaceholderText("原始响应...")
        result_tabs.addTab(self.raw_text, "原始数据")

        splitter.addWidget(result_tabs)
        layout.addWidget(splitter)

    def _start_crawl(self):
        """开始爬取"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入URL")
            return

        self.crawl_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.result_text.setText("⏳ 正在爬取...")

        self.worker = CrawlWorker(url)
        self.worker.finished.connect(self._on_crawl_finished)
        self.worker.error.connect(self._on_crawl_error)
        self.worker.start()

    def _on_crawl_finished(self, result: CrawlResult):
        """爬取完成回调"""
        self.crawl_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._crawl_count += 1

        if not result.success:
            self.result_text.setText(f"❌ 爬取失败 (状态码: {result.status_code})")
            return

        info = (
            f"✅ 爬取成功！\n\n"
            f"📌 标题: {result.title or '(无标题)'}\n"
            f"🔗 URL: {result.url}\n"
            f"📏 内容长度: {len(result.content)} 字符\n"
            f"🕐 时间: {result.crawled_at}\n"
            f"📎 链接数: {result.metadata.get('links_count', 0)}\n"
        )
        self.result_text.setText(info)

        # 显示原始内容摘要
        self.raw_text.setText(result.html[:5000] if result.html else "(空)")

        # 尝试提取表格
        if self.table_check.isChecked() and result.html:
            try:
                table_df = self._extract_table(result.html)
                if table_df is not None:
                    self._display_table(table_df)
            except Exception as e:
                logger.warning(f"表格提取失败: {e}")

    def _on_crawl_error(self, error_msg: str):
        """爬取错误回调"""
        self.crawl_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.result_text.setText(f"❌ 爬取失败:\n{error_msg}")

    def _extract_table(self, html: str):
        """从HTML提取表格"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return None

        import pandas as pd
        rows = table.find_all("tr")
        data = []
        for row in rows:
            cells = row.find_all(["th", "td"])
            data.append([cell.get_text(strip=True) for cell in cells])

        if data:
            return data
        return None

    def _display_table(self, data: list):
        """在表格控件中显示数据"""
        if not data:
            return

        self.table_widget.setVisible(True)
        self.table_widget.setRowCount(len(data))
        self.table_widget.setColumnCount(max(len(r) for r in data))
        self.table_widget.setHorizontalHeaderLabels(
            [f"列{i+1}" for i in range(self.table_widget.columnCount())]
        )

        for row_idx, row_data in enumerate(data):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                self.table_widget.setItem(row_idx, col_idx, item)

        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def get_crawl_count(self) -> int:
        """获取爬取次数"""
        return self._crawl_count
