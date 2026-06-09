"""
异动监控模块
监控宏观经济、大宗商品、科技赛道、突发事件四个维度
"""
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnomalyScore:
    """异动评分"""
    dimension: str  # 宏观/大宗/科技/突发
    score: float    # 0-25分
    description: str
    details: dict = None


@dataclass
class AnomalyResult:
    """异动监控结果"""
    total_score: float  # 0-100分
    scores: list  # List[AnomalyScore]
    timestamp: datetime
    should_push: bool  # 是否达到推送阈值


class AnomalyMonitor:
    """异动监控器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.push_threshold = self.config.get("push_threshold", 60)

    def monitor_macro(self) -> AnomalyScore:
        """监控宏观经济"""
        score = 0
        details = {}
        description_parts = []

        try:
            # 获取美联储利率数据
            df = ak.macro_bank_usa_interest_rate()
            if len(df) > 0:
                latest = df.iloc[-1]
                # 简化评分逻辑：根据最新利率变化评分
                score += 5  # 基础分
                description_parts.append("美联储利率数据正常")
                details["fed_rate"] = "正常"
        except Exception as e:
            logger.warning(f"获取美联储利率失败: {e}")
            details["fed_rate"] = f"失败: {e}"

        try:
            # 获取中国CPI数据
            df = ak.macro_china_cpi_yearly()
            if len(df) > 0:
                score += 5
                description_parts.append("CPI数据正常")
                details["cpi"] = "正常"
        except Exception as e:
            logger.warning(f"获取CPI数据失败: {e}")
            details["cpi"] = f"失败: {e}"

        # 限制分数范围
        score = max(0, min(25, score))
        description = "宏观经济: " + "; ".join(description_parts) if description_parts else "宏观经济数据获取失败"

        return AnomalyScore(
            dimension="宏观",
            score=score,
            description=description,
            details=details
        )

    def monitor_commodity(self) -> AnomalyScore:
        """监控大宗商品"""
        score = 0
        details = {}
        description_parts = []

        try:
            # 获取期货主力数据
            df = ak.futures_main_sina(symbol="V0")  # 聚氯乙烯主力
            if len(df) > 0:
                latest = df.iloc[-1]
                # 简化评分逻辑
                score += 8
                description_parts.append("期货数据正常")
                details["futures"] = "正常"
        except Exception as e:
            logger.warning(f"获取期货数据失败: {e}")
            details["futures"] = f"失败: {e}"

        # 限制分数范围
        score = max(0, min(25, score))
        description = "大宗商品: " + "; ".join(description_parts) if description_parts else "大宗商品数据获取失败"

        return AnomalyScore(
            dimension="大宗",
            score=score,
            description=description,
            details=details
        )

    def monitor_tech(self, news_list: list = None) -> AnomalyScore:
        """监控科技赛道"""
        score = 0
        details = {}
        description_parts = []

        tech_keywords = self.config.get("dimensions", {}).get("tech", {}).get("keywords",
            ["AI", "芯片", "新能源", "半导体", "人工智能"])

        if news_list:
            # 统计科技相关新闻数量
            tech_news = []
            for news in news_list:
                if any(keyword in news.get("title", "") or keyword in news.get("text", "")
                      for keyword in tech_keywords):
                    tech_news.append(news)

            # 每条科技新闻 +2分，上限15分
            news_score = min(15, len(tech_news) * 2)
            score += news_score
            description_parts.append(f"科技新闻 {len(tech_news)} 条")
            details["tech_news_count"] = len(tech_news)

        # 限制分数范围
        score = max(0, min(25, score))
        description = "科技赛道: " + "; ".join(description_parts) if description_parts else "无科技相关新闻"

        return AnomalyScore(
            dimension="科技",
            score=score,
            description=description,
            details=details
        )

    def monitor_event(self, news_list: list = None) -> AnomalyScore:
        """监控突发事件"""
        score = 0
        details = {}
        description_parts = []

        event_keywords = self.config.get("dimensions", {}).get("event", {}).get("keywords",
            ["政策", "地缘", "制裁", "战争", "灾害"])

        if news_list:
            # 统计突发事件相关新闻数量
            event_news = []
            for news in news_list:
                if any(keyword in news.get("title", "") or keyword in news.get("text", "")
                      for keyword in event_keywords):
                    event_news.append(news)

            # 每条突发事件新闻 +5分，上限25分
            event_score = min(25, len(event_news) * 5)
            score += event_score
            description_parts.append(f"突发事件新闻 {len(event_news)} 条")
            details["event_news_count"] = len(event_news)

        # 限制分数范围
        score = max(0, min(25, score))
        description = "突发事件: " + "; ".join(description_parts) if description_parts else "无突发事件"

        return AnomalyScore(
            dimension="突发",
            score=score,
            description=description,
            details=details
        )

    def run(self, news_list: list = None) -> AnomalyResult:
        """运行异动监控"""
        logger.info("开始异动监控...")

        scores = []

        # 监控宏观经济
        macro_score = self.monitor_macro()
        scores.append(macro_score)

        # 监控大宗商品
        commodity_score = self.monitor_commodity()
        scores.append(commodity_score)

        # 监控科技赛道
        tech_score = self.monitor_tech(news_list)
        scores.append(tech_score)

        # 监控突发事件
        event_score = self.monitor_event(news_list)
        scores.append(event_score)

        # 计算总分
        total_score = sum(s.score for s in scores)

        # 判断是否达到推送阈值
        should_push = total_score >= self.push_threshold

        result = AnomalyResult(
            total_score=total_score,
            scores=scores,
            timestamp=datetime.now(),
            should_push=should_push
        )

        logger.info(f"异动监控完成: 总分={total_score}, 推送阈值={self.push_threshold}, 是否推送={should_push}")

        return result
