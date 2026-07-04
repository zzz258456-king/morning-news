# DPPT Web 后端容器
# 构建：docker build -t dppt-web-backend .
# 运行：docker run -p 8000:8000 --env DATABASE_URL=... dppt-web-backend

FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（PostgreSQL 客户端库、构建工具）
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖并安装，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露 FastAPI 默认端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
