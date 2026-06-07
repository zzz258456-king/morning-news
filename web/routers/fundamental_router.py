"""
基本面分析路由
/api/fundamental/*
"""
from fastapi import APIRouter, HTTPException

from web.services.fundamental_service import get_fundamental_score, get_intraday_data

router = APIRouter(prefix="/api/fundamental", tags=["基本面分析"])


@router.get("/stock/{code}/intraday")
def stock_intraday(code: str):
    """
    获取个股分时数据

    注意：此路由必须在 /{code} 之前注册，否则会被 /{code} 捕获
    """
    result = get_intraday_data(code)
    if not result.get("points"):
        raise HTTPException(status_code=404, detail=f"未找到 {code} 的分时数据")
    return result


@router.get("/{code}")
def fundamental_score(code: str):
    """获取个股基本面评分"""
    result = get_fundamental_score(code)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未找到 {code} 的基本面数据")
    return result
