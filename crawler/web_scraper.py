"""
高级网页数据采集器
支持：普通页面抓取、表格提取、API数据采集、批量抓取
"""
import json
import re
import logging
from typing import List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
import pandas as pd

from .base_crawler import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)


class WebScraper(BaseCrawler):
    """
    增强版网页数据采集器
    提供表格提取、批量抓取、数据导出等功能
    """

    def __init__(self, name: str = "scraper"):
        super().__init__(name)

    def extract_tables(self, html: str, table_index: int = 0) -> Optional[pd.DataFrame]:
        """
        从HTML中提取表格数据，返回DataFrame
        table_index: 页面中第几个表格（0-based）
        """
        soup = self.parse_html(html)
        tables = soup.find_all("table")
        if not tables or table_index >= len(tables):
            logger.warning(f"未找到表格（索引: {table_index}）")
            return None

        table = tables[table_index]
        rows = table.find_all("tr")

        data = []
        headers = []
        for i, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            cell_texts = [cell.get_text(strip=True) for cell in cells]

            if i == 0 and row.find_all("th"):
                headers = cell_texts
            elif headers:
                data.append(cell_texts)
            else:
                data.append(cell_texts)

        df = pd.DataFrame(data, columns=headers or None)
        logger.info(f"提取表格: {df.shape[0]}行 x {df.shape[1]}列")
        return df

    def extract_articles(self, html: str, article_selector: str = "article") -> List[dict]:
        """
        提取页面中的文章列表
        支持自定义选择器
        """
        soup = self.parse_html(html)
        articles = soup.select(article_selector)
        results = []

        for article in articles:
            title_el = article.find(["h1", "h2", "h3", "h4"])
            link_el = article.find("a", href=True)
            time_el = article.find(["time", "span", "div"], class_=re.compile(r"time|date|meta"))

            results.append({
                "title": title_el.get_text(strip=True) if title_el else "",
                "url": link_el["href"] if link_el else "",
                "summary": article.get_text(strip=True)[:200],
                "date": time_el.get_text(strip=True) if time_el else "",
            })

        logger.info(f"提取到 {len(results)} 篇文章")
        return results

    def batch_crawl(self, urls: List[str], max_workers: int = 5) -> List[CrawlResult]:
        """
        批量爬取多个URL
        使用线程池提高效率
        """
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self.crawl, url): url for url in urls}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"[批量] 完成: {url} -> {'成功' if result.success else '失败'}")
                except Exception as e:
                    logger.error(f"[批量] 异常: {url} -> {e}")
                    results.append(CrawlResult(url=url, success=False))
        return results

    def crawl_and_export_csv(self, url: str, output_name: str = None) -> Optional[str]:
        """
        爬取页面并导出为CSV
        自动识别表格数据并导出
        """
        result = self.crawl(url)
        if not result.success:
            logger.error("爬取失败，无法导出")
            return None

        df = self.extract_tables(result.html)
        if df is not None:
            if output_name is None:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace(".", "_")
                output_name = f"{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            from config import PROCESSED_DATA_DIR
            output_path = PROCESSED_DATA_DIR / f"{output_name}.csv"
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"数据已导出: {output_path}")
            return str(output_path)
        return None

    def fetch_api_data(self, api_url: str) -> Optional[dict]:
        """采集API接口数据"""
        return self.fetch_json(api_url)
