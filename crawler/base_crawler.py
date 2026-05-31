"""
爬虫基类 - 提供通用的HTTP请求、解析、缓存功能
"""
import json
import time
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import RAW_DATA_DIR, CRAWLER_USER_AGENT, CRAWLER_TIMEOUT, CRAWLER_DELAY

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """爬取结果数据类"""
    url: str
    title: str = ""
    content: str = ""
    html: str = ""
    metadata: dict = field(default_factory=dict)
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status_code: int = 0
    success: bool = False


class BaseCrawler:
    """
    爬虫基类
    封装了请求发送、响应解析、结果缓存等通用功能
    """

    def __init__(self, name: str = "base"):
        self.name = name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": CRAWLER_USER_AGENT,
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.delay = CRAWLER_DELAY
        self.timeout = CRAWLER_TIMEOUT
        self._last_request_time = 0.0

    def _respect_rate_limit(self):
        """遵守请求频率限制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def fetch(self, url: str, params: dict = None, headers: dict = None) -> Optional[requests.Response]:
        """
        发送HTTP GET请求
        返回 Response 对象，失败返回 None
        """
        self._respect_rate_limit()
        try:
            merged_headers = {}
            if headers:
                merged_headers.update(headers)
            resp = self.session.get(
                url, params=params, headers=merged_headers or None,
                timeout=self.timeout
            )
            resp.raise_for_status()
            logger.info(f"[{self.name}] GET {url} -> {resp.status_code}")
            return resp
        except requests.RequestException as e:
            logger.error(f"[{self.name}] 请求失败: {url} -> {e}")
            return None

    def fetch_json(self, url: str, **kwargs) -> Optional[dict]:
        """获取JSON响应"""
        resp = self.fetch(url, **kwargs)
        if resp and resp.headers.get("content-type", "").startswith("application/json"):
            try:
                return resp.json()
            except ValueError:
                logger.warning(f"JSON解析失败: {url}")
        return None

    def parse_html(self, html: str, parser: str = "lxml") -> BeautifulSoup:
        """解析HTML为BeautifulSoup对象"""
        return BeautifulSoup(html, parser)

    def extract_text(self, soup: BeautifulSoup, selector: str = None) -> str:
        """从soup中提取文本"""
        if selector:
            elements = soup.select(selector)
            return "\n".join(e.get_text(strip=True) for e in elements)
        return soup.get_text(strip=True)

    def extract_links(self, soup: BeautifulSoup, base_url: str = "") -> list:
        """提取页面中的所有链接"""
        from urllib.parse import urljoin
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if base_url:
                href = urljoin(base_url, href)
            links.append({
                "text": a.get_text(strip=True),
                "url": href,
            })
        return links

    def save_result(self, result: CrawlResult, filename: str = None) -> Path:
        """保存爬取结果到文件"""
        if filename is None:
            hash_str = hashlib.md5(result.url.encode()).hexdigest()[:12]
            filename = f"{self.name}_{hash_str}.json"

        save_path = RAW_DATA_DIR / filename
        data = asdict(result)
        save_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"结果已保存: {save_path}")
        return save_path

    def crawl(self, url: str) -> CrawlResult:
        """
        通用爬取入口方法
        子类可重写此方法实现特定逻辑
        """
        result = CrawlResult(url=url)
        resp = self.fetch(url)
        if resp is None:
            return result

        result.status_code = resp.status_code
        result.html = resp.text

        soup = self.parse_html(resp.text)
        result.title = soup.title.string if soup.title else ""
        result.content = self.extract_text(soup)

        # 自动提取元数据
        result.metadata = {
            "content_length": len(resp.text),
            "content_type": resp.headers.get("content-type", ""),
            "links_count": len(self.extract_links(soup)),
        }
        result.success = True
        self.save_result(result)
        return result
