"""
风险预警整合模块
将 RiskWarningEngine 的评估结果生成为 Markdown 段落，追加在晨报尾部
"""
import logging
from datetime import datetime
from typing import Optional

from risk.risk_engine import RiskWarningEngine

logger = logging.getLogger(__name__)


def build_risk_section(risk_result: dict) -> str:
    """
    从风险评分结果生成 Markdown 段落

    Args:
        risk_result: RiskWarningEngine.assess() 的返回字典

    Returns:
        格式化的 Markdown 字符串，可直接追加在晨报末尾
    """
    if not risk_result or "风险分数" not in risk_result:
        logger.warning("风险结果为空，跳过风险段")
        return ""

    score = risk_result["风险分数"]
    level = risk_result["风险等级"]
    suggestion = risk_result.get("操作建议", "")
    dims = risk_result.get("各维度", {})
    snapshot = risk_result.get("数据快照", {})

    lines = [
        "",
        "---",
        "## 风险预警",
        "",
        f"> 综合评分 **{score}/10** → **{level}**",
        f"> {suggestion}",
        "",
        "| 维度 | 评分 | 说明 | 当前值 |",
        "|------|:----:|------|:-----:|",
    ]

    # 各维度表格行
    dim_config = [
        ("涨跌家数", "ad"),
        ("北向资金", "north"),
        ("指数偏离", "index"),
        ("日历效应", "cal"),
    ]
    dim_keys = list(dims.keys())
    for name in ["涨跌家数", "北向资金", "指数偏离", "日历效应"]:
        d = dims.get(name, {})
        if d:
            score_str = f"{d.get('分数', '?')}/3" if name != "日历效应" else f"{d.get('分数', '?')}/1"
            value = d.get("值", "")
            desc = d.get("说明", "")
            lines.append(f"| {name} | {score_str} | {desc} | {value} |")

    # 数据快照
    lines.extend([
        "",
        "**📊 数据快照：**",
    ])
    if snapshot.get("涨跌比%") is not None:
        lines.append(f"- 涨跌家数比：{snapshot['涨跌比%']:.1f}%")
    if snapshot.get("北向合计(亿)") is not None:
        lines.append(f"- 北向资金净流入：{snapshot['北向合计(亿)']:+.1f}亿")
    if snapshot.get("指数20日偏离%") is not None:
        lines.append(f"- 上证指数20日偏离：{snapshot['指数20日偏离%']:+.2f}%")
    if snapshot.get("指数60日偏离%") is not None:
        lines.append(f"- 上证指数60日偏离：{snapshot['指数60日偏离%']:+.2f}%")

    # 风险等级图标
    if level == "低风险":
        lines.append("\n✅ **市场环境健康，可正常交易**")
    elif level == "中风险":
        lines.append("\n⚠️ **出现风险信号，建议控制仓位 ≤ 70%**")
    else:
        lines.append("\n🔴 **风险较高！建议减仓至半仓以下，不开新仓**")

    lines.append("")  # 末尾空行
    return "\n".join(lines)


def run_risk_and_build_section() -> str:
    """
    便捷函数：运行风险评分并直接生成 Markdown 段落

    Returns:
        Markdown 字符串（空 str 表示失败）
    """
    try:
        engine = RiskWarningEngine()
        result = engine.assess()
        return build_risk_section(result)
    except Exception as e:
        logger.warning(f"风险预警生成失败: {e}")
        return ""
