"""
晨报服务
从 recommendations.json 读取晨报数据
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 推荐记录文件路径
RECOMMENDATIONS_FILE = Path(__file__).parent.parent.parent / "data" / "recommendations" / "recommendations.json"


def get_morning_data(date: Optional[str] = None) -> dict:
    """
    获取指定日期的晨报数据

    Args:
        date: 日期字符串 YYYYMMDD 或 YYYY-MM-DD，None 则使用今天

    Returns:
        晨报数据字典
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    else:
        # 统一格式为 YYYYMMDD
        date = date.replace("-", "")

    result = {
        "date": date,
        "sentiment": "中性",
        "top_picks": [],
        "good_sectors": [],
        "bad_sectors": [],
        "stock_mentions": [],
        "key_events": [],
        "available": False,
    }

    try:
        if not RECOMMENDATIONS_FILE.exists():
            logger.warning("推荐记录文件不存在: %s", RECOMMENDATIONS_FILE)
            return result

        with open(RECOMMENDATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = data.get("records", [])

        # 筛选指定日期的记录
        date_records = [r for r in records if r.get("date") == date]
        if not date_records:
            logger.info("日期 %s 无晨报数据", date)
            return result

        # 提取情绪
        sentiments = [r.get("sentiment", "") for r in date_records if r.get("sentiment")]
        if sentiments:
            result["sentiment"] = sentiments[0]

        # 提取推荐股票
        for r in date_records:
            sector = r.get("sector", "")
            if sector and sector != "个股提及":
                if sector not in result["good_sectors"]:
                    result["good_sectors"].append(sector)

            stock_info = {
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "reason": r.get("reason", ""),
                "sector": sector,
                "strength": int(r.get("strength", 0)),
            }
            result["stock_mentions"].append(stock_info)

            # 强度 >= 4 的作为 top picks
            if stock_info["strength"] >= 4:
                # 按板块分组
                existing = None
                for pick in result["top_picks"]:
                    if pick.get("sector") == sector:
                        existing = pick
                        break
                if existing:
                    existing["stocks"].append({
                        "code": stock_info["code"],
                        "name": stock_info["name"],
                        "reason": stock_info["reason"],
                    })
                else:
                    result["top_picks"].append({
                        "sector": sector,
                        "strength": stock_info["strength"],
                        "reason": r.get("sector_reason", ""),
                        "stocks": [{
                            "code": stock_info["code"],
                            "name": stock_info["name"],
                            "reason": stock_info["reason"],
                        }],
                    })

        # 提取关键事件
        sector_reasons = [r.get("sector_reason", "") for r in date_records if r.get("sector_reason")]
        result["key_events"] = list(set(sector_reasons))

        result["available"] = True
        logger.info("获取晨报数据成功: date=%s, %d 条记录", date, len(date_records))

    except Exception as e:
        logger.error("获取晨报数据失败: %s", e)

    return result
