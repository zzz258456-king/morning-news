# tests/test_integration.py
"""
集成测试
"""
import pytest
import tempfile
from pathlib import Path
from morning.db_manager import DBManager
from morning.watchlist_manager import WatchlistManager
from morning.trade_journal import TradeJournal
from morning.stock_tracker import StockTracker
from morning.anomaly_monitor import AnomalyMonitor


class TestIntegration:
    """集成测试"""

    @pytest.fixture
    def setup(self, tmp_path):
        """设置测试环境"""
        db_manager = DBManager(
            str(tmp_path / "daily"),
            str(tmp_path / "global.db")
        )
        yield db_manager
        del db_manager
        import gc
        gc.collect()

    def test_full_workflow(self, setup):
        """测试完整工作流程"""
        db_manager = setup

        # 1. 添加推荐记录
        db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")

        # 2. 添加特别关注
        watchlist_manager = WatchlistManager(db_manager)
        watchlist_manager.add("600036", "招商银行", 35.20, "价值投资", "中线")

        # 3. 记录操作
        journal = TradeJournal(db_manager)
        journal.record_buy("000001", "平安银行", 10.83, 1000, "突破年线", "自信", ["技术面"])

        # 4. 验证数据
        recommendations = db_manager.get_recommendations(days=1)
        assert len(recommendations) == 1

        watchlist = db_manager.get_watchlist()
        assert len(watchlist) == 1

        records = journal.get_records(days=1)
        assert len(records) == 1

        # 5. 生成报告
        report = journal.generate_review_report(days=1)
        assert "操作复盘报告" in report

    def test_database_operations(self, setup):
        """测试数据库操作"""
        db_manager = setup

        # 测试备份
        with tempfile.TemporaryDirectory() as backup_dir:
            db_manager.backup(backup_dir)
            assert len(list(Path(backup_dir).glob("*.db"))) > 0

        # 测试状态
        status = db_manager.get_status()
        assert "daily_db_count" in status

    def test_anomaly_monitor_integration(self, setup):
        """测试异动监控集成"""
        monitor = AnomalyMonitor({"push_threshold": 60})
        result = monitor.run()

        assert 0 <= result.total_score <= 100
        assert isinstance(result.should_push, bool)
