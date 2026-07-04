# DPPT Pro

商业级本地 PPT 生成引擎，采用 **DSL → Renderer → Checker** 三段式架构，对标 Kimi PPT 实现。

## 项目结构

```
dppt-pro/
├── dppt/                 # 核心 Python 包
│   ├── ai_generator.py   # AI 自动生成 DSL
│   ├── parser.py         # .dppt YAML 解析器
│   ├── models.py         # DSL 数据模型
│   ├── theme.py          # 主题引用解析
│   ├── renderer.py       # PPTX 渲染器
│   ├── checker.py        # 质量检查器
│   ├── utils.py          # 工具函数
│   └── __main__.py       # 命令行入口
├── scripts/
│   ├── generate_with_ai.py # AI 一键生成 PPTX
│   └── outline_to_dppt.py  # 大纲 → DSL 转换器
├── templates/
│   ├── themes/           # 主题模板
│   └── layouts/          # 页面布局模板
├── examples/             # 示例 .dppt / outline 文件
├── tests/                # 单元测试
├── SKILL.md              # Claude Skill 文档
└── requirements.txt
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
python -m pytest tests/ -v

# 方式一：AI 一键生成（需要 ANTHROPIC_API_KEY）
python scripts/generate_with_ai.py "主题" output.pptx --pages 6 --style business

# 方式二：直接渲染 DSL
python -m dppt examples/z-generation.dppt output.pptx

# 方式三：从大纲生成 DSL，再渲染
python scripts/outline_to_dppt.py examples/outline.yaml output.dppt
python -m dppt output.dppt output.pptx

# 仅检查 DSL
python -m dppt examples/z-generation.dppt output.pptx --check
```

## DSL 示例

```yaml
version: "0.1"
title: 演示标题
theme:
  name: business
  colors:
    primary: "#1E3A8A"
    text: "#1F2937"
  fonts:
    heading: "Microsoft YaHei"
  text_styles:
    title:
      font_family: "$heading"
      font_size: 44pt
      color: "$primary"
      bold: true
pages:
  - type: cover
    title: 封面标题
    elements:
      - type: text
        text: 封面标题
        style: $title
        bounds: {x: 1, y: 2.5, width: 11, height: 1.2}
```

## 支持的页面布局

`scripts/outline_to_dppt.py` 可识别 `layout` 字段自动套用版式；未指定时根据内容自动推断：

- `cover` / `toc` / `closing`：经典结构
- `title-only`：章节分隔页
- `two-column`：左文右卡片
- `three-column`：三栏并列
- `image-left` / `image-right`：图文混排
- `timeline`：水平时间轴
- `team`：团队头像 + 职位
- `quote`：金句引用页
- `data-cards`：KPI 数字卡片
- `comparison`：左右方案对比
- `chart`：数据图表

## 支持的元素

- `text`：文本框
- `shape`：矩形、圆角矩形、椭圆、三角形、箭头
- `image`：本地图片
- `icon`：SVG 图标（内置图标库 / SVG path / SVG 文件）
- `table`：表格
- `chart`：柱状图、折线图、饼图

## 主题引用

- 颜色：`$primary`
- 字体：`$heading`
- 文本样式：`$title`

## 检查器

自动检测：
- 文档格式问题
- 元素溢出页面边界
- 文本对比度过低
- 图片资源缺失

## 动画与母版

- 渲染器默认会为内容元素（文本、图片、图标、表格、图表）添加淡入（fade）入场动画，单击逐条出现。
- 可通过 `--master` 参数传入自定义 PowerPoint 母版模板，继承其尺寸、布局与视觉风格：
  ```bash
  python -m dppt input.dppt output.pptx --master templates/masters/animated.pptx
  ```
- 如需关闭动画，可在使用 `DpptRenderer` 时设置 `enable_animation=False`。

## 许可

仅供个人学习与小范围使用，商用需自行承担合规责任。
