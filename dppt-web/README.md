# DPPT Web

将 `ppt-from-outline-to-delivery` 技能封装为可视化 Web 应用。

## 启动方式

### 1. 启动后端

```bash
cd backend
.venv\Scripts\python run.py
```

或在项目根目录双击 `start_backend.bat`。

后端默认运行在 http://localhost:8000

### 2. 启动前端

```bash
cd frontend
npm run dev
```

或在项目根目录双击 `start_frontend.bat`。

前端默认运行在 http://localhost:5173

## 项目结构

```
dppt-web/
├── frontend/          # React + Vite + Tailwind CSS
├── backend/           # FastAPI + Python
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   └── services/
│   └── .venv/
├── start_frontend.bat
└── start_backend.bat
```

## 开发状态

- [x] 项目骨架初始化
- [ ] 后端核心接口
- [ ] 前端步骤向导
- [ ] 前后端联调
- [ ] 测试与收尾
