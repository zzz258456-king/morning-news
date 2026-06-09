# morning/trade_journal.py
"""
操作日志模块
记录交易操作，支持复盘分析
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from collections import Counter
from .db_manager import DBManager, TradeRecord

logger = logging.getLogger(__name__)


@dataclass
class TradeStats:
    """交易统计"""
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_loss_ratio: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0


@dataclass
class EmotionStats:
    """情绪统计"""
    emotion: str
    count: int
    win_count: int
    win_rate: float


@dataclass
class TagStats:
    """标签统计"""
    tag: str
    count: int
    win_count: int
    win_rate: float


class TradeJournal:
    """操作日志管理器"""

    def __init__(self, db_manager: DBManager, config: dict = None):
        self.db_manager = db_manager
        self.config = config or {}
        self.emotion_tags = self.config.get("emotion_tags", ["自信", "犹豫", "恐惧", "贪婪", "平静"])
        self.trade_tags = self.config.get("trade_tags", ["技术面", "基本面", "消息面", "资金面"])

    def record_buy(self, stock_code: str, stock_name: str,
                   price: float, quantity: int, reason: str,
                   emotion: str = "", tags: list = None) -> bool:
        """记录买入操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="BUY",
                stock_code=stock_code,
                stock_name=stock_name,
                price=price,
                quantity=quantity,
                reason=reason,
                emotion=emotion,
                tags=tags or []
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录买入: {stock_code} {stock_name} @ {price} x {quantity}")
            return True
        except Exception as e:
            logger.error(f"记录买入失败: {e}")
            return False

    def record_sell(self, stock_code: str, stock_name: str,
                    price: float, quantity: int, reason: str,
                    emotion: str = "", tags: list = None,
                    profit_loss: float = 0.0) -> bool:
        """记录卖出操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="SELL",
                stock_code=stock_code,
                stock_name=stock_name,
                price=price,
                quantity=quantity,
                reason=reason,
                emotion=emotion,
                tags=tags or [],
                profit_loss=profit_loss
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录卖出: {stock_code} {stock_name} @ {price} x {quantity}")
            return True
        except Exception as e:
            logger.error(f"记录卖出失败: {e}")
            return False

    def record_watch(self, stock_code: str, reason: str) -> bool:
        """记录关注操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="WATCH",
                stock_code=stock_code,
                reason=reason
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录关注: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"记录关注失败: {e}")
            return False

    def record_unwatch(self, stock_code: str) -> bool:
        """记录取消关注操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="UNWATCH",
                stock_code=stock_code
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录取消关注: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"记录取消关注失败: {e}")
            return False

    def record_note(self, stock_code: str, notes: str) -> bool:
        """记录备注"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="NOTE",
                stock_code=stock_code,
                notes=notes
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录备注: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"记录备注失败: {e}")
            return False

    def get_records(self, days: int = 30) -> list:
        """获取操作记录"""
        return self.db_manager.get_trade_records(days)

    def calculate_stats(self, days: int = 30) -> TradeStats:
        """计算交易统计"""
        records = self.get_records(days)

        # 筛选卖出记录
        sell_records = [r for r in records if r.trade_type == "SELL"]

        if not sell_records:
            return TradeStats()

        # 计算统计
        profits = [r.profit_loss for r in sell_records if r.profit_loss > 0]
        losses = [r.profit_loss for r in sell_records if r.profit_loss < 0]

        win_count = len(profits)
        loss_count = len(losses)
        total_trades = len(sell_records)

        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        return TradeStats(
            total_trades=total_trades,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_count / total_trades if total_trades > 0 else 0,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_loss_ratio=abs(avg_profit / avg_loss) if avg_loss != 0 else 0,
            max_profit=max(profits) if profits else 0,
            max_loss=min(losses) if losses else 0
        )

    def calculate_emotion_stats(self, days: int = 30) -> list:
        """计算情绪统计"""
        records = self.get_records(days)
        sell_records = [r for r in records if r.trade_type == "SELL" and r.emotion]

        emotion_data = {}
        for record in sell_records:
            if record.emotion not in emotion_data:
                emotion_data[record.emotion] = {"count": 0, "win_count": 0}
            emotion_data[record.emotion]["count"] += 1
            if record.profit_loss > 0:
                emotion_data[record.emotion]["win_count"] += 1

        return [
            EmotionStats(
                emotion=emotion,
                count=data["count"],
                win_count=data["win_count"],
                win_rate=data["win_count"] / data["count"] if data["count"] > 0 else 0
            )
            for emotion, data in emotion_data.items()
        ]

    def calculate_tag_stats(self, days: int = 30) -> list:
        """计算标签统计"""
        records = self.get_records(days)
        sell_records = [r for r in records if r.trade_type == "SELL" and r.tags]

        tag_data = {}
        for record in sell_records:
            for tag in record.tags:
                if tag not in tag_data:
                    tag_data[tag] = {"count": 0, "win_count": 0}
                tag_data[tag]["count"] += 1
                if record.profit_loss > 0:
                    tag_data[tag]["win_count"] += 1

        return [
            TagStats(
                tag=tag,
                count=data["count"],
                win_count=data["win_count"],
                win_rate=data["win_count"] / data["count"] if data["count"] > 0 else 0
            )
            for tag, data in tag_data.items()
        ]

    def generate_review_report(self, days: int = 30) -> str:
        """生成复盘报告"""
        stats = self.calculate_stats(days)
        emotion_stats = self.calculate_emotion_stats(days)
        tag_stats = self.calculate_tag_stats(days)
        records = self.get_records(days)

        lines = [
            f"📊 操作复盘报告 (最近{days}天)",
            "",
            "═" * 40,
            "【交易统计】",
            "═" * 40,
            f"总交易次数：{stats.total_trades}",
            f"盈利次数：{stats.win_count}",
            f"亏损次数：{stats.loss_count}",
            f"胜率：{stats.win_rate:.1%}",
            f"平均盈利：{stats.avg_profit:+.2%}",
            f"平均亏损：{stats.avg_loss:+.2%}",
            f"盈亏比：{stats.profit_loss_ratio:.2f}",
            f"最大单笔盈利：{stats.max_profit:+.2%}",
            f"最大单笔亏损：{stats.max_loss:+.2%}",
            "",
            "═" * 40,
            "【情绪分析】",
            "═" * 40,
        ]

        for emotion_stat in emotion_stats:
            lines.append(f"{emotion_stat.emotion}时交易：{emotion_stat.count}次，胜率{emotion_stat.win_rate:.1%}")

        lines.extend([
            "",
            "═" * 40,
            "【标签分析】",
            "═" * 40,
        ])

        for tag_stat in tag_stats:
            lines.append(f"{tag_stat.tag}交易：{tag_stat.count}次，胜率{tag_stat.win_rate:.1%}")

        lines.extend([
            "",
            "═" * 40,
            "【操作明细】",
            "═" * 40,
        ])

        for record in records[:20]:  # 只显示最近20条
            lines.append(f"{record.trade_date.strftime('%Y-%m-%d %H:%M')}  {record.trade_type:5}  {record.stock_code} {record.stock_name}")
            if record.reason:
                lines.append(f"理由：{record.reason} | 情绪：{record.emotion} | 标签：{', '.join(record.tags)}")
            if record.profit_loss != 0:
                lines.append(f"结果：{record.profit_loss:+.2%}")
            lines.append("")

        return "\n".join(lines)
