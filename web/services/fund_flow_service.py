"""
资金流向服务
使用 akshare 获取板块资金流向数据
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_fund_flow_data(
    date: Optional[str] = None,
    sector_type: str = "industry",
    top_n: int = 30,
) -> list[dict]:
    """
    获取板块资金流向数据

    Args:
        date: 日期 YYYY-MM-DD 或 YYYYMMDD，None 则使用今天
        sector_type: 板块类型 - industry(行业), concept(概念), area(地域)
        top_n: 返回前 N 条

    Returns:
        资金流向数据列表
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    else:
        date = date.replace("-", "")

    items = []

    try:
        import akshare as ak

        # akshare 资金流向接口
        if sector_type == "industry":
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        elif sector_type == "concept":
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")
        else:
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="地域资金流")

        if df is None or df.empty:
            logger.warning("资金流向数据为空: sector_type=%s", sector_type)
            return items

        # 取前 N 条
        df = df.head(top_n)

        for i, (_, row) in enumerate(df.iterrows()):
            item = {
                "sector_name": str(row.get("名称", "")),
                "sector_type": sector_type,
                "main_net_inflow": _safe_float(row.get("主力净流入-净额", 0)),
                "retail_net_inflow": _safe_float(row.get("小单净流入-净额", 0)),
                "super_large_inflow": _safe_float(row.get("超大单净流入-净额", 0)),
                "large_inflow": _safe_float(row.get("大单净流入-净额", 0)),
                "medium_inflow": _safe_float(row.get("中单净流入-净额", 0)),
                "small_inflow": _safe_float(row.get("小单净流入-净额", 0)),
                "rank": i + 1,
            }
            items.append(item)

        logger.info("获取资金流向数据成功: %s, %d 条", sector_type, len(items))

    except ImportError:
        logger.error("akshare 未安装")
    except Exception as e:
        logger.error("获取资金流向数据失败: %s", e)

    return items


def _safe_float(val) -> float:
    """安全转换为浮点数"""
    if val is None:
        return 0.0
    try:
        s = str(val).replace(",", "").replace("%", "").strip()
        if s in ("--", "", "None", "nan"):
            return 0.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0
