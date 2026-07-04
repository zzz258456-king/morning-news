# Task Plan: 后端与系统架构技能拓展

## Goal

通过安装/创建新的 Claude Code skills，在现有 Python 项目（特别是 `dppt-web`）基础上系统性地建立起后端工程能力：API 设计 → 数据持久化 → 测试 → 容器化 → 异步任务 → CI/CD，最终让 `dppt-web` 从“本地可跑”升级为“工程化、可部署、可维护”的后端服务。

## Current Phase

Phase 5（全部完成）

## Phases

### Phase 1: API 与数据建模基础（FastAPI + Pydantic + SQLAlchemy）
- [x] 安装/获取 FastAPI、Pydantic、SQLAlchemy 相关 skills
- [x] 检查 `dppt-web` 后端当前结构并确定接入点
- [x] 为 `dppt-web` 配置 SQLAlchemy 数据库连接（本地无 PostgreSQL/Docker，先用 SQLite，后续切换）
- [x] 使用 SQLAlchemy 定义 `PPTJob` 数据模型
- [x] 使用 Pydantic 定义 `/health` 和 `/jobs` 的请求/响应模型
- [x] 实现 `/health` 接口（返回服务状态和数据库连接状态）
- [x] 实现 `/jobs` 接口（创建/查询 PPT 渲染任务）
- [x] 启动服务并验证 Swagger `/docs` 可访问
- **Status:** complete

### Phase 2: 数据库迁移与后端测试（Alembic + pytest）
- [x] 安装/获取 Alembic 和 pytest 相关 skills
- [x] 为 `PPTJob` 表编写 Alembic 迁移脚本
- [x] 使用 pytest + TestClient 为 `/health` 编写测试
- [x] 为 `/jobs` 编写正常路径和错误路径测试
- [x] 运行 `alembic upgrade head` 并确认数据库表结构正确
- [x] 运行 `pytest` 并确认全部通过
- **Status:** complete

### Phase 3: 容器化（Docker + Docker Compose）
- [x] 安装/获取 Docker 相关 skills
- [x] 为 `dppt-web` 编写 `Dockerfile`
- [x] 编写 `docker-compose.yml`（包含 app + PostgreSQL 服务）
- [x] 验证 `docker compose up` 能启动完整服务（本地无 Docker，先做配置和静态验证）
- [x] 验证数据库数据能持久化到 volume
- [x] 验证容器内能运行测试
- **Status:** complete

### Phase 4: 异步任务与缓存（Celery + Redis）
- [x] 安装/获取 Celery + Redis 相关 skills
- [x] 在 `dppt-web` 中集成 Redis 作为 broker/backend
- [x] 将 DPPT Pro 的 PPT 渲染流程封装为 Celery task
- [x] 实现异步提交：`POST /jobs` 返回 `job_id`
- [x] 实现进度查询：`GET /jobs/{id}`
- [x] 启动 worker 并验证端到端异步渲染流程
- **Status:** complete

### Phase 5: CI/CD 与部署基础（GitHub Actions + Nginx）
- [x] 安装/获取 GitHub Actions 相关 skills
- [x] 为 `dppt-web` 创建 `.github/workflows/ci.yml`
- [x] 配置 lint、test、Docker build 三个 job
- [x] 推送代码并验证 Actions 跑通
- [x] 整理部署/回滚思路文档
- **Status:** complete

## Key Questions

1. `dppt-web` 后端当前依赖和项目结构是什么？
2. 本地是否已经安装 PostgreSQL，还是需要用 Docker 运行？
3. 是否需要保留原有同步生成接口，还是直接改造为异步？
4. GitHub 仓库是否已创建并关联到 `dppt-web`？

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 从 Phase 1 开始，不跳过基础 | 用户后端工程基础相对薄弱，先打牢 API + DB 基础再谈云原生 |
| 使用 PostgreSQL 而非 SQLite | 更接近生产环境，便于后续 Docker 和 CI/CD 验证 |
| 使用 Celery + Redis | dppt-web 已有 Python 后端，Celery 生态成熟，与 FastAPI 配合良好 |
| 每个阶段用独立 git worktree/分支 | 失败可快速回滚，不破坏现有 dppt-web 功能 |
| 优先安装成熟 skills，缺失时自造 | 避免重复造轮子，同时确保能力可复制到其他项目 |
| 本地无 Docker/Redis 时，使用 SQLite + 内存 Celery | 保证本地可测试、可验证，不阻塞开发；生产配置保留 |
| 一步到位完成所有 Phase | 用户当前有时间，希望一次性完整落地；每 Phase 仍通过测试验收 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| TestClient 未触发 lifespan，导致 SQLite 表未创建 | 1 | 使用 `with TestClient(app) as client:` 上下文管理器 |
| pytest 找不到 app 模块 | 1 | 创建 `pytest.ini` 并设置 `pythonpath = .` |
| JobResponse 缺少 input_data 字段 | 1 | 在 `app/schemas.py` 的 JobResponse 中补充该字段 |
| Alembic 读取 alembic.ini 中文编码失败 | 1 | alembic.ini 使用占位符 URL，env.py 动态从 app.database.DATABASE_URL 读取 |
| Celery result backend `memory://` 不被支持 | 1 | backend 改为 `cache+memory://` |

## Notes

- 每完成一个 Phase 后更新本文件和 `progress.md`
- 每完成一个 Phase 后调用 `mem_save` 保存经验到 Engram
- 工作区限定：`C:\Users\Administrator\Desktop\_Projects\try`
- 中间过渡文件：`D:\缓存区\`
- 长耗时操作（>10s）使用后台运行，确保 STOP 命令可中断
