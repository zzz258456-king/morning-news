"""
交易记录服务
封装交易记录的 CRUD 和盈亏计算
"""
import logging
from typing import Optional

from web.repositories.trade_repo import TradeRepository

logger = logging.getLogger(__name__)


def create_trade(
    date: str,
    stock_code: str,
    stock_name: str = "",
    action: str = "buy",
    price: float = 0,
    quantity: int = 0,
    reason: str = "",
    reflection: str = "",
    tags: str = "",
) -> Optional[int]:
    """创建交易记录"""
    repo = TradeRepository()
    return repo.create(
        date=date,
        stock_code=stock_code,
        stock_name=stock_name,
        action=action,
        price=price,
        quantity=quantity,
        reason=reason,
        reflection=reflection,
        tags=tags,
    )


def list_trades(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stock_code: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """查询交易记录列表"""
    repo = TradeRepository()
    return repo.list_all(
        start_date=start_date,
        end_date=end_date,
        stock_code=stock_code,
        limit=limit,
        offset=offset,
    )


def get_trade(trade_id: int) -> Optional[dict]:
    """获取单条交易记录"""
    repo = TradeRepository()
    return repo.get_by_id(trade_id)


def update_trade(trade_id: int, **kwargs) -> bool:
    """更新交易记录"""
    repo = TradeRepository()
    return repo.update(trade_id, **kwargs)


def delete_trade(trade_id: int) -> bool:
    """删除交易记录"""
    repo = TradeRepository()
    return repo.delete(trade_id)


def calc_daily_pnl(date: Optional[str] = None) -> dict:
    """
    计算指定日期的交易盈亏

    Args:
        date: 日期，None 则计算所有交易

    Returns:
        盈亏统计字典
    """
    repo = TradeRepository()
    trades = repo.list_all(start_date=date, end_date=date) if date else repo.list_all(limit=10000)

    total_buy_amount = 0.0
    total_sell_amount = 0.0
    buy_count = 0
    sell_count = 0

    for t in trades:
        amount = t.get("price", 0) * t.get("quantity", 0)
        if t.get("action") == "buy":
            total_buy_amount += amount
            buy_count += 1
        elif t.get("action") == "sell":
            total_sell_amount += amount
            sell_count += 1

    pnl = total_sell_amount - total_buy_amount

    return {
        "date": date or "all",
        "total_buy_amount": round(total_buy_amount, 2),
        "total_sell_amount": round(total_sell_amount, 2),
        "pnl": round(pnl, 2),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "trade_count": len(trades),
    }
