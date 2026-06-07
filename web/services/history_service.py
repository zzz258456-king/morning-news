"""
历史记录服务
提供日历数据和日详情查询
"""
import logging
from datetime import datetime
from typing import Optional

from web.repositories.trade_repo import TradeRepository
from web.repositories.log_repo import LogRepository
from web.repositories.fund_flow_repo import FundFlowRepository
from web.services.morning_service import get_morning_data

logger = logging.getLogger(__name__)


def get_calendar_data(year: int, month: int) -> dict:
    """
    获取指定年月的日历数据

    Args:
        year: 年份
        month: 月份

    Returns:
        日历数据字典
    """
    trade_repo = TradeRepository()
    log_repo = LogRepository()

    # 获取有数据的日期
    log_dates = log_repo.list_dates_with_logs(year, month)

    # 计算本月每天的统计数据
    days = []
    import calendar
    _, num_days = calendar.monthrange(year, month)

    for day in range(1, num_days + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        dt = datetime(year, month, day)

        # 跳过周末
        if dt.weekday() >= 5:
            continue

        # 查询该日交易
        trades = trade_repo.list_by_date(date_str)
        trade_count = len(trades)

        # 计算盈亏
        pnl = 0.0
        for t in trades:
            amount = t.get("price", 0) * t.get("quantity", 0)
            if t.get("action") == "sell":
                pnl += amount
            elif t.get("action") == "buy":
                pnl -= amount

        # 检查是否有晨报
        has_morning = log_repo.has_morning_for_date(date_str)

        # 确定日志类型
        log_type = ""
        if date_str in log_dates:
            logs = log_repo.list_by_date(date_str)
            if logs:
                log_type = logs[0].get("log_type", "")

        days.append({
            "date": date_str,
            "has_data": trade_count > 0 or has_morning,
            "trade_count": trade_count,
            "pnl": round(pnl, 2),
            "sentiment": "",
            "log_type": log_type,
        })

    return {
        "year": year,
        "month": month,
        "days": days,
    }


def get_day_detail(date: str) -> dict:
    """
    获取指定日期的详细信息

    Args:
        date: 日期 YYYY-MM-DD 或 YYYYMMDD

    Returns:
        日详情字典
    """
    # 统一日期格式
    date_clean = date.replace("-", "")
    date_fmt = f"{date_clean[:4]}-{date_clean[4:6]}-{date_clean[6:8]}" if len(date_clean) == 8 else date

    trade_repo = TradeRepository()
    log_repo = LogRepository()
    fund_flow_repo = FundFlowRepository()

    # 交易记录
    trades = trade_repo.list_by_date(date_fmt)

    # 日志
    logs = log_repo.list_by_date(date_fmt)

    # 资金流向
    fund_flow_raw = fund_flow_repo.query(date_fmt)
    fund_flow_items = []
    for ff in fund_flow_raw:
        fund_flow_items.append({
            "sector_name": ff.get("sector_name", ""),
            "sector_type": ff.get("sector_type", "industry"),
            "main_net_inflow": ff.get("main_net_inflow", 0),
            "retail_net_inflow": ff.get("retail_net_inflow", 0),
            "super_large_inflow": ff.get("super_large_inflow", 0),
            "large_inflow": ff.get("large_inflow", 0),
            "medium_inflow": ff.get("medium_inflow", 0),
            "small_inflow": ff.get("small_inflow", 0),
            "rank": ff.get("rank", 0),
        })

    # 晨报数据
    morning = get_morning_data(date_clean)

    return {
        "date": date_fmt,
        "trades": trades,
        "logs": logs,
        "fund_flow": fund_flow_items,
        "morning": morning if morning.get("available") else None,
    }
