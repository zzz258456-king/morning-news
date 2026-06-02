# 🚀 StockStrategySystem — 量化策略研究与预警系统

量化策略研究与预警系统，集成新闻晨报、风险预警、打板策略回测、遗传算法参数进化、定时调度等模块。

---

## 📦 环境要求

- Python 3.10+
- 虚拟环境（推荐）

```bash
# 激活虚拟环境
.\.venv\Scripts\Activate

# 安装依赖
pip install -r requirements.txt
```

---

## 🚀 快速开始

### 1. 配置

编辑项目根目录的 `config.yaml`，配置 API Key 等敏感信息放在 `.env` 中：

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-your-key-here
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=your-secret-here  # 可选，加签模式
```

### 2. 运行

```bash
# 查看帮助
python main.py

# 晨报干运行（抓取+分析，不推送）
python main.py --dry-run

# 完整晨报流程（抓取→分析→风险→推送）
python main.py --morning

# 仅风险预警
python main.py --risk

# 策略参数进化（遗传算法）
python main.py --evolution

# 常驻进程模式（按定时任务自动运行）
python main.py --all
```

---

## 📂 项目结构

```
try/
├── main.py                 # 统一入口（StockStrategySystem）
├── run.py                  # 旧入口（回测系统）
├── config.yaml             # 统一配置文件
├── config.py               # Python 配置常量
├── .env                    # 密钥文件
├── requirements.txt        # 依赖清单
│
├── morning/                # 📰 新闻晨报模块
│   ├── __init__.py
│   ├── config.py           # 配置加载（读取 config.yaml）
│   ├── news_fetcher.py     # RSS 新闻抓取
│   ├── ai_analyzer.py      # DeepSeek AI 分析
│   ├── dingtalk_sender.py  # 钉钉消息推送
│   └── risk_integration.py # 风险预警整合为晨报附件
│
├── risk/                   # 🛡️ 风险预警模块
│   ├── __init__.py
│   ├── risk_engine.py      # 综合风险评分引擎 (0-10分)
│   ├── data_provider.py    # 市场数据获取
│   └── calendar_effects.py # 日历效应统计
│
├── strategy/               # 📊 策略回测模块
│   ├── __init__.py
│   ├── base.py             # 策略基类
│   ├── board_chaser.py     # 打板策略 v3
│   ├── trend_follower.py   # 趋势跟踪策略
│   ├── backtest_engine.py  # 回测引擎
│   ├── data_fetcher.py     # 数据获取
│   ├── evolver.py          # 遗传算法进化器
│   └── risk_warning.py     # 旧版风险预警（已迁移）
│
├── scheduler/              # ⏰ 定时调度模块
│   ├── __init__.py
│   └── tasks.py            # 定时任务定义
│
├── data/                   # 数据目录
│   ├── raw/                # 原始数据
│   └── processed/          # 处理后数据
│
└── logs/                   # 日志目录
```

---

## 📰 新闻晨报模块

**功能：** 每日开盘前自动抓取财经新闻 → AI 分析 → 钉钉推送

**RSS 源配置：** 编辑 `config.yaml` 的 `morning.rss_sources` 列表

**周一模式：** 自动加大抓取量（50条/源），AI 汇总周末消息面

**数据流：**
```
RSS 源 → news_fetcher.py → 新闻列表
                                ↓
news_list → ai_analyzer.py → AnalysisResult (市场情绪/板块/个股)
                                ↓
AnalysisResult → dingtalk_sender.py → 钉钉 Markdown 推送
                                ↓
                    risk_integration.py → 风险预警追加
```

**运行方式：**
```bash
# 完整流程
python main.py --morning

# 干运行（不推送）
python main.py --dry-run
```

---

## 🛡️ 风险预警模块

**功能：** 综合评估大盘风险，输出 0-10 分评分

**评分维度（满分10分）：**

| 维度 | 分数 | 数据源 |
|------|:----:|--------|
| 涨跌家数比 | 0-3 | akshare 全市场涨跌统计 |
| 北向资金净流入 | 0-3 | akshare 沪/深港通数据 |
| 指数均线偏离度 | 0-3 | 上证指数 20/60 日均线 |
| 日历效应 | 0-1 | 历史星期几概率统计 |

**风险等级：**
- **0-3 分**：低风险 ✅ — 可正常交易
- **4-6 分**：中风险 ⚠️ — 控制仓位 ≤ 70%，暂停追高
- **7-10 分**：高风险 🔴 — 减仓至半仓以下，不开新仓

**独立运行：**
```bash
python main.py --risk
```

---

## 🧬 遗传算法进化器

**功能：** 使用 DEAP 库搜索最优策略参数组合

**优化参数（11个维度）：**

| 参数 | 范围 | 说明 |
|------|:----:|------|
| min_score | 8-28 | 打板评分最低阈值 |
| buy_timeout_minutes | 30-90 | 买入截止时间(距9:30分钟) |
| min_seal_ratio | 0.02-0.20 | 最小封单额/成交额比 |
| turnover_min | 1.0-8.0 | 最小换手率 % |
| turnover_max | 15.0-35.0 | 最大换手率 % |
| market_cap_min | 10-50 | 最小流通市值(亿) |
| profit_target | 0.03-0.12 | 止盈目标 |
| stop_loss | -0.08 至 -0.02 | 止损线 |
| trailing_stop | 0.01-0.05 | 回落止盈 |
| max_daily_buy | 1-5 | 每日最大买入数 |
| single_pct | 0.05-0.25 | 单票仓位占比 |

**适应度函数：** 年化收益×0.5 + 夏普比率×0.3 - 最大回撤×0.2

**运行：**
```bash
python main.py --evolution
```

**配置进化参数：** `config.yaml` → `evolution:` 节

---

## ⏰ 定时调度

**支持的定时任务：**

| 任务 | 默认时间 | 频率 |
|------|:--------:|:----:|
| 新闻晨报 + 风险预警 | 08:30 | 每个交易日 |
| 数据更新 | 15:30 | 每个交易日 |
| 策略进化 | 周五 16:00 | 每周 |

**常驻进程模式：**
```bash
python main.py --all
```

---

## ⚙️ 配置文件

`config.yaml` 是统一配置入口，涵盖所有模块参数：

```yaml
morning:
  enabled: true
  schedule_time: "08:30"
  rss_sources:
    - name: "36氪"
      url: "https://36kr.com/feed"
    - name: "东方财富"
      url: "https://finance.eastmoney.com/a/czqyw.html"
  max_news_per_source: 20
  monday_max_news: 50
```

详见 `config.yaml` 中的详细注释。

---

## 🔧 旧版兼容

- `run.py` — 旧版回测系统入口，仍保留
- `run_morning.py` — 旧版晨报入口，仍保留
- `strategy/risk_warning.py` — 旧版风险预警，功能已迁移至 `risk/` 模块

---

## 📊 全能数据平台

本仓库也包含原始的全能数据平台功能（网页爬虫、数据分析、ML、Web服务、桌面应用）：

```bash
# Web 服务 (FastAPI)
python run.py --gui      # 桌面应用
```

详情见各模块源代码。
