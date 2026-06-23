# DPPT Web 应用实现计划

> 将 `ppt-from-outline-to-delivery` 技能封装为可视化前端应用。

## 目标

搭建一个可运行的 DPPT Web MVP：用户通过浏览器完成「大纲输入 → 模板选择 → 图片配置 → 生成检查 → 下载 PPTX」的完整流程，后端调用 Claude Code + dppt 技能完成生成。

## 阶段与优先级

### Phase 1: 项目骨架初始化（20 分钟）
- [x] 在 `C:\Users\Administrator\Desktop\_Projects\try\dppt-web\` 创建前后端目录
- [x] 初始化 React + Vite 前端项目
- [x] 初始化 FastAPI 后端项目
- [x] 配置跨域与启动脚本
- Status: complete

### Phase 2: 后端核心接口（30 分钟）
- [x] 实现 `/api/projects` 创建项目
- [x] 实现 `/api/projects/{id}/outline` 大纲上传与解析
- [x] 实现 `/api/projects/{id}/templates` 模板方案获取
- [x] 实现 `/api/projects/{id}/templates/refresh` 模板刷新
- [x] 实现 `/api/projects/{id}/generate` 调用 Claude 生成 PPTX
- [x] 实现 `/api/projects/{id}/download` 文件下载
- Status: complete

### Phase 3: 前端步骤向导（40 分钟）
- [x] 搭建顶部进度条 + 步骤内容区 + 底部导航
- [x] 步骤一：大纲输入（文本框 + 多格式文件上传 + 解析预览）
- [x] 步骤二：模板选择（卡片网格 + 刷新 + 比例切换）
- [x] 步骤三：图片配置（逐页卡片 + 本地上传 + 跳过）
- [x] 步骤四：页面编辑（三栏布局 + 实时预览）
- [x] 步骤五：检查生成（检查清单 + 生成按钮 + 下载）
- Status: complete

### Phase 4: 前后端联调与生成验证（30 分钟）
- [x] 打通从前端到 Claude 的完整链路
- [x] 使用示例大纲验证 PPTX 可正常生成
- [x] 处理常见错误（解析失败、生成超时、检查未通过）
- Status: complete

### Phase 5: 测试与收尾（20 分钟）
- [x] 前后端基础测试
- [x] 更新 `progress.md`
- [x] 向用户汇报成果
- Status: complete

## 技术栈

- 前端：React 18 + Vite + Tailwind CSS + Axios
- 后端：Python 3.11 + FastAPI + Uvicorn
- AI 后端：Claude Code CLI / MCP + `ppt-from-outline-to-delivery` 技能
- 文件存储：`D:\缓存区\dppt-web\`

## 风险与应对

| 风险 | 应对 |
|------|------|
| 前端依赖安装慢 | 使用 npm 淘宝镜像 |
| Claude CLI 调用不稳定 | 增加超时与重试机制 |
| 文件上传格式解析复杂 | MVP 先支持 txt/md/docx/pdf/pptx |
| 跨域问题 | FastAPI 配置 CORS |

## 备注

- 所有中间过渡文件放 `D:\缓存区\dppt-web\`
- 项目代码严格限定在 `C:\Users\Administrator\Desktop\_Projects\try\dppt-web\`
- MVP 优先跑通完整链路，页面编辑和图片搜索的细节可二期优化
