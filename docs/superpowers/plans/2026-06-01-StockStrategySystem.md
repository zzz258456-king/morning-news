# StockStrategySystem 量化策略系统 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有碎片代码整合为完整的、可自动化运行的量化策略研究与预警系统 StockStrategySystem，含新闻晨报、风险预警、打板策略回测与遗传算法进化、定时调度四大模块。

**Architecture:** 统一 config.yaml 配置 → 四大模块独立互调 → main.py CLI入口 → schedule定时任务。保持现有代码的核心逻辑不动，只做整合、补缺、完善。

**Tech Stack:** Python 3.10+, DeepSeek API, akshare/baostock, feedparser, schedule, DEAP, vectorbt

---
> **Workstream 说明：** 项目已按模块拆分，每个模块包含自己独立的文档和代码，可独立测试。

## 文件结构计划

```
C:\Users\Administrator\Desktop\_Projects\try\
├── config.yaml                    # 统一配置文件（新建）
├── main.py                        # 统一入口（新建）
├── run_morning.py                 # 保留，改为调用 morning 模块
├── .env                           # 密钥文件（已有）
├── requirements.txt               # 更新依赖
├── README.md                      # 更新说明
│
├── morning/                       # 新闻晨报模块（基本完好）
│   ├── __init__.py
│   ├── config.py                  # 保留兼容（读取 config.yaml）
│   ├── news_fetcher.py            # 完善：修复 RSS 源
│   ├── ai_analyzer.py             # 已有：DeepSeek API 分析
│   ├── dingtalk_sender.py         # 已有：钉钉推送
│   └── risk_integration.py        # 新建：风险预警整合为晨报附件
│
├── risk/                          # 风险预警模块（从 strategy/ 拆出）
│   ├── __init__.py                # 新建
│   ├── risk_engine.py             # 从 strategy/risk_warning.py 迁移
│   ├── calendar_effects.py        # 从 strategy/risk_warning.py 拆分
│   └── data_provider.py           # 从 strategy/risk_warning.py 拆分
│
├── strategy/                      # 策略回测模块（已有）
│   ├── __init__.py
│   ├── base.py
│   ├── board_chaser.py
│   ├── backtest_engine.py
│   ├── data_fetcher.py
│   └── evolver.py                 # 新建：遗传算法进化器
│
└── scheduler/                     # 调度模块（新建）
    ├── __init__.py                # 新建
    └── tasks.py                   # 新建：定时任务定义
```

---

### Task 1: 统一配置 config.yaml

**Files:**
- Create: `config.yaml`
- Modify: `morning/config.py` → 改为读取项目根目录 config.yaml
- Modify: `morning/config.yaml` → 删除（统一到根目录）

- [ ] **Step 1: 创建根目录 config.yaml**

```yaml
# ============================================
# StockStrategySystem — 统一配置文件
# API Key 等敏感信息请放在 .env 中
# ============================================

# ---------- 新闻晨报 ----------
morning:
  enabled: true
  schedule_time: "08:30"
  rss_sources:
    - name: "财联社电报"
      url: "https://www.cls.cn/telegraph"
    - name: "华尔街见闻"
      url: "https://wallstreetcn.com/rss/global"
    - name: "东方财富"
      url: "https://finance.eastmoney.com/a/czqyw.html"
    - name: "36氪"
      url: "https://36kr.com/feed"
  max_news_per_source: 20
  monday_max_news: 50

# ---------- AI 分析（DeepSeek API）----------
ai:
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 4096

# ---------- 钉钉推送 ----------
dingtalk:
  title: "【晨报】📰 财经新闻晨报"

# ---------- 风险预警 ----------
risk:
  enabled: true
  schedule_time: "08:30"
  # 涨跌家数阈值
  ad_warn: 30.0
  ad_danger: 20.0
  # 北向资金阈值（亿元）
  north_warn: -20.0
  north_danger: -50.0
  # 指数偏离阈值（%）
  index_dev_warn: 5.0
  index_dev_danger: 8.0
  # 低/中/高风险评分阈值
  low_risk_max: 3
  medium_risk_max: 6

# ---------- 回测参数 ----------
backtest:
  initial_capital: 1_000_000
  commission: 0.0003
  slippage: 0.001
  t_plus_1: true

# ---------- 打板策略 ----------
board_strategy:
  min_score: 14
  max_daily_buy: 3
  single_pct: 0.10

# ---------- 遗传算法进化 ----------
evolution:
  enabled: true
  schedule_time: "16:00"
  schedule_day: "fri"
  population_size: 30
  generations: 20
  elite_ratio: 0.2
  crossover_prob: 0.7
  mutation_prob: 0.1
  # 适应度权重
  fitness_weights:
    annual_return: 0.5
    sharpe_ratio: 0.3
    max_drawdown: -0.2

# ---------- 数据更新 ----------
data_update:
  enabled: true
  schedule_time: "15:30"
  cache_hours: 24

# ---------- 日志 ----------
logging:
  level: "INFO"
  file: "logs/system.log"
  max_bytes: 10485760
  backup_count: 7
```

- [ ] **Step 2: 更新 morning/config.py 改为读取根目录 config.yaml**

修改 `morning/config.py`，统一从项目根目录的 `config.yaml` 读取，保持兼容 MorningConfig 等数据结构。

- [ ] **Step 3: 删除 morning/config.yaml**（已无需要）

---

### Task 2: 完善新闻模块 — 修复 RSS 源

**Files:**
- Modify: `morning/news_fetcher.py`

- [ ] **Step 1: 优化 RSS 源，添加真实有效的 RSS 地址**

当前问题：财联社、华尔街见闻、东方财富的 RSS 都失效了（返回 HTML 不是 XML）。36氪正常工作。需要：
1. 把财联社 URL 改为真实的 RSS 地址
2. 添加更多可靠的 RSS 源
3. 确保兜底抓取逻辑更健壮

```python
# 在 _fetch_rss 前添加真实可用的 RSS 源列表
# 财联社: 无公开RSS，保留兜底
# 华尔街见闻: https://wallstreetcn.com/rss/global (有时可用)
# 东方财富: https://finance.eastmoney.com/rss/soft.html
# 36氪: https://36kr.com/feed (正常工作)
# 新增: 新浪财经 https://feed.mix.sina.com.cn/rss/stock.xml
```

- [ ] **Step 2: 测试修正后的新闻抓取**

Run: `cd try && python run_morning.py --fetch`

---

### Task 3: 创建 risk/ 模块 — 从 strategy/ 拆出并完善

**Files:**
- Create: `risk/__init__.py`
- Create: `risk/risk_engine.py`
- Create: `risk/data_provider.py`
- Create: `risk/calendar_effects.py`

- [ ] **Step 1: 创建 risk/__init__.py**

```python
"""
风险预警模块
独立评估大盘风险，输出 0-10 分风险评分
"""
__version__ = "1.0.0"
```

- [ ] **Step 2: 从 strategy/risk_warning.py 迁移核心代码**

核心类 `RiskWarningEngine` 基本完整，复制并适配新路径：
- `RiskWarningEngine.assess()` — 综合评分
- `RiskWarningEngine.print_report()` — 报告输出
- 阈值从 config.yaml 读取

- [ ] **Step 3: 测试风险模块**

Run: `python -c "from risk.risk_engine import RiskWarningEngine; e=RiskWarningEngine(); r=e.assess(); print(r['风险等级'], r['风险分数'])"`

---

### Task 4: 风险整合 — 晨报附件

**Files:**
- Create: `morning/risk_integration.py`

- [ ] **Step 1: 创建 risk_integration.py**

```python
"""
将风险预警结果作为晨报的附件追加发送
"""
def build_risk_section(risk_result: dict) -> str:
    """生成风险预警的 Markdown 段落，追加在晨报尾部"""
    ...
```

- [ ] **Step 2: 测试风险+晨报整合**

---

### Task 5: 创建 strategy/evolver.py — 遗传算法进化器

**Files:**
- Create: `strategy/evolver.py`
- Modify: `requirements.txt`（添加 deap）

- [ ] **Step 1: 实现遗传算法进化器**

```python
"""
策略参数进化器
使用 DEAP 库的遗传算法搜索最优策略参数组合

优化参数：
- min_score: 60-80（整数）
- entry_threshold: 7%-10%（连续值）
- default_first_time: 9:30/9:35/9:40/9:45/9:50（封板时间替代值）

适应度 = 年化收益×0.5 + 夏普比率×0.3 - 最大回撤×0.2
"""
import random
from deap import base, creator, tools, algorithms

class StrategyEvolver:
    def __init__(self, config: dict):
        self.pop_size = config.get("population_size", 30)
        self.generations = config.get("generations", 20)
        ...
    
    def evaluate(self, individual) -> tuple:
        """适应度函数：回测当前参数并计算得分"""
        ...
    
    def evolve(self) -> dict:
        """运行进化算法，返回最优参数"""
        ...
    
    def generate_report(self, best, logbook) -> str:
        """生成文本报告"""
        ...
```

- [ ] **Step 2: 安装 deap 依赖**

Run: `pip install deap`

- [ ] **Step 3: 测试进化器**

Run: `python -c "from strategy.evolver import StrategyEvolver; e=StrategyEvolver({}); print('进化器导入成功')"`

---

### Task 6: 创建 main.py — 统一入口

**Files:**
- Create: `main.py`
- Modify: `run_morning.py` → 简化，只保留 morning 模块独立入口

- [ ] **Step 1: 创建 main.py**

```python
#!/usr/bin/env python3
"""
StockStrategySystem — 量化策略研究与预警系统
统一入口，支持命令行参数运行各模块

用法:
    python main.py --morning       仅运行晨报+风险预警
    python main.py --risk          仅运行风险预警
    python main.py --evolution     仅运行策略进化
    python main.py --update_data   仅更新历史数据
    python main.py --all           按定时任务配置运行（常驻进程模式）
"""
import argparse
import logging
import sys
from pathlib import Path

def setup_logging(config: dict):
    ...

def cmd_morning():
    """抓取新闻 → AI 分析 → 风险预警 → 钉钉推送"""
    ...

def cmd_risk():
    """仅风险预警分析"""
    ...

def cmd_evolution():
    """运行遗传算法进化"""
    ...

def cmd_update_data():
    """更新历史数据"""
    ...

def cmd_all():
    """常驻进程模式，按定时任务运行"""
    import schedule
    import time
    # 设置所有定时任务
    while True:
        schedule.run_pending()
        time.sleep(30)

def main():
    parser = argparse.ArgumentParser(description="StockStrategySystem")
    parser.add_argument("--morning", action="store_true")
    parser.add_argument("--risk", action="store_true")
    parser.add_argument("--evolution", action="store_true")
    parser.add_argument("--update_data", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    
    if args.morning: cmd_morning()
    elif args.risk: cmd_risk()
    elif args.evolution: cmd_evolution()
    elif args.update_data: cmd_update_data()
    elif args.all: cmd_all()
    else: parser.print_help()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 测试各 CLI 参数**

Run: `python main.py --help`

---

### Task 7: 创建 scheduler/tasks.py — 调度整合

**Files:**
- Create: `scheduler/__init__.py`
- Create: `scheduler/tasks.py`

- [ ] **Step 1: 实现定时任务注册**

```python
"""
定时任务定义
"""

def register_tasks(config: dict):
    import schedule
    
    # 每个交易日 8:30 晨报+风险预警
    if config.get("morning", {}).get("enabled", True):
        schedule.every().day.at(config["morning"]["schedule_time"]).do(morning_job)
    
    # 每个交易日 15:30 更新数据
    if config.get("data_update", {}).get("enabled", True):
        schedule.every().day.at(config["data_update"]["schedule_time"]).do(update_data_job)
    
    # 每周五 16:00 策略进化
    if config.get("evolution", {}).get("enabled", True):
        schedule.every().friday.at(config["evolution"]["schedule_time"]).do(evolution_job)
```

---

### Task 8: 完善 README.md 和 requirements.txt

- [ ] **Step 1: 更新 requirements.txt 添加依赖**

添加：`deap>=1.4.1`, `schedule>=1.2.0`, `pyyaml>=6.0`, `python-dotenv>=1.0.0`

- [ ] **Step 2: 编写 README.md**

包含：安装步骤、config.yaml 配置说明、运行方法、常见问题

---

### Task 9: 端到端集成测试

- [ ] **Step 1: 测试新闻晨报完整流程**
Run: `python main.py --morning`（先 --dry-run 模式）

- [ ] **Step 2: 测试风险预警独立运行**
Run: `python main.py --risk`

- [ ] **Step 3: 测试策略进化运行**
Run: `python main.py --evolution`（短数据测试）

