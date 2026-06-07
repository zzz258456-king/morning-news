"""
资金流向路由
/api/fund-flow/*
"""
from fastapi import APIRouter

from web.services.fund_flow_service import get_fund_flow_data

router = APIRouter(prefix="/api/fund-flow", tags=["资金流向"])


@router.get("/today")
def fund_flow_today():
    """获取今日资金流向数据"""
    items = get_fund_flow_data()
    return {
        "date": "",
        "items": items,
        "total": len(items),
    }


@router.get("/{date}")
def fund_flow_by_date(date: str):
    """
    获取指定日期的资金流向数据

    Args:
        date: 日期 YYYYMMDD 或 YYYY-MM-DD
    """
    items = get_fund_flow_data(date=date)
    return {
        "date": date,
        "items": items,
        "total": len(items),
    }


@router.get("/top/{date}")
def fund_flow_top(date: str, sector_type: str = "industry", limit: int = 10):
    """
    获取指定日期资金流向 Top N

    Args:
        date: 日期
        sector_type: 板块类型
        limit: 返回数量
    """
    items = get_fund_flow_data(date=date, sector_type=sector_type, top_n=limit)
    return {
        "date": date,
        "items": items,
        "total": len(items),
    }
