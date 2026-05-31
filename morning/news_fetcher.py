"""
新闻抓取模块
使用 feedparser 从 RSS 源获取财经新闻，支持多种 RSS/Atom 格式
"""
import logging
from datetime import datetime
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import RSSSource, get_config

logger = logging.getLogger(__name__)

# 当 feedparser 解析失败时，尝试用 requests + BeautifulSoup 兜底
_FALLBACK_TIMEOUT = 15  # 秒


class NewsEntry:
    """单条新闻条目"""
    def __init__(
        self,
        title: str,
        link: str,
        summary: str = "",
        published: Optional[str] = None,
        source_name: str = "",
    ):
        self.title = (title or "").strip()
        self.link = (link or "").strip()
        self.summary = (summary or "").strip()
        self.published = published or ""
        self.source_name = source_name

    @property
    def text(self) -> str:
        """拼接为纯文本，供后续分析使用"""
        parts = [
            f"【{self.source_name}】{self.title}",
            f"链接：{self.link}",
        ]
        if self.summary:
            # 去除 HTML 标签
            clean = BeautifulSoup(self.summary, "html.parser").get_text(
                separator=" ", strip=True
            )
            parts.append(f"摘要：{clean}")
        if self.published:
            parts.append(f"时间：{self.published}")
        return "\n".join(parts)

    def __repr__(self):
        return f"NewsEntry({self.source_name}, {self.title[:30]})"


def _fetch_rss(source: RSSSource) -> list[NewsEntry]:
    """
    通过 feedparser 解析 RSS 源
    返回该源的所有新闻条目
    """
    entries: list[NewsEntry] = []
    logger.info("正在抓取 RSS: %s (%s)", source.name, source.url)

    try:
        feed = feedparser.parse(source.url)
    except Exception as e:
        logger.warning("feedparser 解析失败 %s: %s", source.name, e)
        return _fallback_fetch(source)

    # 检查解析结果
    if feed.bozo and not feed.entries:
        logger.warning(
            "RSS 解析异常 [%s] %s，尝试兜底抓取", source.name, feed.bozo_exception
        )
        return _fallback_fetch(source)

    if not feed.entries:
        logger.warning("RSS [%s] 无条目", source.name)
        return _fallback_fetch(source)

    for item in feed.entries:
        try:
            entry = NewsEntry(
                title=item.get("title", ""),
                link=item.get("link", ""),
                summary=item.get("summary", item.get("description", "")),
                published=(
                    item.get("published", item.get("updated", ""))
                ),
                source_name=source.name,
            )
            if entry.title:  # 跳过空标题
                entries.append(entry)
        except Exception as e:
            logger.debug("跳过异常条目: %s", e)
            continue

    logger.info("RSS [%s] 获取 %d 条新闻", source.name, len(entries))
    return entries


def _fallback_fetch(source: RSSSource) -> list[NewsEntry]:
    """
    当 feedparser 失败时，尝试用 requests + BeautifulSoup 抓取
    仅提取页面标题和正文段落作为兜底
    """
    logger.info("兜底抓取: %s (%s)", source.name, source.url)
    try:
        resp = requests.get(
            source.url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36"},
            timeout=_FALLBACK_TIMEOUT,
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        # 提取所有段落文本
        paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "li"])
        texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]

        # 尝试获取页面标题
        page_title = ""
        title_tag = soup.find("title")
        if title_tag:
            page_title = title_tag.get_text(strip=True)

        # 合并为一个条目（兜底场景下抓取整页内容）
        combined = "\n".join(texts[:50])  # 限制前 50 个段落
        if combined:
            entries = [
                NewsEntry(
                    title=page_title or f"{source.name} - 当日新闻汇总",
                    link=source.url,
                    summary=combined[:2000],
                    source_name=source.name,
                )
            ]
            logger.info("兜底抓取 [%s] 成功，获取 %d 字符", source.name, len(combined))
            return entries
    except Exception as e:
        logger.error("兜底抓取失败 %s: %s", source.name, e)

    return []


def fetch_all_news(max_per_source: int = 20) -> list[NewsEntry]:
    """
    从所有 RSS 源抓取新闻

    Args:
        max_per_source: 每个源最多保留的条数

    Returns:
        合并后的新闻列表（按源顺序排列）
    """
    config = get_config()
    all_entries: list[NewsEntry] = []

    for source in config.rss_sources:
        if not source.url:
            logger.warning("跳过空 URL 的源: %s", source.name)
            continue

        entries = _fetch_rss(source)
        # 每个源最多取 max_per_source 条
        all_entries.extend(entries[:max_per_source])

    logger.info(
        "新闻抓取完成，共 %d 条（来自 %d 个源）",
        len(all_entries),
        len(config.rss_sources),
    )
    return all_entries
