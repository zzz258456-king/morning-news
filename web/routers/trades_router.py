"""
交易记录路由
/api/trades/*
"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from web.models.schemas import TradeCreate, TradeUpdate
from web.services import trade_service

router = APIRouter(prefix="/api/trades", tags=["交易记录"])


@router.get("")
def list_trades(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stock_code: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """查询交易记录列表"""
    trades = trade_service.list_trades(
        start_date=start_date,
        end_date=end_date,
        stock_code=stock_code,
        limit=limit,
        offset=offset,
    )
    return {"items": trades, "total": len(trades)}


@router.post("")
def create_trade(payload: TradeCreate):
    """创建交易记录"""
    trade_id = trade_service.create_trade(
        date=payload.date,
        stock_code=payload.stock_code,
        stock_name=payload.stock_name,
        action=payload.action,
        price=payload.price,
        quantity=payload.quantity,
        reason=payload.reason,
        reflection=payload.reflection,
        tags=payload.tags,
    )
    if trade_id is None:
        raise HTTPException(status_code=500, detail="创建交易记录失败")
    return {"id": trade_id, "message": "创建成功"}


@router.get("/pnl")
def daily_pnl(date: Optional[str] = None):
    """计算交易盈亏"""
    return trade_service.calc_daily_pnl(date)


@router.get("/{trade_id}")
def get_trade(trade_id: int):
    """获取单条交易记录"""
    trade = trade_service.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"交易记录 {trade_id} 不存在")
    return trade


@router.put("/{trade_id}")
def update_trade(trade_id: int, payload: TradeUpdate):
    """更新交易记录"""
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="未提供更新字段")

    success = trade_service.update_trade(trade_id, **update_data)
    if not success:
        raise HTTPException(status_code=404, detail=f"交易记录 {trade_id} 不存在或更新失败")
    return {"message": "更新成功"}


@router.delete("/{trade_id}")
def delete_trade(trade_id: int):
    """删除交易记录"""
    success = trade_service.delete_trade(trade_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"交易记录 {trade_id} 不存在")
    return {"message": "删除成功"}
