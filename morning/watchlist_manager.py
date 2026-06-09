# morning/watchlist_manager.py
"""
特别关注模块
管理特别关注的股票列表
"""
import logging
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass
from .db_manager import DBManager, WatchlistItem

logger = logging.getLogger(__name__)


class WatchlistManager:
    """特别关注管理器"""

    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager

    def add(self, stock_code: str, stock_name: str,
            price: float, reason: str, group_name: str = "默认") -> bool:
        """添加特别关注"""
        try:
            self.db_manager.add_watchlist(stock_code, stock_name, price, reason, group_name)
            return True
        except Exception as e:
            logger.error(f"添加特别关注失败: {e}")
            return False

    def remove(self, stock_code: str) -> bool:
        """移除特别关注"""
        try:
            self.db_manager.remove_watchlist(stock_code)
            return True
        except Exception as e:
            logger.error(f"移除特别关注失败: {e}")
            return False

    def list(self, group_name: str = None) -> list:
        """获取特别关注列表"""
        return self.db_manager.get_watchlist(group_name)

    def change_group(self, stock_code: str, new_group: str) -> bool:
        """修改分组"""
        try:
            # 获取当前关注信息
            watchlist = self.db_manager.get_watchlist()
            item = next((w for w in watchlist if w.stock_code == stock_code), None)

            if not item:
                logger.warning(f"未找到关注股票: {stock_code}")
                return False

            # 更新分组
            self.db_manager.add_watchlist(
                item.stock_code,
                item.stock_name,
                item.add_price,
                item.reason,
                new_group
            )

            logger.info(f"修改分组: {stock_code} -> {new_group}")
            return True
        except Exception as e:
            logger.error(f"修改分组失败: {e}")
            return False

    def get_groups(self) -> list:
        """获取所有分组"""
        watchlist = self.list()
        groups = list(set(item.group_name for item in watchlist))
        return sorted(groups)

    def format_list(self, group_name: str = None) -> str:
        """格式化输出关注列表"""
        watchlist = self.list(group_name)

        if not watchlist:
            return "暂无特别关注股票"

        lines = ["📊 特别关注列表", ""]

        # 按分组组织
        groups = {}
        for item in watchlist:
            if item.group_name not in groups:
                groups[item.group_name] = []
            groups[item.group_name].append(item)

        for group_name, items in groups.items():
            lines.append(f"【{group_name}】")
            for item in items:
                lines.append(f"  {item.stock_code} {item.stock_name}")
                lines.append(f"    关注日期: {item.add_date}")
                lines.append(f"    关注价格: {item.add_price}")
                lines.append(f"    关注理由: {item.reason}")
            lines.append("")

        return "\n".join(lines)
