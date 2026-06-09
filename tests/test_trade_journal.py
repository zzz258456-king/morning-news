# tests/test_trade_journal.py
"""
操作日志模块测试
"""
import pytest
import tempfile
from pathlib import Path
from morning.db_manager import DBManager
from morning.trade_journal import TradeJournal


class TestTradeJournal:
    """操作日志管理器测试"""

    @pytest.fixture
    def journal(self, tmp_path):
        """创建操作日志管理器"""
        db_manager = DBManager(
            str(tmp_path / "daily"),
            str(tmp_path / "global.db")
        )
        yield TradeJournal(db_manager)
        del db_manager
        import gc
        gc.collect()

    def test_record_buy(self, journal):
        """测试记录买入"""
        result = journal.record_buy("000001", "平安银行", 10.83, 1000, "突破年线", "自信", ["技术面"])
        assert result == True

        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "BUY"

    def test_record_sell(self, journal):
        """测试记录卖出"""
        result = journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", "犹豫", ["技术面"], 0.028)
        assert result == True

        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "SELL"

    def test_record_watch(self, journal):
        """测试记录关注"""
        result = journal.record_watch("000001", "突破年线")
        assert result == True

        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "WATCH"

    def test_record_unwatch(self, journal):
        """测试记录取消关注"""
        result = journal.record_unwatch("000001")
        assert result == True

        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "UNWATCH"

    def test_record_note(self, journal):
        """测试记录备注"""
        result = journal.record_note("000001", "这是一条备注")
        assert result == True

        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "NOTE"

    def test_calculate_stats(self, journal):
        """测试计算统计"""
        # 添加测试数据
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", profit_loss=0.028)
        journal.record_sell("600036", "招商银行", 34.50, 1000, "止损", profit_loss=-0.02)

        stats = journal.calculate_stats(days=1)
        assert stats.total_trades == 2
        assert stats.win_count == 1
        assert stats.loss_count == 1
        assert stats.win_rate == 0.5

    def test_calculate_emotion_stats(self, journal):
        """测试情绪统计"""
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", "自信", profit_loss=0.028)
        journal.record_sell("600036", "招商银行", 34.50, 1000, "止损", "犹豫", profit_loss=-0.02)

        emotion_stats = journal.calculate_emotion_stats(days=1)
        assert len(emotion_stats) == 2

    def test_calculate_tag_stats(self, journal):
        """测试标签统计"""
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", tags=["技术面"], profit_loss=0.028)
        journal.record_sell("600036", "招商银行", 34.50, 1000, "止损", tags=["基本面"], profit_loss=-0.02)

        tag_stats = journal.calculate_tag_stats(days=1)
        assert len(tag_stats) == 2

    def test_generate_review_report(self, journal):
        """测试生成复盘报告"""
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", "自信", ["技术面"], 0.028)

        report = journal.generate_review_report(days=1)
        assert "操作复盘报告" in report
        assert "交易统计" in report
        assert "情绪分析" in report
        assert "标签分析" in report
