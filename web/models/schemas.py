"""
Pydantic 数据模型
定义所有 API 的请求和响应模型
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# 交易记录模型
# ============================================================

class TradeCreate(BaseModel):
    """创建交易记录请求"""
    date: str = Field(..., description="交易日期 YYYY-MM-DD")
    stock_code: str = Field(..., description="股票代码")
    stock_name: str = Field(default="", description="股票名称")
    action: str = Field(..., description="操作: buy/sell")
    price: float = Field(..., gt=0, description="价格")
    quantity: int = Field(..., gt=0, description="数量")
    reason: str = Field(default="", description="交易理由")
    reflection: str = Field(default="", description="交易反思")
    tags: str = Field(default="", description="标签，逗号分隔")


class TradeUpdate(BaseModel):
    """更新交易记录请求"""
    date: Optional[str] = Field(None, description="交易日期")
    stock_code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    action: Optional[str] = Field(None, description="操作: buy/sell")
    price: Optional[float] = Field(None, gt=0, description="价格")
    quantity: Optional[int] = Field(None, gt=0, description="数量")
    reason: Optional[str] = Field(None, description="交易理由")
    reflection: Optional[str] = Field(None, description="交易反思")
    tags: Optional[str] = Field(None, description="标签")


class TradeResponse(BaseModel):
    """交易记录响应"""
    id: int
    date: str
    stock_code: str
    stock_name: str
    action: str
    price: float
    quantity: int
    reason: str
    reflection: str
    tags: str
    created_at: str
    updated_at: str


# ============================================================
# 晨报模型
# ============================================================

class StockMention(BaseModel):
    """股票提及"""
    code: str = ""
    name: str = ""
    reason: str = ""
    sector: str = ""
    strength: int = 0


class MorningResponse(BaseModel):
    """晨报数据响应"""
    date: str = ""
    sentiment: str = "中性"
    top_picks: list[dict] = Field(default_factory=list)
    good_sectors: list[str] = Field(default_factory=list)
    bad_sectors: list[str] = Field(default_factory=list)
    stock_mentions: list[dict] = Field(default_factory=list)
    key_events: list[str] = Field(default_factory=list)
    available: bool = False


# ============================================================
# 风险预警模型
# ============================================================

class DimensionDetail(BaseModel):
    """风险维度详情"""
    score: float = 0.0
    reason: str = ""
    value: str = ""


class RiskResponse(BaseModel):
    """风险预警响应"""
    total_score: float = 0.0
    level: str = "低风险"
    suggestion: str = ""
    dimensions: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


# ============================================================
# 基本面分析模型
# ============================================================

class FundamentalDimension(BaseModel):
    """基本面维度评分"""
    score: float = 0.0
    desc: str = ""
    hl: str = ""


class FundamentalResponse(BaseModel):
    """基本面评分响应"""
    code: str = ""
    name: str = ""
    total: int = 0
    dimensions: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class IntradayPoint(BaseModel):
    """分时数据点"""
    time: str
    price: float
    volume: float = 0
    avg_price: float = 0


class IntradayResponse(BaseModel):
    """分时数据响应"""
    code: str = ""
    name: str = ""
    points: list[IntradayPoint] = Field(default_factory=list)
    prev_close: float = 0.0


# ============================================================
# 资金流向模型
# ============================================================

class FundFlowItem(BaseModel):
    """资金流向条目"""
    sector_name: str = ""
    sector_type: str = "industry"
    main_net_inflow: float = 0.0
    retail_net_inflow: float = 0.0
    super_large_inflow: float = 0.0
    large_inflow: float = 0.0
    medium_inflow: float = 0.0
    small_inflow: float = 0.0
    rank: int = 0


class FundFlowResponse(BaseModel):
    """资金流向响应"""
    date: str = ""
    items: list[FundFlowItem] = Field(default_factory=list)
    total: int = 0


# ============================================================
# 历史记录模型
# ============================================================

class CalendarDay(BaseModel):
    """日历日数据"""
    date: str = ""
    has_data: bool = False
    trade_count: int = 0
    pnl: float = 0.0
    sentiment: str = ""
    log_type: str = ""


class CalendarResponse(BaseModel):
    """日历数据响应"""
    year: int = 0
    month: int = 0
    days: list[CalendarDay] = Field(default_factory=list)


class DayDetailResponse(BaseModel):
    """日详情响应"""
    date: str = ""
    trades: list[TradeResponse] = Field(default_factory=list)
    logs: list[dict] = Field(default_factory=list)
    fund_flow: list[FundFlowItem] = Field(default_factory=list)
    morning: Optional[MorningResponse] = None
