# 后端与系统架构技能拓展设计

**日期**：2026-07-04
**作者**：Claude Code + 用户
**状态**：已批准，待实施

## 1. 目标

在现有 Python 项目（`dppt-web`、`market-daily-report` 等）基础上，通过安装/创建新的 Claude Code skills，系统性地建立起后端工程能力：

- API 设计与数据建模
- 数据库迁移与测试
- 容器化
- 异步任务与缓存
- CI/CD 与部署基础

最终让 `dppt-web` 从“本地可跑”升级为“工程化、可部署、可维护”的后端服务。

## 2. 背景

用户当前技能栈已覆盖：
- 前端/UI/UX 设计
- 办公自动化
- 投资/金融分析
- 工程测试与 TDD
- PPT/视频/PCB 设计

但**后端与系统架构**是明显缺口。`dppt-web` 后端目前是 Python 实现，但缺乏：
- 结构化的 API 设计
- 持久化数据层
- 自动化测试
- 容器化部署能力
- 异步任务处理能力

本设计通过分阶段、可验证的方式补齐这一能力面。

## 3. 设计原则

1. **每个阶段独立可交付**——完成一个阶段后必须验证通过，再进入下一阶段。
2. **与真实项目结合**——不练空 Demo，所有实践落到 `dppt-web` 或相关项目。
3. **Skill 驱动**——优先复用/安装成熟 skills，缺失时再用 `superpowers-writing-skills` 自造。
4. **隔离试错**——每个阶段使用 git worktree 或独立分支，失败可快速回滚。
5. **慢慢推进**——用户有时间，不压缩步骤，每阶段结束后复盘并保存 Engram 记忆。

## 4. 五阶段路线图

### Phase 1：API 与数据建模基础
**时长**：1–2 个会话

**要掌握的技能**：
- FastAPI 现代 API 开发
- Pydantic 数据建模与验证
- SQLAlchemy ORM + PostgreSQL 基础

**实践任务**：
在 `dppt-web` 后端新增 `/health` 和 `/jobs` 接口：
- `/health`：返回服务状态和数据库连接状态
- `/jobs`：支持创建/查询 PPT 渲染任务
- 使用 Pydantic 定义请求/响应模型
- 使用 SQLAlchemy 定义 `PPTJob` 表

**验证标准**：
- `uvicorn` 能启动新 API
- `/docs` Swagger 页面可访问
- PostgreSQL 中能看到 `ppt_jobs` 表

---

### Phase 2：数据库迁移与后端测试
**时长**：1–2 个会话

**要掌握的技能**：
- Alembic 数据库迁移
- pytest + TestClient 做 API 测试
- 与现有 `eng-testing-anti-patterns`、`tdd` skill 结合

**实践任务**：
- 为 `PPTJob` 表编写 Alembic 迁移脚本
- 为 `/health` 和 `/jobs` 接口编写 3–5 个测试用例
- 覆盖正常路径和错误路径

**验证标准**：
- `alembic upgrade head` 成功
- `pytest` 全部通过

---

### Phase 3：容器化
**时长**：1 个会话

**要掌握的技能**：
- Docker 镜像构建
- Docker Compose 多服务编排（app + db）

**实践任务**：
为 `dppt-web` 编写：
- `Dockerfile`
- `docker-compose.yml`
实现 `docker compose up` 一键启动应用和数据库。

**验证标准**：
- `docker compose up` 后 API 可访问
- 数据库数据能持久化到 volume
- 容器内能运行测试

---

### Phase 4：异步任务与缓存
**时长**：2–3 个会话

**要掌握的技能**：
- Celery / RQ 异步任务队列
- Redis 缓存与会话
- 任务状态查询与回调

**实践任务**：
把 DPPT Pro 的 PPT 渲染流程改造为异步任务：
- 用户提交 outline → 返回 job_id
- Worker 后台渲染
- 用户通过 `/jobs/{id}` 查询进度和下载结果

**验证标准**：
- 提交任务后立即返回 job_id
- Worker 能完成渲染并更新数据库状态
- 用户可查询任务进度

---

### Phase 5：CI/CD 与部署基础
**时长**：1–2 个会话

**要掌握的技能**：
- GitHub Actions 工作流
- Nginx / Traefik 反向代理基础
- secrets 与配置管理

**实践任务**：
为 `dppt-web` 建立 GitHub Actions：
- push 时自动跑 lint + test
- 构建 Docker 镜像
- （可选）推送到镜像仓库

**验证标准**：
- push 后 Actions 跑通
- 镜像构建成功
- 有基本的部署/回滚思路文档

## 5. 与现有技能的协同

| 新领域 | 现有技能如何配合 |
|--------|----------------|
| FastAPI / Pydantic | 配合 `eng-holistic-systems` 做接口设计前的系统建模 |
| 后端测试 | 配合 `eng-testing-anti-patterns`、`tdd` 避免测试反模式 |
| Docker / CI/CD | 配合 `superpowers-using-git-worktrees` 隔离每个阶段的改动 |
| 异步任务 | 配合 `eng-observability` 做任务监控与日志 |
| 整体设计 | 用 `superpowers-brainstorming` 规划每个阶段，`planning-with-files` 跟踪进度 |

## 6. 风险与回滚策略

| 风险 | 应对策略 |
|------|---------|
| 新技能与现有项目冲突 | 每个阶段在独立 git worktree/分支进行 |
| 数据库迁移失败 | 先备份，使用 `alembic downgrade` 回滚 |
| Docker 占用资源过多 | 限制容器资源，使用 `docker compose down` 清理 |
| 异步任务调试困难 | 先写同步版本，再逐步异步化 |
| CI/CD 配置错误 | 先在本地验证脚本，再推送到 GitHub |

## 7. 成功标准

- [ ] Phase 1：`dppt-web` 有使用 Pydantic + SQLAlchemy 的新 API
- [ ] Phase 2：Alembic 迁移可运行，pytest 全部通过
- [ ] Phase 3：`docker compose up` 能启动 dppt-web
- [ ] Phase 4：PPT 生成可走异步队列
- [ ] Phase 5：GitHub Actions 自动跑测试/构建

## 8. 下一步

调用 `writing-plans` skill，将本设计拆分为具体的实施计划，明确每个 Phase 的任务、文件、命令和验收标准。
