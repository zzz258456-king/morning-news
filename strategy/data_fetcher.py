"""
数据获取模块
通过 akshare 获取 A 股涨停板数据，通过直连 API 获取日线数据
支持本地缓存避免重复请求，绕过 Windows 代理
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd
import requests

from config import RAW_DATA_DIR, BACKTEST_START_DATE, BACKTEST_END_DATE

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = RAW_DATA_DIR / "backtest_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 绕过 Windows 系统代理（127.0.0.1:7890）
# 创建独立的无代理会话，不继承系统代理设置
_http = requests.Session()
_http.trust_env = False
_http.proxies = {"http": None, "https": None}
# 设置超时和重试
_adapter = requests.adapters.HTTPAdapter(
    max_retries=requests.urllib3.Retry(total=2, backoff_factor=0.5)
)
_http.mount("https://", _adapter)
_http.mount("http://", _adapter)


# ============================================================
# 涨停板数据（通过 akshare，该接口不受代理影响）
# ============================================================

def fetch_zt_pool(date: str) -> pd.DataFrame:
    """
    获取指定日期涨停板池

    Args:
        date: 日期 YYYYMMDD

    Returns:
        DataFrame 含涨停股票明细
    """
    cache_file = CACHE_DIR / f"zt_pool_{date}.parquet"
    if cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
            logger.info(f"缓存命中: {date} 涨停池 ({len(df)} 条)")
            return df
        except Exception:
            pass

    try:
        df = ak.stock_zt_pool_em(date=date)
        if df is not None and not df.empty:
            df = _standardize_zt_columns(df)
            df["日期"] = date
            try:
                df.to_parquet(cache_file, index=False)
            except Exception:
                pass
            logger.info(f"获取涨停池 [{date}]: {len(df)} 条")
            return df
    except Exception as e:
        logger.warning(f"获取涨停池失败 [{date}]: {e}")

    return pd.DataFrame()


def fetch_zt_pool_range(start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取日期范围内所有涨停板数据
    """
    trade_dates = _get_trade_dates(start_date, end_date)
    all_dfs = []
    for date in trade_dates:
        df = fetch_zt_pool(date)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        logger.warning("未获取到任何涨停板数据")
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"涨停板汇总: {len(result)} 条 ({len(trade_dates)} 个交易日)")
    return result


def _standardize_zt_columns(df: pd.DataFrame) -> pd.DataFrame:
    """标准化涨停板列名"""
    rename_map = {
        "序号": "序号", "代码": "代码", "名称": "名称",
        "涨跌幅": "涨跌幅", "最新价": "最新价",
        "成交额": "成交额", "流通市值": "流通市值",
        "总市值": "总市值", "封板资金": "封单额",
        "换手率": "换手率",
        "首次封板时间": "首次封板", "最后封板时间": "最后封板",
        "炸板次数": "炸板次数", "连板数": "连板数",
        "涨停统计": "涨停统计", "所属行业": "所属行业",
    }
    rename_actual = {k: v for k, v in rename_map.items() if k in df.columns}
    return df.rename(columns=rename_actual)


# ============================================================
# 个股日线数据（绕过代理直连 API）
# ============================================================

_HIST_API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_HIST_PARAMS = {
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
    "ut": "7eea3edcaed734bea9cbfc24409ed989",
}


def _fetch_kline_api(symbol: str, period: str, start: str, end: str, adjust: str) -> Optional[list]:
    """
    通过东方财富直连 API 获取 K 线数据（绕过系统代理）

    Returns:
        klines list 或 None
    """
    market_code = "1" if symbol.startswith("6") else "0"
    adj_map = {"qfq": "1", "hfq": "2", "": "0"}
    period_map = {"daily": "101", "weekly": "102", "monthly": "103"}

    params = dict(_HIST_PARAMS)
    params.update({
        "klt": period_map.get(period, "101"),
        "fqt": adj_map.get(adjust, "0"),
        "secid": f"{market_code}.{symbol}",
        "beg": start,
        "end": end,
    })

    for attempt in range(3):
        try:
            resp = _http.get(_HIST_API, params=params, timeout=10)
            if resp.status_code != 200:
                logger.debug(f"K线API HTTP {resp.status_code} [{symbol}]")
                return None
            data = resp.json()
            if data and data.get("data") and data["data"].get("klines"):
                return data["data"]["klines"]
            return None
        except requests.exceptions.ProxyError:
            logger.debug(f"代理拦截 [{symbol}]，尝试直连...")
            # 最终方案：直接使用 socket 绕过代理
            try:
                resp = requests.get(_HIST_API, params=params,
                                    proxies={"http": None, "https": None},
                                    timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and data.get("data") and data["data"].get("klines"):
                        return data["data"]["klines"]
            except Exception:
                pass
            return None
        except Exception as e:
            logger.debug(f"K线API异常 [{symbol}]: {e}")
            if attempt < 2:
                continue
            return None
    return None


def fetch_daily_data(
    symbol: str,
    start_date: str = BACKTEST_START_DATE,
    end_date: str = BACKTEST_END_DATE,
) -> pd.DataFrame:
    """
    获取个股日线行情（前复权），使用直连 API 绕过代理

    Args:
        symbol: 股票代码（如 000001）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        日线 DataFrame
    """
    code = symbol.zfill(6)
    cache_file = CACHE_DIR / f"daily_{code}_{start_date}_{end_date}.parquet"
    if cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
            if len(df) > 0:
                return df
        except Exception:
            pass

    klines = _fetch_kline_api(code, "daily", start_date, end_date, "qfq")
    if not klines:
        return pd.DataFrame()

    rows = []
    for item in klines:
        parts = item.split(",")
        if len(parts) >= 11:
            rows.append({
                "日期": parts[0],
                "开盘": float(parts[1]),
                "收盘": float(parts[2]),
                "最高": float(parts[3]),
                "最低": float(parts[4]),
                "成交量": int(parts[5]) if parts[5] else 0,
                "成交额": float(parts[6]) if parts[6] else 0,
                "振幅": float(parts[7]) if parts[7] else 0,
                "涨跌幅": float(parts[8]) if parts[8] else 0,
                "涨跌额": float(parts[9]) if parts[9] else 0,
                "换手率": float(parts[10]) if parts[10] else 0,
                "代码": code,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 日期排序
    df["日期"] = df["日期"].astype(str)
    df = df.sort_values("日期").reset_index(drop=True)
    try:
        df.to_parquet(cache_file, index=False)
    except Exception:
        pass
    return df


# ============================================================
# 市场情绪数据
# ============================================================

def fetch_market_overview(date: str) -> dict:
    """获取当日市场概览"""
    try:
        df = ak.stock_market_activity_em()
        if df is not None and not df.empty:
            row = df.iloc[0]
            up = int(row.get("上涨家数", 0))
            down = int(row.get("下跌家数", 0))
            return {
                "上涨": up, "下跌": down,
                "涨停": int(row.get("涨停家数", 0)),
                "跌停": int(row.get("跌停家数", 0)),
                "赚钱效应": round(up / max(up + down, 1) * 100, 1),
            }
    except Exception as e:
        logger.debug(f"获取市场概览失败: {e}")
    return {}


# ============================================================
# 交易日历
# ============================================================

def _get_trade_dates(start_date: str, end_date: str) -> list[str]:
    """获取指定范围内的交易日列表"""
    try:
        df = ak.tool_trade_date_hist_sina()
        if df is not None and "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d")
            mask = (df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)
            if "is_trading_day" in df.columns:
                mask = mask & (df["is_trading_day"] == 1)
            return sorted(df[mask]["trade_date"].tolist())
    except Exception as e:
        logger.warning(f"获取交易日历失败: {e}")

    # 兜底：按周一到周五生成
    dates = []
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    d = start
    while d <= end:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return dates


# ============================================================
# 连板识别
# ============================================================

def tag_consecutive_boards(zt_df: pd.DataFrame) -> pd.DataFrame:
    """标注连板数"""
    if zt_df.empty or "代码" not in zt_df.columns:
        return zt_df
    df = zt_df.copy().sort_values(["代码", "日期"])
    df["连板数"] = 1
    for code, group in df.groupby("代码"):
        dates = sorted(group["日期"].unique())
        for i in range(1, len(dates)):
            prev = datetime.strptime(dates[i - 1], "%Y%m%d")
            curr = datetime.strptime(dates[i], "%Y%m%d")
            gap = (curr - prev).days
            if gap == 1 or (gap == 3 and curr.weekday() == 0):
                mask = (df["代码"] == code) & (df["日期"] == dates[i])
                prev_mask = (df["代码"] == code) & (df["日期"] == dates[i - 1])
                if prev_mask.any():
                    df.loc[mask, "连板数"] = df.loc[prev_mask, "连板数"].iloc[0] + 1
    return df


# ============================================================
# 工具
# ============================================================

def clear_cache(older_than_hours: int = 24):
    """清理过期缓存"""
    now = datetime.now()
    for f in CACHE_DIR.glob("*.parquet"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if (now - mtime).total_seconds() > older_than_hours * 3600:
                f.unlink()
        except Exception:
            pass


def get_today_str() -> str:
    return datetime.now().strftime("%Y%m%d")
