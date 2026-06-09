# 晨报系统

A股财经新闻晨报系统，支持异动监控、晚间回溯、特别关注、操作日志等功能。

## 功能模块

### 1. 晨报
- 抓取财经新闻（RSS/API）
- AI 分析（DeepSeek API）
- 钉钉推送

### 2. 异动监控
- 宏观经济（美联储利率、CPI）
- 大宗商品（期货、黄金）
- 科技赛道（AI、芯片、新能源）
- 突发事件（政策、地缘政治）
- 量化评分（0-100分），60分阈值推送

### 3. 晚间回溯
- 跟踪推荐股票（5天）
- 跟踪特别关注股票（持续）
- 获取完整行情数据（OHLC + 成交量 + 换手率）
- 生成跟踪报告

### 4. 特别关注
- 添加/删除关注股票
- 分组管理（短线/中线/长线）
- 持续跟踪

### 5. 操作日志
- 记录买入/卖出操作
- 情绪标签（自信/犹豫/恐惧/贪婪/平静）
- 交易标签（技术面/基本面/消息面/资金面）
- 复盘报告（胜率、盈亏比、情绪分析）

### 6. 数据库管理
- 每日独立数据库
- 全局数据库（特别关注、操作日志）
- 备份和清理

## 安装

```bash
# 克隆项目
git clone <repository-url>
cd try

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入 API 密钥：
   - `DEEPSEEK_API_KEY` - DeepSeek API 密钥
   - `DINGTALK_WEBHOOK_URL` - 钉钉 Webhook URL
   - `DINGTALK_SECRET` - 钉钉签名密钥（可选）

## 使用

### 命令行模式

```bash
# 晨报流程
python run_morning.py                    # 完整晨报
python run_morning.py --dry-run          # 预览不推送

# 异动监控
python run_morning.py --anomaly          # 运行异动监控

# 晚间回溯
python run_morning.py --track            # 运行晚间回溯
python run_morning.py --track --days 10  # 指定跟踪天数

# 特别关注
python run_morning.py --watch add 000001 平安银行 --reason "突破年线" --group 短线
python run_morning.py --watch list
python run_morning.py --watch remove 000001

# 操作日志
python run_morning.py --trade buy 000001 10.83 1000 --reason "突破年线" --emotion 自信
python run_morning.py --trade sell 000001 11.13 1000 --reason "止盈" --emotion 犹豫
python run_morning.py --trade review --days 30

# 数据库管理
python run_morning.py --db-status        # 查看状态
python run_morning.py --db-backup        # 备份数据库
python run_morning.py --db-cleanup       # 清理旧数据
```

### Web UI 模式

```bash
# 启动 Web UI
python run_morning.py --web

# 自定义端口
python run_morning.py --web --web-port 8080

# 详细日志
python run_morning.py --web -v
```

然后浏览器访问 `http://localhost:5000`

### 打包为可执行程序

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller morning.spec

# 生成的可执行文件在 dist/morning.exe
```

## 项目结构

```
try/
├── morning/                    # 核心模块
│   ├── __init__.py
│   ├── config.py              # 配置模块
│   ├── news_fetcher.py        # 新闻抓取
│   ├── ai_analyzer.py         # AI 分析
│   ├── dingtalk_sender.py     # 钉钉推送
│   ├── fundamental_analyzer.py # 基本面分析
│   ├── anomaly_monitor.py     # 异动监控
│   ├── stock_tracker.py       # 晚间回溯
│   ├── watchlist_manager.py   # 特别关注
│   ├── trade_journal.py       # 操作日志
│   ├── db_manager.py          # 数据库管理
│   ├── web_server.py          # Web UI 服务器
│   ├── templates/             # HTML 模板
│   └── static/                # 静态资源
├── tests/                     # 测试文件
├── data/                      # 数据目录
│   ├── daily/                 # 每日数据库
│   ├── global.db              # 全局数据库
│   └── backup/                # 备份目录
├── config.yaml                # 配置文件
├── .env                       # 环境变量
├── requirements.txt           # 依赖列表
├── run_morning.py             # 主入口
└── morning.spec               # PyInstaller 配置
```

## 配置说明

### config.yaml

```yaml
# 异动监控
anomaly_monitor:
  enabled: true
  push_threshold: 60  # 推送阈值（0-100）

# 晚间回溯
stock_tracker:
  enabled: true
  tracking_days: 5  # 跟踪天数

# 特别关注
watchlist:
  enabled: true
  groups:
    - name: "短线"
    - name: "中线"
    - name: "长线"

# 操作日志
trade_journal:
  enabled: true
  emotion_tags: ["自信", "犹豫", "恐惧", "贪婪", "平静"]
  trade_tags: ["技术面", "基本面", "消息面", "资金面"]

# 数据库
database:
  daily_path: "data/daily"
  global_path: "data/global.db"
  backup_days: 30
  cleanup_days: 90
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_db_manager.py -v
pytest tests/test_anomaly_monitor.py -v
```

## 常见问题

### Q: 如何修改推送阈值？
A: 编辑 `config.yaml` 中的 `anomaly_monitor.push_threshold`

### Q: 如何添加新的 RSS 源？
A: 编辑 `config.yaml` 中的 `morning.rss_sources`

### Q: 数据库在哪里？
A: 每日数据库在 `data/daily/` 目录，全局数据库在 `data/global.db`

### Q: 如何备份数据？
A: 运行 `python run_morning.py --db-backup`

## 许可证

MIT License
