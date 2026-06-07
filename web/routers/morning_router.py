"""
晨报路由
/api/morning/*
"""
from fastapi import APIRouter

from web.services.morning_service import get_morning_data

router = APIRouter(prefix="/api/morning", tags=["晨报"])


@router.get("/today")
def morning_today():
    """获取今日晨报数据"""
    return get_morning_data()


@router.get("/{date}")
def morning_by_date(date: str):
    """
    获取指定日期的晨报数据

    Args:
        date: 日期，支持 YYYYMMDD 或 YYYY-MM-DD 格式
    """
    return get_morning_data(date)
