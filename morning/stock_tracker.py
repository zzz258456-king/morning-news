"""
晚间回溯模块
跟踪推荐股票和特别关注股票的行情
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import akshare as ak
import pandas as pd
from .db_manager import DBManager, WatchlistItem

logger = logging.getLogger(__name__)


@dataclass
class StockTrackingInfo:
    """股票跟踪信息"""
    stock_code: str
    stock_name: str
    is_watchlist: bool  # 是否特别关注
    recommend_date: date
    recommend_price: float
    current_price: float
    change_pct: float
    tracking_days: int
    history_data: list  # 历史行情数据


class StockTracker:
    """股票跟踪器"""

    def __init__(self, db_manager: DBManager, config: dict = None):
        self.db_manager = db_manager
        self.config = config or {}
        self.default_tracking_days = self.config.get("tracking_days", 5)

    def fetch_stock_history(self, stock_code: str, days: int = 5) -> pd.DataFrame:
        """获取股票历史行情"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days + 5)  # 多取几天以确保有足够的交易日

            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"  # 前复权
            )

            if df is not None and len(df) > 0:
                # 标准化列名
                df = df.rename(columns={
                    "日期": "trade_date",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "换手率": "turnover_rate",
                    "涨跌幅": "change_pct"
                })
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取股票历史行情失败 {stock_code}: {e}")
            return pd.DataFrame()

    def get_tracking_stocks(self, days: int = None) -> list:
        """获取需要跟踪的股票列表"""
        if days is None:
            days = self.default_tracking_days

        tracking_stocks = []

        # 1. 获取推荐记录
        recommendations = self.db_manager.get_recommendations(days)
        for rec in recommendations:
            tracking_stocks.append({
                "stock_code": rec["stock_code"],
                "stock_name": rec["stock_name"],
                "is_watchlist": False,
                "recommend_date": rec["recommend_date"],
                "recommend_price": rec["recommend_price"],
                "tracking_days": days
            })

        # 2. 获取特别关注股票
        watchlist = self.db_manager.get_watchlist()
        for item in watchlist:
            # 检查是否已经在推荐记录中
            if not any(s["stock_code"] == item.stock_code for s in tracking_stocks):
                tracking_stocks.append({
                    "stock_code": item.stock_code,
                    "stock_name": item.stock_name,
                    "is_watchlist": True,
                    "recommend_date": item.add_date,
                    "recommend_price": item.add_price,
                    "tracking_days": item.tracking_days if item.tracking_days > 0 else days
                })

        return tracking_stocks

    def track_stocks(self, days: int = None) -> list:
        """跟踪股票行情"""
        if days is None:
            days = self.default_tracking_days

        tracking_stocks = self.get_tracking_stocks(days)
        results = []

        for stock_info in tracking_stocks:
            stock_code = stock_info["stock_code"]
            tracking_days = stock_info["tracking_days"]

            logger.info(f"跟踪股票: {stock_code} {stock_info['stock_name']}")

            # 获取历史行情
            history_df = self.fetch_stock_history(stock_code, tracking_days)

            if history_df.empty:
                logger.warning(f"无法获取股票行情: {stock_code}")
                continue

            # 计算当前价格和涨跌幅
            current_price = history_df.iloc[-1]["close"]
            recommend_price = stock_info["recommend_price"]
            change_pct = (current_price - recommend_price) / recommend_price if recommend_price > 0 else 0

            # 构建历史数据
            history_data = []
            for _, row in history_df.iterrows():
                history_data.append({
                    "trade_date": row["trade_date"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "turnover_rate": row["turnover_rate"],
                    "change_pct": row["change_pct"]
                })

            # 保存跟踪数据到数据库
            today = date.today()
            for data in history_data:
                try:
                    self.db_manager.add_tracking_data(
                        stock_code=stock_code,
                        trade_date=data["trade_date"],
                        open_price=data["open"],
                        high=data["high"],
                        low=data["low"],
                        close=data["close"],
                        volume=data["volume"],
                        turnover_rate=data["turnover_rate"],
                        change_pct=data["change_pct"],
                        target_date=today
                    )
                except Exception as e:
                    logger.warning(f"保存跟踪数据失败 {stock_code} {data['trade_date']}: {e}")

            # 构建跟踪信息
            tracking_info = StockTrackingInfo(
                stock_code=stock_code,
                stock_name=stock_info["stock_name"],
                is_watchlist=stock_info["is_watchlist"],
                recommend_date=stock_info["recommend_date"],
                recommend_price=recommend_price,
                current_price=current_price,
                change_pct=change_pct,
                tracking_days=tracking_days,
                history_data=history_data
            )

            results.append(tracking_info)

        return results

    def generate_report(self, tracking_results: list) -> str:
        """生成跟踪报告"""
        if not tracking_results:
            return "暂无跟踪股票"

        lines = [
            f"📊 推荐股票跟踪报告 ({date.today()})",
            "",
        ]

        # 分离推荐股票和特别关注股票
        recommendations = [r for r in tracking_results if not r.is_watchlist]
        watchlist = [r for r in tracking_results if r.is_watchlist]

        # 推荐股票部分
        if recommendations:
            lines.extend([
                "═" * 40,
                "【推荐股票】",
                "═" * 40,
                ""
            ])

            for info in recommendations:
                lines.extend([
                    f"【{info.stock_code}】{info.stock_name}",
                    f"推荐日期：{info.recommend_date}",
                    f"推荐价格：{info.recommend_price:.2f}",
                    f"当前价格：{info.current_price:.2f}",
                    f"累计涨跌：{info.change_pct:+.2%}",
                    "",
                    f"{info.tracking_days}日行情：",
                    "日期        开盘    最高    最低    收盘    成交量    换手率"
                ])

                for data in info.history_data[-info.tracking_days:]:
                    lines.append(
                        f"{data['trade_date']}  {data['open']:6.2f}  {data['high']:6.2f}  "
                        f"{data['low']:6.2f}  {data['close']:6.2f}  {data['volume']:8.0f}  "
                        f"{data['turnover_rate']:6.2%}"
                    )

                lines.append("")

        # 特别关注股票部分
        if watchlist:
            lines.extend([
                "═" * 40,
                "【特别关注】",
                "═" * 40,
                ""
            ])

            for info in watchlist:
                lines.extend([
                    f"【{info.stock_code}】{info.stock_name}",
                    f"关注日期：{info.recommend_date}",
                    f"关注价格：{info.recommend_price:.2f}",
                    f"当前价格：{info.current_price:.2f}",
                    f"累计涨跌：{info.change_pct:+.2%}",
                    f"跟踪天数：{info.tracking_days}天",
                    "",
                    f"{info.tracking_days}日行情：",
                    "日期        开盘    最高    最低    收盘    成交量    换手率"
                ])

                for data in info.history_data[-info.tracking_days:]:
                    lines.append(
                        f"{data['trade_date']}  {data['open']:6.2f}  {data['high']:6.2f}  "
                        f"{data['low']:6.2f}  {data['close']:6.2f}  {data['volume']:8.0f}  "
                        f"{data['turnover_rate']:6.2%}"
                    )

                lines.append("")

        return "\n".join(lines)
