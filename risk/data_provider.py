"""
风险预警 - 数据获取模块
从 akshare 获取市场数据：涨跌家数、北向资金、指数行情
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config import RAW_DATA_DIR

logger = logging.getLogger(__name__)

RISK_CACHE_DIR = RAW_DATA_DIR / "risk_cache"
RISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_advance_decline(date: Optional[str] = None) -> dict:
    """
    获取全市场涨跌家数

    返回:
        {"上涨": int, "下跌": int, "平盘": int,
         "总数": int, "涨跌比%": float, "日期": str}
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    try:
        import akshare as ak
        df = ak.stock_market_activity_em()
        if df is not None and not df.empty:
            row = df.iloc[0]
            up = int(row.get("上涨家数", 0))
            down = int(row.get("下跌家数", 0))
            flat = int(row.get("平盘家数", 0))
            total = up + down + flat
            ratio = round(up / max(total, 1) * 100, 2)
            return {
                "上涨": up, "下跌": down, "平盘": flat,
                "总数": total, "涨跌比%": ratio, "日期": date,
            }
    except Exception as e:
        logger.warning(f"涨跌家数获取失败 [{date}]: {e}")

    # 兜底：akshare 实时行情统计
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        up = int((df["涨跌幅"] > 0).sum())
        down = int((df["涨跌幅"] < 0).sum())
        flat = int((df["涨跌幅"] == 0).sum())
        total = up + down + flat
        ratio = round(up / max(total, 1) * 100, 2)
        return {
            "上涨": up, "下跌": down, "平盘": flat,
            "总数": total, "涨跌比%": ratio, "日期": date,
        }
    except Exception as e:
        logger.warning(f"实时行情涨跌统计失败: {e}")

    return {}


def fetch_northbound_flow(date: Optional[str] = None) -> dict:
    """
    获取北向资金（沪股通+深股通）当日净流入

    返回:
        {"沪股通": float, "深股通": float, "合计": float, "日期": str}
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            sh = float(latest.get("沪股通_净流入", 0))
            sz = float(latest.get("深股通_净流入", 0))
            total = sh + sz
            return {
                "沪股通": round(sh, 2),
                "深股通": round(sz, 2),
                "合计": round(total, 2),
                "日期": str(latest.get("date", date))[:10],
            }
    except Exception as e:
        logger.warning(f"北向资金获取失败: {e}")

    # 备用接口
    try:
        import akshare as ak
        df = ak.stock_hsgt_summary_em()
        latest = df.iloc[-1]
        sh = float(latest.get("沪股通_净流入", 0))
        sz = float(latest.get("深股通_净流入", 0))
        return {
            "沪股通": round(sh, 2),
            "深股通": round(sz, 2),
            "合计": round(sh + sz, 2),
            "日期": str(latest.get("日期", date))[:10],
        }
    except Exception as e:
        logger.warning(f"北向备用接口失败: {e}")

    return {}


def fetch_index_data(code: str = "000001",
                     start_date: str = "20250101",
                     end_date: str = "") -> pd.DataFrame:
    """
    获取指数日线数据（用于计算均线偏离度）

    Args:
        code: 指数代码，000001=上证指数
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期，默认今天

    Returns:
        DataFrame: 日期, 收盘, 20日均线, 60日均线
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    cache_file = RISK_CACHE_DIR / f"index_{code}_{start_date}_{end_date}.parquet"
    if cache_file.exists():
        try:
            return pd.read_parquet(cache_file)
        except Exception:
            pass

    try:
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol=f"sh{code}")
        if df is None or df.empty:
            return pd.DataFrame()

        df["日期"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d")
        df = df.sort_values("日期").reset_index(drop=True)
        df["20日均线"] = df["close"].rolling(20).mean()
        df["60日均线"] = df["close"].rolling(60).mean()

        mask = (df["日期"] >= start_date) & (df["日期"] <= end_date)
        result = df[mask][["日期", "close", "20日均线", "60日均线"]].copy()
        result.columns = ["日期", "收盘", "20日均线", "60日均线"]

        try:
            result.to_parquet(cache_file, index=False)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.warning(f"指数数据获取失败 [{code}]: {e}")

    return pd.DataFrame()


def calc_index_deviation(index_df: pd.DataFrame) -> dict:
    """
    计算指数相对于20日/60日均线的偏离度

    Returns:
        {"收盘": float, "20日偏离%": float, "60日偏离%": float, "日期": str}
    """
    if index_df.empty or len(index_df) < 60:
        return {}

    latest = index_df.iloc[-1]
    close = float(latest["收盘"])
    ma20 = float(latest["20日均线"])
    ma60 = float(latest["60日均线"])

    return {
        "收盘": close,
        "20日偏离%": round((close / ma20 - 1) * 100, 2) if ma20 > 0 else 0,
        "60日偏离%": round((close / ma60 - 1) * 100, 2) if ma60 > 0 else 0,
        "日期": str(latest["日期"]),
    }
