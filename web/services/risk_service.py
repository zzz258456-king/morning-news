"""
风险预警服务
封装 risk.RiskWarningEngine
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_risk_assessment(
    ad_ratio: Optional[float] = None,
    north_net: Optional[float] = None,
) -> dict:
    """
    获取综合风险评估

    Args:
        ad_ratio: 涨跌比%，None 则自动获取
        north_net: 北向净流入(亿)，None 则自动获取

    Returns:
        风险评估字典
    """
    default_result = {
        "total_score": 0.0,
        "level": "低风险",
        "suggestion": "风险数据不可用",
        "dimensions": {},
        "snapshot": {},
        "timestamp": "",
    }

    try:
        from risk.risk_engine import RiskWarningEngine
        from morning.config import load_config, get_config

        cfg = get_config()

        engine = RiskWarningEngine(
            ad_warn=cfg.risk.ad_warn,
            ad_danger=cfg.risk.ad_danger,
            north_warn=cfg.risk.north_warn,
            north_danger=cfg.risk.north_danger,
            index_dev_warn=cfg.risk.index_dev_warn,
            index_dev_danger=cfg.risk.index_dev_danger,
        )

        raw = engine.assess(ad_ratio=ad_ratio, north_net=north_net)

        # 转换为 API 响应格式
        dimensions = {}
        raw_dims = raw.get("各维度", {})
        for key, val in raw_dims.items():
            dimensions[key] = {
                "score": val.get("分数", 0),
                "reason": val.get("说明", ""),
                "value": val.get("值", ""),
            }

        return {
            "total_score": raw.get("风险分数", 0),
            "level": raw.get("风险等级", "低风险"),
            "suggestion": raw.get("操作建议", ""),
            "dimensions": dimensions,
            "snapshot": raw.get("数据快照", {}),
            "timestamp": raw.get("时间戳", ""),
        }

    except Exception as e:
        logger.error("获取风险评估失败: %s", e)
        default_result["suggestion"] = f"风险评估出错: {e}"
        return default_result
