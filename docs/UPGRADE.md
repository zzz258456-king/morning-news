# StockStrategySystem 升级架构指南

> 本文档说明系统的架构设计、扩展点，以及如何安全地添加新功能。

---

## 一、架构总览

```
main.py (CLI 路由 + 交互菜单)
   │
   ├── config.yaml ←─── 统一配置入口（所有模块从这里读配置）
   │
   ├── morning/     ←─── 新闻晨报模块
   │   └── risk_integration.py ←── 扩展点：可追加更多"附件"段
   │
   ├── risk/        ←─── 风险预警模块
   │   └── risk_engine.py ←── 扩展点：可添加更多评分维度
   │
   ├── strategy/    ←─── 策略回测模块
   │   └── evolver.py ←── 扩展点：可添加更多优化参数/适应度函数
   │
   └── scheduler/   ←─── 定时调度模块
       └── tasks.py ←── 扩展点：可注册新定时任务
```

## 二、扩展点（已预留）

### 2.1 添加新模块

```python
# 1. 创建 mymodule/ 目录
# 2. 在 main.py 中添加 CLI 参数和 cmd_xxx() 函数
# 3. 在 config.yaml 中添加配置段
# 4. 在 scheduler/tasks.py 中添加定时任务

# main.py 模板：
parser.add_argument("--my-feature", action="store_true", help="新功能说明")
# ...
elif args.my_feature:
    cmd_my_feature()
```

### 2.2 配置扩展（config.yaml）

在 `config.yaml` 任意位置添加新配置节，无需修改代码即可被 `morning/config.py` 读取：

```yaml
# config.yaml 扩展模板
my_new_module:
  enabled: true
  schedule_time: "09:00"
  # 自定义参数...
```

`morning/config.py` 已支持自动读取所有 YAML 节，只需添加对应的 Config 类即可。

### 2.3 风险评分扩展

在 `risk/risk_engine.py` 的 `RiskWarningEngine.assess()` 方法中添加新维度评分：

```python
# 新增维度示例：市场波动率评分
def _score_volatility(self, vix_value: float) -> tuple[float, str]:
    if vix_value < 20:
        return 0.0, "波动正常"
    elif vix_value < 30:
        return 1.0, "波动偏高"
    else:
        return 2.0, "波动剧烈"
```

### 2.4 进化器参数扩展

在 `strategy/evolver.py` 的 `PARAM_BOUNDS` 字典中添加新参数：

```python
PARAM_BOUNDS = {
    # ... 现有参数 ...
    "my_new_param": (0.0, 1.0, float),  # (最小值, 最大值, 类型)
}
```

### 2.5 晨报附件扩展

在 `morning/risk_integration.py` 同级添加新的附件段生成函数，然后在 `main.py` 的 `cmd_morning()` 中组合：

```python
# morning/sentiment_integration.py
def build_sentiment_section(sentiment_data: dict) -> str:
    return "## 市场情绪\n..."
```

## 三、升级流程

### 3.1 源码升级（开发环境）

```bash
# 1. 拉取新代码
git pull

# 2. 更新依赖
pip install -r requirements.txt

# 3. 测试
python main.py --dry-run
```

### 3.2 重新打包（生产环境）

```bash
python build.py
```

### 3.3 数据兼容

- 缓存文件在 `data/raw/risk_cache/` 下，按日期命名，新版本自动读取
- 配置文件 `config.yaml` 向后兼容——新版本会为缺失的配置项使用默认值
- 日志文件自动轮转，不影响升级

## 四、版本规划建议

| 版本 | 建议功能 | 涉及模块 |
|------|---------|---------|
| v2.1 | 多数据源支持（baostock 增量更新） | strategy/data_fetcher.py |
| v2.2 | 微信/飞书推送 | 新建 morning/feishu_sender.py |
| v2.3 | 板块热度追踪 | 新建 sector/ 模块 |
| v2.4 | 实时盯盘 + 盘中预警 | 新建 monitor/ 模块 |
| v2.5 | Web 管理面板 | 新建 web/ 模块 |
| v2.6 | 多策略组合回测 | strategy/portfolio.py |
| v2.7 | AI 复盘总结 | morning/ai_analyzer.py 扩展 |
