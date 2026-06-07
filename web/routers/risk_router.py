"""
风险预警路由
/api/risk/*
"""
from fastapi import APIRouter

from web.services.risk_service import get_risk_assessment

router = APIRouter(prefix="/api/risk", tags=["风险预警"])


@router.get("/today")
def risk_today():
    """获取今日风险评估"""
    return get_risk_assessment()
