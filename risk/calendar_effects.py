"""
日历效应统计
计算各星期几的历史下跌概率和平均涨跌幅（星期几效应）
数据源：akshare，缓存到本地每周更新一次
"""
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config import RAW_DATA_DIR

logger = logging.getLogger(__name__)

CALENDAR_CACHE_DIR = RAW_DATA_DIR / "risk_cache"
CALENDAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def compute_calendar_effects(
    years: int = 3,
    force_refresh: bool = False,
) -> dict[str, dict]:
    """
    计算星期几效应：过去 N 年各星期几的下跌概率和平均涨跌幅

    结果缓存到本地，每周更新一次

    Returns:
        {
            "周一": {"样本数": N, "下跌概率%": float, "平均涨跌幅%": float},
            "周二": ...,
        }
    """
    cache_file = CALENDAR_CACHE_DIR / "calendar_effects.pkl"

    if not force_refresh and cache_file.exists():
        try:
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if (datetime.now() - mtime).days < 7:  # 一周缓存
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
        except Exception:
            pass

    logger.info("计算日历效应（过去 %d 年）...", years)

    try:
        import akshare as ak

        end = datetime.now()
        start = end - timedelta(days=years * 365)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # 获取上证指数日线
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df is None or df.empty:
            logger.warning("日历效应：获取指数数据失败")
            return {}

        df["日期"] = pd.to_datetime(df["date"])
        df = df[(df["日期"] >= start) & (df["日期"] <= end)].copy()
        df["星期几"] = df["日期"].dt.dayofweek  # 0=周一
        df["涨跌幅%"] = df["close"].pct_change() * 100

        # 按星期几分组统计
        day_names = ["周一", "周二", "周三", "周四", "周五"]
        result = {}
        for dow, name in enumerate(day_names):
            sub = df[df["星期几"] == dow]["涨跌幅%"].dropna()
            if len(sub) == 0:
                continue
            down_prob = (sub < 0).sum() / len(sub) * 100
            result[name] = {
                "样本数": len(sub),
                "下跌概率%": round(down_prob, 1),
                "平均涨跌幅%": round(sub.mean(), 2),
            }

        # 缓存
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(result, f)
        except Exception:
            pass

        return result
    except Exception as e:
        logger.warning(f"日历效应计算失败: {e}")
        return {}
