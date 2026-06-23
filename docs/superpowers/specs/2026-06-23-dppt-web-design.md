# DPPT Web 应用设计文档

> 将 `ppt-from-outline-to-delivery` 技能封装为可视化前端应用。  
> 版本：v1.0（MVP）  
> 日期：2026-06-23

---

## 1. 概述

DPPT Web 是一个面向 PPT 生成的 Web 应用。用户在浏览器中完成「大纲输入 → 模板选择 → 图片配置 → 页面编辑 → 检查生成」的全流程，后端通过调用 Claude Code + `ppt-from-outline-to-delivery` 技能完成 `.pptx` 文件生成。

### 1.1 目标

- 把 dppt 技能中的配置步骤（模板、图片、布局）变为可视化点选。
- 降低用户使用门槛：不需要记忆命令或手动组织提示词。
- 保留后端由 Claude 处理复杂判断（模板匹配、图片搜索、生成检查）的能力。

### 1.2 非目标

- 不替代 Claude 的生成能力：前端只做参数收集和结果展示，PPT 生成仍由后端完成。
- 不做在线协作、版本管理、用户系统等非核心功能。

---

## 2. 技术方案

采用 **Web 前端 + Python FastAPI 后端** 架构。

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React 18 + Vite + Tailwind CSS | 组件化界面、热重载、响应式布局 |
| 后端 | Python 3.11 + FastAPI | 接收前端请求、调用 Claude Code CLI、返回生成结果 |
| 文件存储 | 本地临时目录（`D:\缓存区\dppt-web\`） | 上传文件、生成中间文件、最终 PPTX 均存放于此 |
| AI 后端 | Claude Code CLI / MCP | 由后端封装用户选择为提示词，调用 dppt 技能 |

**选择理由**：开发周期最短，与现有 Python 项目生态一致，跨平台运行无额外成本。

---

## 3. 系统架构

```
┌─────────────────┐      HTTP/JSON       ┌──────────────────┐
│   React 前端     │  ──────────────────▶ │  FastAPI 后端     │
│                 │                      │                  │
│ - 大纲输入       │                      │ - 接收用户配置    │
│ - 模板选择       │                      │ - 调用 Claude CLI │
│ - 图片搜索/上传  │                      │ - 管理文件目录    │
│ - 页面编辑       │                      │ - 返回生成状态    │
│ - 检查生成       │                      │                  │
└─────────────────┘                      └────────┬─────────┘
                                                  │
                                                  ▼
                                         ┌──────────────────┐
                                         │  Claude Code      │
                                         │  + dppt skill     │
                                         │                  │
                                         │ - 模板匹配        │
                                         │ - 图片搜索        │
                                         │ - PPTX 生成       │
                                         └──────────────────┘
```

---

## 4. 数据流

### 4.1 核心流程

1. **用户提交大纲**：前端上传文本/文档/PPT，后端解析为结构化页面列表。
2. **用户选择模板**：前端展示候选模板；用户可点击「刷新」重新搜索/生成模板方案。
3. **图片配置**：前端按页展示自动搜索的候选图，用户可确认/替换/上传本地图/跳过。
4. **页面编辑**：用户调整每页标题、正文、图片位置和布局。
5. **生成请求**：前端打包完整配置，后端调用 Claude 生成 PPTX。
6. **结果返回**：后端返回文件路径/下载链接，前端提供下载。

### 4.2 关键数据结构

```typescript
interface ProjectConfig {
  id: string;
  title: string;
  outline: OutlinePage[];
  template: TemplateOption;
  slides: SlideConfig[];
  outputPath?: string;
}

interface OutlinePage {
  id: string;
  title: string;
  content?: string;
  notes?: string;
}

interface TemplateOption {
  id: string;
  name: string;
  colors: string[];
  layout: '16:9' | '4:3';
  source: 'builtin' | 'search';
}

interface SlideConfig {
  pageId: string;
  title: string;
  body: string;
  image?: {
    source: 'search' | 'upload' | 'none';
    url?: string;
    localPath?: string;
    position: 'left' | 'right' | 'center' | 'banner' | 'corner';
  };
  layout: string;
}
```

---

## 5. 界面设计

### 5.1 整体布局

采用 **顶部进度条 + 下方内容区** 的向导式布局。

```
┌─────────────────────────────────────────────┐
│  DPPT Web              [1] [2] [3] [4] [5]  │  <- 顶部导航/进度
├─────────────────────────────────────────────┤
│                                             │
│              步骤内容区                      │
│        （根据当前步骤显示不同面板）           │
│                                             │
├─────────────────────────────────────────────┤
│  [上一步]                         [下一步]   │
└─────────────────────────────────────────────┘
```

### 5.2 步骤一：输入大纲

- **文本输入区**：支持 Markdown / 纯文本粘贴。
- **文件上传**：支持 `.txt`、`.md`、`.docx`、`.pdf`、`.pptx`、`.ppt` 等格式。
- **解析预览**：右侧显示解析后的页面结构，可手动增删改。

### 5.3 步骤二：选择模板

- **模板卡片网格**：展示 2-4 个候选模板，每张卡片包含配色预览、风格名称、适用场景。
- **刷新按钮**：用户点击后，后端重新搜索/生成新的模板方案。
- **比例切换**：16:9 / 4:3。

### 5.4 步骤三：图片配置

- **逐页卡片**：每页显示标题、自动搜索的候选图（3-6 张）。
- **操作按钮**：使用此图、搜索更多、上传本地图片、跳过此页。
- **图片来源**：开放期刊、arXiv、免费图库；上传图片保存到本地临时目录。

### 5.5 步骤四：页面编辑

- **三栏布局**：
  - 左侧：页面缩略图列表，可拖拽排序。
  - 中间：PPT 页面实时预览（简化版）。
  - 右侧：属性面板，可编辑标题、正文、选择图片位置、布局模板。

### 5.6 步骤五：检查与生成

- **检查清单**：
  - [ ] 所有占位符已替换
  - [ ] 图片不裁切关键内容
  - [ ] 配色统一
  - [ ] 每页有视觉元素
- **生成按钮**：检查通过后启用。
- **下载区域**：生成成功后显示文件信息和下载按钮。

---

## 6. API 设计

### 6.1 后端接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects` | 创建新项目 |
| POST | `/api/projects/{id}/outline` | 上传/解析大纲 |
| GET  | `/api/projects/{id}/outline` | 获取解析后的大纲 |
| POST | `/api/projects/{id}/templates` | 获取模板方案（首次） |
| POST | `/api/projects/{id}/templates/refresh` | 刷新模板方案 |
| POST | `/api/projects/{id}/slides/{pageId}/images` | 搜索某页配图 |
| POST | `/api/projects/{id}/slides/{pageId}/images/upload` | 上传本地图片 |
| PUT  | `/api/projects/{id}/slides` | 更新页面配置 |
| POST | `/api/projects/{id}/generate` | 调用 Claude 生成 PPTX |
| GET  | `/api/projects/{id}/download` | 下载生成的 PPTX |

### 6.2 与 Claude 的交互

后端把 `ProjectConfig` 序列化为一段结构化提示词，调用 Claude Code CLI：

```bash
claude "根据以下配置，使用 ppt-from-outline-to-delivery 技能生成 PPT：..."
```

Claude 执行生成后，将 `.pptx` 保存到项目临时目录，后端返回该路径。

---

## 7. 项目结构

```
dppt-web/
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/       # 通用组件
│   │   ├── pages/            # 步骤页面
│   │   ├── hooks/            # 自定义 hooks
│   │   ├── api.ts            # 后端 API 封装
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── projects.py
│   │   │   ├── outline.py
│   │   │   ├── templates.py
│   │   │   ├── images.py
│   │   │   └── generate.py
│   │   ├── services/
│   │   │   ├── claude_service.py
│   │   │   ├── outline_parser.py
│   │   │   └── image_search.py
│   │   └── models.py
│   ├── requirements.txt
│   └── run.py
└── README.md
```

---

## 8. 依赖

### 8.1 前端

```bash
npm install react react-dom react-router-dom axios
npm install -D vite tailwindcss postcss autoprefixer @types/react @types/react-dom
```

### 8.2 后端

```bash
pip install fastapi uvicorn python-multipart aiofiles
pip install python-pptx Pillow markitdown
```

---

## 9. 错误处理

| 场景 | 处理策略 |
|------|----------|
| 大纲解析失败 | 返回原始文本，提示用户手动校对 |
| 模板刷新无新结果 | 前端提示「已尝试其他风格」，保留上次结果 |
| 图片搜索无结果 | 显示「未找到配图」，提供上传入口 |
| Claude 生成超时 | 返回超时提示，保留配置，支持重试 |
| 生成检查未通过 | 标红未通过项，阻止生成并给出修改建议 |

---

## 10. 测试

- **前端**：Vitest + React Testing Library，覆盖步骤导航、表单提交、文件上传。
- **后端**：pytest，覆盖 API 路由、大纲解析、Claude 调用封装。
- **端到端**：Playwright（可选，二期），覆盖完整生成流程。

---

## 11. 二期功能

- 模板收藏与历史复用。
- 多语言大纲识别与翻译。
- 生成后在线预览 PPT（转为图片）。
- 批量生成/对比多个版本。

---

## 12. 验收标准

- [ ] 用户可通过界面完成从大纲输入到 PPT 下载的完整流程。
- [ ] 支持文本粘贴、Markdown、Word、PDF、PPT 等多种大纲输入方式。
- [ ] 模板选择支持刷新，能基于搜索返回新方案。
- [ ] 图片配置支持自动搜索、本地上传、跳过三种方式。
- [ ] 生成前检查清单明确标红未通过项。
- [ ] 最终生成文件可在浏览器中下载。
