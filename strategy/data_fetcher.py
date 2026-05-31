"""
数据获取模块 v2
双数据源架构：
  - 涨停板数据：akshare (直接可用，不受代理影响)
  - 日线K线数据：baostock (稳定全量，覆盖5年以上)
  - 交易日历：akshare

缓存策略：
  - 涨停板：按日期缓存 parquet (4小时)
  - 日线：按股票+范围缓存 parquet (永久，除非代码变化)
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd

from config import RAW_DATA_DIR

logger = logging.getLogger(__name__)

CACHE_DIR = RAW_DATA_DIR / "backtest_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ----- baostock 连接池 -----
_bs_connected = False


def _bs_login():
    """延迟登录 baostock"""
    global _bs_connected
    if not _bs_connected:
        import baostock as bs
        lg = bs.login()
        if lg.error_code == "0":
            _bs_connected = True
            logger.debug("baostock 登录成功")
        else:
            raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")


def _bs_logout():
    global _bs_connected
    if _bs_connected:
        import baostock as bs
        bs.logout()
        _bs_connected = False


# ============================================================
# 涨停板数据 — akshare
# ============================================================

def fetch_zt_pool(date: str) -> pd.DataFrame:
    """获取指定日期涨停板池"""
    cache_file = CACHE_DIR / f"zt_{date}.parquet"
    if cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
            if len(df) > 0:
                return df
        except Exception:
            pass

    try:
        df = ak.stock_zt_pool_em(date=date)
        if df is not None and not df.empty:
            df = _standardize_zt(df)
            df["日期"] = date
            try:
                df.to_parquet(cache_file, index=False)
            except Exception:
                pass
            logger.info(f"涨停板 [{date}]: {len(df)} 只")
            return df
    except Exception as e:
        logger.warning(f"涨停板获取失败 [{date}]: {e}")
    return pd.DataFrame()


def fetch_zt_pool_range(start_date: str, end_date: str) -> pd.DataFrame:
    """获取日期范围内所有涨停板数据"""
    trade_dates = get_trade_dates(start_date, end_date)
    dfs = []
    for dt in trade_dates:
        df = fetch_zt_pool(dt)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    result = pd.concat(dfs, ignore_index=True)
    logger.info(f"涨停板汇总: {len(result)} 条 ({len(trade_dates)} 交易日)")
    return result


def _standardize_zt(df: pd.DataFrame) -> pd.DataFrame:
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
    return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})


# ============================================================
# 日线K线数据 — baostock (稳定全量)
# ============================================================

# 将akshare日期YYYYMMDD转为baostock格式 YYYY-MM-DD
def _bs_date(d: str) -> str:
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d


def _code_to_bs(code: str) -> str:
    """将6位代码转为baostock格式：sh.600000 / sz.000001"""
    code = code.zfill(6)
    return f"sh.{code}" if code.startswith("6") else f"sz.{code}"


def fetch_daily_data(
    symbol: str,
    start_date: str = "20260101",
    end_date: str = "",
) -> pd.DataFrame:
    """
    获取个股日线行情（前复权）— 使用 baostock

    Args:
        symbol: 股票代码 (6位)
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD，默认今天

    Returns:
        DataFrame: 日期,开盘,收盘,最高,最低,成交量,成交额,换手率
    """
    code = symbol.zfill(6)
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    cache_file = CACHE_DIR / f"daily_{code}_{start_date}_{end_date}.parquet"
    if cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
            if len(df) > 0:
                return df
        except Exception:
            pass

    try:
        _bs_login()
        import baostock as bs

        bs_code = _code_to_bs(code)
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount,turn",
            start_date=_bs_date(start_date),
            end_date=_bs_date(end_date),
            frequency="d",
            adjustflag="2",  # 前复权
        )

        rows = []
        while rs.next():
            row = rs.get_row_data()
            if row[1] == "":  # 跳过停牌日
                continue
            rows.append({
                "日期": row[0].replace("-", ""),
                "开盘": float(row[1]),
                "收盘": float(row[2]),
                "最高": float(row[3]),
                "最低": float(row[4]),
                "成交量": int(float(row[5])) if row[5] else 0,
                "成交额": float(row[6]) if row[6] else 0,
                "换手率": float(row[7]) if row[7] else 0,
                "代码": code,
            })

        if rows:
            df = pd.DataFrame(rows)
            try:
                df.to_parquet(cache_file, index=False)
            except Exception:
                pass
            return df
    except Exception as e:
        logger.debug(f"baostock日线失败 [{code}]: {e}")

    return pd.DataFrame()


def fetch_batch_daily(
    symbols: list[str],
    start_date: str = "20260101",
    end_date: str = "",
) -> dict[str, pd.DataFrame]:
    """
    批量获取多只股票日线（共享baostock连接）

    Returns:
        {code: DataFrame}
    """
    result = {}
    for code in symbols:
        df = fetch_daily_data(code, start_date, end_date)
        if not df.empty:
            result[code] = df
    return result


# ============================================================
# 交易日历
# ============================================================

_trade_dates_cache: list[str] = []


def get_trade_dates(start_date: str, end_date: str) -> list[str]:
    """获取交易日列表，优先用baostock"""
    global _trade_dates_cache
    try:
        _bs_login()
        import baostock as bs

        rs = bs.query_trade_dates(start_date=_bs_date(start_date),
                                   end_date=_bs_date(end_date))
        dates = []
        while rs.next():
            row = rs.get_row_data()
            if row[1] == "1":  # is_trading_day
                dates.append(row[0].replace("-", ""))
        if dates:
            return sorted(dates)
    except Exception as e:
        logger.debug(f"baostock交易日历失败: {e}")

    # 兜底
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
    """基于日期连续性标注连板数"""
    if zt_df.empty or "代码" not in zt_df.columns:
        return zt_df
    df = zt_df.copy().sort_values(["代码", "日期"])
    df["连板数"] = 1
    for code, grp in df.groupby("代码"):
        dates = sorted(grp["日期"].unique())
        for i in range(1, len(dates)):
            prev = datetime.strptime(dates[i - 1], "%Y%m%d")
            cur = datetime.strptime(dates[i], "%Y%m%d")
            gap = (cur - prev).days
            if gap == 1 or (gap == 3 and cur.weekday() == 0):
                mask = (df["代码"] == code) & (df["日期"] == dates[i])
                prev_mask = (df["代码"] == code) & (df["日期"] == dates[i - 1])
                if prev_mask.any():
                    df.loc[mask, "连板数"] = df.loc[prev_mask, "连板数"].iloc[0] + 1
    return df


# ============================================================
# 市场情绪
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
        logger.debug(f"市场概览失败: {e}")
    return {}


# ============================================================
# 缓存管理
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
