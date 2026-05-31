# 🚀 全能数据平台

集**网页爬虫**、**数据分析**、**机器学习**、**Web服务**和**桌面应用**为一体的综合性数据平台。

## 快速开始

### 1. 激活虚拟环境

```bash
.\.venv\Scripts\Activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行

```bash
# 交互式菜单
python main.py

# 或直接指定模式
python main.py web        # Web服务 (http://127.0.0.1:8000)
python main.py desktop    # 桌面应用 (PyQt6)
python main.py crawler    # 命令行爬虫
python main.py analyze    # 命令行数据分析
```

## 项目结构

```
├── main.py                 # 主入口
├── config.py               # 全局配置
├── requirements.txt        # 依赖清单
├── crawler/                # 爬虫模块
│   ├── base_crawler.py     #   爬虫基类
│   ├── web_scraper.py      #   数据采集器
│   └── scheduler.py        #   任务调度器
├── analyzer/               # 数据分析模块
│   ├── data_processor.py   #   数据处理
│   ├── visualizer.py       #   可视化引擎
│   └── ml_model.py         #   机器学习模型
├── web_app/                # Web应用模块
│   ├── app.py              #   FastAPI 应用
│   ├── routes/             #   API 路由
│   └── templates/          #   HTML 模板
├── desktop/                # 桌面应用模块
│   ├── main_window.py      #   主窗口
│   ├── crawler_panel.py    #   爬虫面板
│   ├── analysis_panel.py   #   分析面板
│   └── dashboard_panel.py  #   仪表盘
└── data/                   # 数据目录
    ├── raw/                #   原始数据
    └── processed/          #   处理后数据
```

## 功能特性

### 🕷️ 网页爬虫
- 支持单页和批量爬取
- 表格数据自动提取
- 文章内容智能抽取
- 定时任务自动执行
- 数据导出 CSV / JSON

### 📊 数据分析
- CSV/JSON/Excel 数据加载
- 自动数据清洗
- 统计分析摘要
- 7种图表可视化（折线、柱状、饼图、直方图、散点、热力、箱线）
- 数据导出

### 🤖 机器学习
- 分类模型（逻辑回归、随机森林、SVM）
- 回归模型（线性回归、随机森林）
- 聚类分析（K-Means）
- 模型评估与交叉验证
- 网格搜索调参

### 🌐 Web 服务
- FastAPI 高性能后端
- RESTful API 接口
- Swagger 自动文档
- 可视化仪表盘
- 爬虫管理面板

### 🖥️ 桌面应用
- PyQt6 原生界面
- 多标签页管理
- 实时数据图表
- 文件导入导出
