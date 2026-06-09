"""
晚间回溯模块测试
"""
import pytest
import tempfile
from pathlib import Path
from datetime import date
from morning.db_manager import DBManager
from morning.stock_tracker import StockTracker


class TestStockTracker:
    """股票跟踪器测试"""

    @pytest.fixture
    def tracker(self, tmp_path):
        """创建股票跟踪器"""
        db_manager = DBManager(
            str(tmp_path / "daily"),
            str(tmp_path / "global.db")
        )
        yield StockTracker(db_manager)
        del db_manager
        import gc
        gc.collect()

    def test_get_tracking_stocks_empty(self, tracker):
        """测试获取空跟踪列表"""
        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 0

    def test_get_tracking_stocks_with_recommendations(self, tracker):
        """测试获取推荐股票"""
        # 添加推荐记录
        tracker.db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")

        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 1
        assert stocks[0]["stock_code"] == "000001"
        assert stocks[0]["is_watchlist"] == False

    def test_get_tracking_stocks_with_watchlist(self, tracker):
        """测试获取特别关注股票"""
        # 添加特别关注
        tracker.db_manager.add_watchlist("600036", "招商银行", 35.20, "价值投资")

        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 1
        assert stocks[0]["stock_code"] == "600036"
        assert stocks[0]["is_watchlist"] == True

    def test_get_tracking_stocks_dedup(self, tracker):
        """测试去重"""
        # 同时添加推荐和特别关注
        tracker.db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")
        tracker.db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线")

        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 1

    def test_generate_report_empty(self, tracker):
        """测试生成空报告"""
        report = tracker.generate_report([])
        assert "暂无跟踪股票" in report

    def test_generate_report_with_data(self, tracker):
        """测试生成报告"""
        from morning.stock_tracker import StockTrackingInfo

        info = StockTrackingInfo(
            stock_code="000001",
            stock_name="平安银行",
            is_watchlist=False,
            recommend_date=date.today(),
            recommend_price=10.83,
            current_price=11.13,
            change_pct=0.028,
            tracking_days=5,
            history_data=[
                {"trade_date": "2026-06-05", "open": 10.83, "high": 10.98, "low": 10.75, "close": 10.90, "volume": 123456, "turnover_rate": 0.0185, "change_pct": 0.0065},
                {"trade_date": "2026-06-06", "open": 10.90, "high": 11.05, "low": 10.88, "close": 11.00, "volume": 134567, "turnover_rate": 0.0192, "change_pct": 0.0092}
            ]
        )

        report = tracker.generate_report([info])
        assert "000001" in report
        assert "平安银行" in report
        assert "+2.80%" in report
