---
name: dppt-pro
description: Use when generating commercial-grade PPT from outline or content with DPPT Pro engine
---

# DPPT Pro

## Overview

DPPT Pro 是本地商业级 PPT 生成引擎，采用 **DSL → Renderer → Checker** 三段式架构，直接对标 Kimi PPT 商业化实现。

核心思想：
- 用 `.dppt` YAML 描述内容、样式、布局、主题；
- 渲染器负责把 DSL 转成 `.pptx`；
- 检查器自动发现溢出、低对比度、格式问题。

## When to Use

- 用户要求生成高质量 PPT；
- 需要比 dppt-web 更精细的版式控制；
- 需要自定义主题、图表、表格、图片混排。

## Workflow

### 方式一：AI 一键生成（推荐）

```
用户输入主题/需求
    ↓
AI 生成 outline.yaml
    ↓
outline_to_dppt.py 转成 .dppt DSL
    ↓
主题解析 → 质量检查 → 渲染 PPTX
    ↓
交付 .pptx
```

命令：
```bash
cd C:\Users\Administrator\Desktop\_Projects\try\dppt-pro
python scripts/generate_with_ai.py "主题" "D:\缓存区\dppt-pro\输出.pptx" --pages 6 --style business --audience "受众" --extra "补充要求"
```

### 方式二：手动编写 DSL

```
用户输入 → 编写 .dppt DSL → 主题解析 → 质量检查 → 渲染 PPTX → 交付
```

## 生成 DSL 的 AI 流程

当用户请求生成 PPT 时：

1. **理解需求**：确认主题、目标受众、页数、风格（business/tech/academic）。
2. **选择主题**：从 `templates/themes/` 选择最接近的主题（business/tech/academic）。
3. **一键生成**：
   ```bash
   python scripts/generate_with_ai.py "主题" "D:\缓存区\dppt-pro\<项目>.pptx" --pages 6 --style business
   ```
4. **检查并修复**：如果检查器报错，查看中间 `.dppt` 文件，修改后重新渲染。
5. **交付**：把最终 `.pptx` 路径告诉用户。

**何时手动写 outline**：当用户需要控制具体章节、特定数据、指定图片时，先生成 `outline.yaml`，再转换。

**何时直接写 .dppt**：当用户需要精细控制每个元素的 bounds、自定义形状、图片、表格时，直接编写 `.dppt` DSL。

## DSL 核心结构

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
    background: {type: solid, color: "$background"}
    elements:
      - type: text
        text: 封面标题
        style: $title
        bounds: {x: 1, y: 2.5, width: 11, height: 1.2}
```

## 支持的页面布局

outline 中的 `layout` 字段决定版式；未指定时按内容自动推断：

| 布局 | 触发条件/字段 | 说明 |
|------|---------------|------|
| cover / toc / closing | 固定 type | 封面、目录、结束页 |
| title-only | `type: section` 或 `layout: title-only` | 章节分隔页，可用 `number` |
| two-column | `bullets` + `highlight` | 左文右卡片 |
| three-column | `columns` / `cards`（≥3） | 三栏并列 |
| image-left / image-right | `image` / `image_src` + `bullets` | 图文混排 |
| timeline | `steps` / `timeline` | 水平时间轴 |
| team | `members` / `team` | 团队介绍 |
| quote | `quote` / `source` | 金句引用 |
| data-cards | `stats` / `numbers` | KPI 数字卡片 |
| comparison | `left` + `right` | 左右对比 |
| chart | `series` + `labels` | 数据图表 |

## 支持的元素

| 元素 | 类型 | 说明 |
|------|------|------|
| text | Text | 文本框，支持样式引用 |
| shape | Shape | 矩形、圆角矩形、椭圆、箭头、三角形 |
| image | Image | 本地图片路径 |
| icon | Icon | SVG 图标（内置图标库 / SVG path / SVG 文件） |
| table | Table | 表格 |
| chart | Chart | 柱状图/折线图/饼图（matplotlib 生成） |

## 主题引用

- 颜色：`$primary`
- 字体：`$heading`
- 文本样式：`$title`

## 检查器

```python
from dppt import DpptChecker
ok, issues = DpptChecker.quick_check(doc)
```

## 命令行

```bash
python -m dppt input.dppt output.pptx
```

## 页面布局建议（英寸坐标）

- 画布尺寸：13.333 × 7.5（16:9）
- 页边距：左右 0.8，上下 0.6
- 标题区：y 0.6，高 0.9
- 内容区：y 1.7 开始

## 动画与母版

- 渲染器默认会为内容元素（文本、图片、图标、表格、图表）添加淡入（fade）入场动画，单击逐条出现。
- 可通过 `--master` 参数传入自定义 PowerPoint 母版模板，继承其尺寸、布局与视觉风格：
  ```bash
  python -m dppt input.dppt output.pptx --master templates/masters/animated.pptx
  ```
- 如需关闭动画，可在使用 `DpptRenderer` 时设置 `enable_animation=False`。

## 项目位置

`C:\Users\Administrator\Desktop\_Projects\try\dppt-pro`

## 反模式

- 不要手动逐个像素硬编码所有样式，优先使用主题引用；
- 不要在 DSL 中使用实际换行符表示文本换行，使用 `|` YAML 块标量；
- 不要跳过检查器直接交付；
- 不要把动画效果寄托在母版；渲染器已支持为内容元素添加入场动画，可通过 `enable_animation` 控制。
