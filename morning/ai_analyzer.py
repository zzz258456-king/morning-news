"""
新闻分析模块
调用 DeepSeek API（兼容 OpenAI 接口格式）分析财经新闻，
提取利好/利空板块、重点板块与个股推荐、市场情绪等
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional

from openai import OpenAI

from .config import get_config
from .news_fetcher import NewsEntry

logger = logging.getLogger(__name__)


def _is_main_board(code: str) -> bool:
    """检查股票代码是否属于主板或中小板（排除创业板300开头、科创板688开头）"""
    code = code.strip()
    return bool(code) and not (code.startswith("300") or code.startswith("688"))


# ---------- 数据结构 ----------


class StockMention:
    """个股提及"""
    def __init__(self, code: str = "", name: str = "", direction: str = ""):
        self.code = code
        self.name = name
        self.direction = direction  # "利好" / "利空" / "中性"


class SectorAnalysis:
    """板块分析"""
    def __init__(
        self,
        name: str = "",
        strength: int = 3,
        reason: str = "",
    ):
        self.name = name
        self.strength = max(1, min(5, strength))  # 限制 1-5
        self.reason = reason


class StockRecommendation:
    """个股推荐"""
    def __init__(self, code: str = "", name: str = "", reason: str = ""):
        self.code = code
        self.name = name
        self.reason = reason


class TopPickSector:
    """重点推荐板块（含2只推荐个股）"""
    def __init__(
        self,
        name: str = "",
        strength: int = 5,
        reason: str = "",
        stocks: list[StockRecommendation] = None,
    ):
        self.name = name
        self.strength = max(1, min(5, strength))
        self.reason = reason
        self.stocks = stocks or []


class KeyEvent:
    """关键事件"""
    def __init__(
        self,
        title: str = "",
        impact: str = "",
        related_sectors: list[str] = None,
    ):
        self.title = title
        self.impact = impact
        self.related_sectors = related_sectors or []


class AnalysisResult:
    """AI 分析结果"""
    def __init__(
        self,
        top_picks: list[TopPickSector] = None,
        good_sectors: list[SectorAnalysis] = None,
        bad_sectors: list[str] = None,
        stock_mentions: list[StockMention] = None,
        market_sentiment: str = "",
        key_events: list[KeyEvent] = None,
        raw_text: str = "",
    ):
        self.top_picks = top_picks or []
        self.good_sectors = good_sectors or []
        self.bad_sectors = bad_sectors or []
        self.stock_mentions = stock_mentions or []
        self.market_sentiment = market_sentiment or "中性"
        self.key_events = key_events or []
        self.raw_text = raw_text  # AI 原始返回文本

    @property
    def valid(self) -> bool:
        """判断分析结果是否有效"""
        return bool(self.top_picks or self.good_sectors or self.bad_sectors or self.key_events)


# ---------- 提示词 ----------

_SYSTEM_PROMPT = """你是一位经验丰富的 A 股首席分析师。你的任务是根据财经新闻，提供专业、精准的分析并以 JSON 格式输出。

分析要求：
1. 从所有利好消息中，筛选出**今日最具投资价值的 2 个核心板块**，并各推荐 2 只最可能受益的个股（附理由）
2. 同时列出其他利好板块（简要，不加个股推荐）
3. 列出利空板块
4. 找出新闻中明确提及的个股，标注方向
5. 判断整体市场情绪（乐观/谨慎乐观/中性/谨慎悲观/悲观）
6. 梳理关键事件及其影响

推荐个股时请给出具体的 A 股代码（500/600/000/002开头），无法确定代码的写"未明确"。
**注意：只推荐主板和中小板股票，不要推荐创业板（300开头）和科创板（688开头）的股票。**
请始终以 JSON 格式输出，不要包含 ```json 代码块标记，只输出纯 JSON。"""

_USER_PROMPT_TEMPLATE = """请分析以下财经新闻，输出 JSON 格式的分析报告：

当前日期：{date}
{weekend_context}
新闻内容：
{news_text}

请严格按以下 JSON 格式输出，字段说明：

1. top_picks（重点推荐板块，数组，长度为2）：
   每个元素包含：
   - name: 板块名称
   - strength: 强度(1-5)
   - reason: 为什么该板块是今日最佳
   - stocks: 推荐的2只个股，每只包含 code(股票代码)、name(股票名称)、reason(推荐理由)
   **注意：推荐的个股代码必须是主板或中小板（500/600/000/002开头），不要包含创业板（300开头）和科创板（688开头）。**

2. good_sectors（其他利好板块列表，不包含 top_picks 中的板块）：
   每个包含 name(板块名称)、strength(强度1-5)、reason(理由)

3. bad_sectors（利空板块名称列表，每个元素为字符串）

4. stock_mentions（新闻中提及的个股列表，每个包含 code(代码)、name(名称)、direction(利好/利空/中性)）

5. market_sentiment（市场情绪：乐观/谨慎乐观/中性/谨慎悲观/悲观）

6. key_events（关键事件列表，不超过5个，每个包含 title(标题)、impact(影响分析)、related_sectors(相关板块)）"""


# ---------- 主逻辑 ----------


def _build_news_text(news_list: list[NewsEntry], max_chars: int = 8000) -> str:
    """
    将新闻列表拼接为分析用的文本
    限制总字符数，优先保留重要新闻（取前 N 条）
    """
    lines = []
    total = 0
    for i, news in enumerate(news_list, 1):
        text = f"{i}. {news.text}\n"
        total += len(text)
        if total > max_chars:
            # 超出限制后只保留标题和链接
            text = f"{i}. 【{news.source_name}】{news.title}\n   链接：{news.link}\n"
            total += len(text) - 200  # 近似调整
        if total > max_chars * 1.2:
            break
        lines.append(text)
    return "\n".join(lines)


def analyze_news(news_list: list[NewsEntry], is_monday: bool = False) -> AnalysisResult:
    """
    调用 AI API（DeepSeek）分析新闻

    Args:
        news_list: 待分析的新闻列表
        is_monday: 周一模式，汇总周末消息

    Returns:
        AnalysisResult 分析结果
    """
    config = get_config()

    if not config.ai.available:
        logger.error("AI API 密钥未配置，无法进行分析")
        return AnalysisResult(market_sentiment="无法分析（API 未配置）")

    # 构建提示词
    news_text = _build_news_text(news_list)
    weekend_context = ""
    if is_monday:
        weekend_context = "今日是周一，请重点汇总本周末（周五到周日）发生的所有重要消息，覆盖更全面，不要遗漏。\n\n"
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        news_text=news_text,
        weekend_context=weekend_context,
    )

    logger.info(
        "调用 AI API (base_url=%s, model=%s, 输入 %d 字符)",
        config.ai.base_url,
        config.ai.model,
        len(user_prompt),
    )

    try:
        client = OpenAI(
            api_key=config.ai.api_key,
            base_url=config.ai.base_url,
        )
        response = client.chat.completions.create(
            model=config.ai.model,
            max_tokens=config.ai.max_tokens,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content or ""
        logger.debug("AI 原始响应: %s", raw[:200])

        # 解析 JSON
        result = _parse_response(raw)
        result.raw_text = raw
        logger.info("AI 分析完成: 情绪=%s, 重点板块=%d, 利好=%d, 利空=%d, 事件=%d",
                     result.market_sentiment,
                     len(result.top_picks),
                     len(result.good_sectors),
                     len(result.bad_sectors),
                     len(result.key_events))
        return result

    except Exception as e:
        logger.error("AI API 调用失败: %s", e)
        return AnalysisResult(
            market_sentiment=f"分析失败（{str(e)[:50]}）"
        )


def _parse_response(text: str) -> AnalysisResult:
    """解析 AI 返回的 JSON 字符串"""
    # 尝试提取 JSON（兼容可能包含的 markdown 代码块）
    clean = text.strip()
    if clean.startswith("```"):
        # 提取 ```json ... ``` 或 ``` ... ``` 中的内容
        lines = clean.split("\n")
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                start = i + 1
                break
        end = len(lines)
        for i in range(len(lines) - 1, start - 1, -1):
            if lines[i].strip().startswith("```"):
                end = i
                break
        clean = "\n".join(lines[start:end]).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        logger.warning("JSON 解析失败: %s，返回原始文本", e)
        return AnalysisResult(market_sentiment="JSON 解析失败", raw_text=text)

    return _json_to_result(data)


def _json_to_result(data: dict[str, Any]) -> AnalysisResult:
    """将解析后的 dict 转换为 AnalysisResult"""
    result = AnalysisResult()

    # ----- 重点推荐板块（top_picks）-----
    for item in data.get("top_picks", []):
        if not isinstance(item, dict):
            continue
        stocks = []
        for st in item.get("stocks", []):
            if isinstance(st, dict):
                code = st.get("code", "")
                if code and not _is_main_board(code):
                    logger.info("过滤掉非主板个股: %s %s", code, st.get("name", ""))
                    continue
                stocks.append(StockRecommendation(
                    code=code,
                    name=st.get("name", ""),
                    reason=st.get("reason", ""),
                ))
        if not stocks:
            logger.info("板块 [%s] 的推荐个股均为创业板/科创板，已全部过滤", item.get("name", ""))
        result.top_picks.append(TopPickSector(
            name=item.get("name", ""),
            strength=int(item.get("strength", 5)),
            reason=item.get("reason", ""),
            stocks=stocks,
        ))

    # ----- 其他利好板块 -----
    for item in data.get("good_sectors", []):
        if isinstance(item, dict):
            result.good_sectors.append(SectorAnalysis(
                name=item.get("name", ""),
                strength=int(item.get("strength", 3)),
                reason=item.get("reason", ""),
            ))
        elif isinstance(item, str):
            result.good_sectors.append(SectorAnalysis(name=item, strength=3))

    # ----- 利空板块 -----
    bad = data.get("bad_sectors", [])
    if isinstance(bad, list):
        result.bad_sectors = [str(b) for b in bad if b]
    elif isinstance(bad, str):
        result.bad_sectors = [bad]

    # ----- 个股提及 -----
    for item in data.get("stock_mentions", []):
        if isinstance(item, dict):
            code = item.get("code", "")
            if code and not _is_main_board(code):
                logger.info("过滤掉非主板个股提及: %s %s", code, item.get("name", ""))
                continue
            result.stock_mentions.append(StockMention(
                code=item.get("code", ""),
                name=item.get("name", ""),
                direction=item.get("direction", "中性"),
            ))

    # ----- 市场情绪 -----
    result.market_sentiment = data.get("market_sentiment", "中性")

    # ----- 关键事件 -----
    for item in data.get("key_events", []):
        if isinstance(item, dict):
            result.key_events.append(KeyEvent(
                title=item.get("title", ""),
                impact=item.get("impact", ""),
                related_sectors=item.get("related_sectors", []),
            ))

    return result
