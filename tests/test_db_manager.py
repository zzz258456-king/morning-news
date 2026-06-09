# tests/test_db_manager.py
"""
数据库管理模块测试
"""
import pytest
import gc
import tempfile
import shutil
from datetime import date, datetime
from pathlib import Path
from morning.db_manager import DBManager, TradeRecord


class TestDBManager:
    """数据库管理器测试"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """创建临时数据库管理器"""
        daily_path = tmp_path / "daily"
        global_path = tmp_path / "global.db"
        mgr = DBManager(str(daily_path), str(global_path))
        yield mgr
        # 确保所有 SQLite 连接被垃圾回收释放文件锁
        del mgr
        gc.collect()

    def test_init_global_db(self, db_manager):
        """测试全局数据库初始化"""
        assert db_manager.global_path.exists()

    def test_add_recommendation(self, db_manager):
        """测试添加推荐记录"""
        db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")

        recommendations = db_manager.get_recommendations(days=1)
        assert len(recommendations) == 1
        assert recommendations[0]["stock_code"] == "000001"
        assert recommendations[0]["stock_name"] == "平安银行"

    def test_add_watchlist(self, db_manager):
        """测试添加特别关注"""
        db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线", "短线")

        watchlist = db_manager.get_watchlist()
        assert len(watchlist) == 1
        assert watchlist[0].stock_code == "000001"
        assert watchlist[0].group_name == "短线"

    def test_remove_watchlist(self, db_manager):
        """测试移除特别关注"""
        db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线")
        db_manager.remove_watchlist("000001")

        watchlist = db_manager.get_watchlist()
        assert len(watchlist) == 0

    def test_add_trade_record(self, db_manager):
        """测试添加操作记录"""
        record = TradeRecord(
            trade_date=datetime.now(),
            trade_type="BUY",
            stock_code="000001",
            stock_name="平安银行",
            price=10.83,
            quantity=1000,
            reason="突破年线",
            emotion="自信",
            tags=["技术面"]
        )
        db_manager.add_trade_record(record)

        records = db_manager.get_trade_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "BUY"

    def test_get_status(self, db_manager):
        """测试获取数据库状态"""
        status = db_manager.get_status()
        assert "daily_db_count" in status
        assert "watchlist_count" in status
        assert "trade_record_count" in status

    def test_backup(self, db_manager, tmp_path):
        """测试备份功能"""
        db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线")

        backup_dir = str(tmp_path / "backup")
        db_manager.backup(backup_dir)
        assert len(list(Path(backup_dir).glob("*.db"))) > 0
