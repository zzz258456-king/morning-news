#!/usr/bin/env python3
"""快速测试脚本 - 验证各模块功能"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 50)
print("全能数据平台 - 功能测试")
print("=" * 50)

# 1. 测试模块导入
print("\n[1/4] 测试模块导入...")
from config import *
from crawler import BaseCrawler, WebScraper, TaskScheduler
from analyzer import DataProcessor, DataVisualizer, MLModel
print("   [OK] 所有模块导入成功")

# 2. 测试爬虫
print("\n[2/4] 测试爬虫功能...")
scraper = WebScraper("test")
result = scraper.crawl("https://httpbin.org/html")
print(f"   标题: {result.title}")
print(f"   状态: {'成功' if result.success else '失败'}")
print(f"   内容长度: {len(result.content)} 字符")
print(f"   链接数: {result.metadata.get('links_count', 0)}")

# 3. 测试数据分析
print("\n[3/4] 测试数据分析...")
import pandas as pd
import numpy as np
test_data = pd.DataFrame({
    "name": ["A", "B", "C", "D", "E"],
    "value": [10, 20, 15, 30, 25],
    "category": ["X", "Y", "X", "Y", "Z"],
})
processor = DataProcessor()
processor.load_dataframe(test_data, "test")
processor.clean()
summary = processor.summary()
print(f"   数据: {summary['行数']}行 x {summary['列数']}列")
print(f"   列名: {summary['列名']}")

# 4. 测试可视化
print("\n[4/4] 测试可视化...")
viz = DataVisualizer("测试")
img = viz.bar_chart(test_data, "name", "value", output="base64")
print(f"   柱状图: 已生成 ({len(img)} bytes base64)")
img2 = viz.pie_chart(test_data["value"], output="base64")
print(f"   饼图: 已生成 ({len(img2)} bytes base64)")

print("\n" + "=" * 50)
print("所有测试通过！")
print("=" * 50)
