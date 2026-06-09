# tests/test_watchlist_manager.py
"""
特别关注模块测试
"""
import pytest
import tempfile
from pathlib import Path
from morning.db_manager import DBManager
from morning.watchlist_manager import WatchlistManager


class TestWatchlistManager:
    """特别关注管理器测试"""

    @pytest.fixture
    def manager(self, tmp_path):
        """创建特别关注管理器"""
        db_manager = DBManager(
            str(tmp_path / "daily"),
            str(tmp_path / "global.db")
        )
        yield WatchlistManager(db_manager)
        del db_manager
        import gc
        gc.collect()

    def test_add(self, manager):
        """测试添加关注"""
        result = manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        assert result == True

        watchlist = manager.list()
        assert len(watchlist) == 1
        assert watchlist[0].stock_code == "000001"

    def test_remove(self, manager):
        """测试移除关注"""
        manager.add("000001", "平安银行", 10.83, "突破年线")
        result = manager.remove("000001")
        assert result == True

        watchlist = manager.list()
        assert len(watchlist) == 0

    def test_list(self, manager):
        """测试获取列表"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        manager.add("600036", "招商银行", 35.20, "价值投资", "中线")

        # 获取全部
        watchlist = manager.list()
        assert len(watchlist) == 2

        # 按分组获取
        watchlist = manager.list("短线")
        assert len(watchlist) == 1
        assert watchlist[0].stock_code == "000001"

    def test_change_group(self, manager):
        """测试修改分组"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        result = manager.change_group("000001", "中线")
        assert result == True

        watchlist = manager.list("中线")
        assert len(watchlist) == 1

    def test_get_groups(self, manager):
        """测试获取分组"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        manager.add("600036", "招商银行", 35.20, "价值投资", "中线")

        groups = manager.get_groups()
        assert "短线" in groups
        assert "中线" in groups

    def test_format_list(self, manager):
        """测试格式化输出"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")

        output = manager.format_list()
        assert "000001" in output
        assert "平安银行" in output
        assert "短线" in output
