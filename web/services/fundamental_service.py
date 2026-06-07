"""
基本面分析服务
封装 morning.fundamental_analyzer 和 akshare 分时数据
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_fundamental_score(code: str) -> Optional[dict]:
    """
    获取个股基本面评分

    Args:
        code: 股票代码（如 "600519"）

    Returns:
        评分结果字典，失败返回 None
    """
    try:
        from morning.fundamental_analyzer import score_stock

        # 先尝试获取股票名称
        name = _get_stock_name(code)
        if not name:
            name = code

        result = score_stock(code, name)
        if result is None:
            logger.warning("基本面评分返回 None: %s", code)
            return {
                "code": code,
                "name": name,
                "total": 0,
                "dimensions": {},
                "summary": "数据不足，无法评分",
            }

        return result

    except Exception as e:
        logger.error("基本面评分失败 [%s]: %s", code, e)
        return {
            "code": code,
            "name": "",
            "total": 0,
            "dimensions": {},
            "summary": f"评分出错: {e}",
        }


def get_intraday_data(code: str) -> dict:
    """
    获取个股分时数据

    Args:
        code: 股票代码

    Returns:
        分时数据字典
    """
    result = {
        "code": code,
        "name": "",
        "points": [],
        "prev_close": 0.0,
    }

    try:
        import akshare as ak

        # 获取分时数据
        df = ak.stock_zh_a_hist_min_em(symbol=code, period="1", adjust="")
        if df is None or df.empty:
            logger.warning("分时数据为空: %s", code)
            return result

        # 获取股票名称和昨收
        try:
            spot_df = ak.stock_zh_a_spot_em()
            row = spot_df[spot_df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                result["name"] = str(r.get("名称", ""))
                result["prev_close"] = float(r.get("昨收", 0))
        except Exception as e:
            logger.warning("获取股票名称失败: %s", e)

        # 解析分时数据
        for _, row in df.iterrows():
            point = {
                "time": str(row.get("时间", "")),
                "price": float(row.get("收盘", 0)),
                "volume": float(row.get("成交量", 0)),
                "avg_price": float(row.get("均价", 0)) if "均价" in row.index else 0,
            }
            result["points"].append(point)

        logger.info("获取分时数据成功: %s, %d 个点", code, len(result["points"]))

    except ImportError:
        logger.error("akshare 未安装")
    except Exception as e:
        logger.error("获取分时数据失败 [%s]: %s", code, e)

    return result


def _get_stock_name(code: str) -> str:
    """获取股票名称"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            return str(row.iloc[0].get("名称", ""))
    except Exception:
        pass
    return ""
