"""
历史记录路由
/api/history/*
"""
from fastapi import APIRouter

from web.services.history_service import get_calendar_data, get_day_detail

router = APIRouter(prefix="/api/history", tags=["历史记录"])


@router.get("/calendar/{year}/{month}")
def calendar_data(year: int, month: int):
    """
    获取指定年月的日历数据

    Args:
        year: 年份
        month: 月份
    """
    return get_calendar_data(year, month)


@router.get("/{date}")
def day_detail(date: str):
    """
    获取指定日期的详细信息

    Args:
        date: 日期 YYYY-MM-DD 或 YYYYMMDD
    """
    return get_day_detail(date)
