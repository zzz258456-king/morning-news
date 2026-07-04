# Findings & Decisions

## Requirements

- 用户希望“拓宽技能面”，重点在后端与系统架构，而非升级现有技能
- 用户选择方案 A：后端与系统架构方向
- 用户要求完整、逐步实施，不急于求成
- 用户已批准五阶段设计：API + DB → 测试 + 迁移 → Docker → 异步任务 → CI/CD
- 所有实践必须落到真实项目（优先 `dppt-web`）

## Research Findings

- 当前 `dppt-web` 后端使用 FastAPI（从旧 task_plan.md 得知）
- 当前技能栈中缺少：后端 API 设计、数据库、Docker、异步任务、CI/CD 类 skills
- 已有相关技能可协同：`eng-testing-anti-patterns`、`tdd`、`eng-observability`、`superpowers-using-git-worktrees`、`planning-with-files`
- GitHub 上可安装的后端 skills：
  - `iktakahiro/python-fastapi-ddd-skill`：Python + FastAPI + DDD 实用模板，含 Pydantic schemas、pytest 模式
  - `pydantic/skills`：官方 Pydantic skills，含 logfire-instrumentation、logfire-query
  - `alirezarezvani/claude-skills`：330+ skills 大合集，可能含后端技能
  - `Fuenfgeld/pydantic-ai-skills`：Pydantic AI 相关（依赖注入、工具调用、结构化输出）
- 技能市场（MCP Market / Awesome Skills）还有大量 FastAPI/SQLAlchemy 专项 skill，但多为付费/市场托管

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 使用隔离计划目录 `.planning/2026-07-04-backend-skills-expansion/` | 保留旧的 DPPT Web 计划，避免覆盖 |
| 优先安装官方/社区成熟 skills | 减少自定义维护成本 |
| 使用 PostgreSQL 作为持久化数据库 | 生产级选择，便于后续容器化 |
| 使用 SQLAlchemy 2.0 + Pydantic v2 | 当前 Python 后端主流组合 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| 本地未安装 PostgreSQL，且未安装 Docker | Phase 1 先用 SQLite 跑通 SQLAlchemy 模型与 API；代码按 PostgreSQL 兼容方式编写，后续切换到 PostgreSQL 只需改数据库 URL |

## Resources

- 设计文档：`C:\Users\Administrator\Desktop\_Projects\try\docs\superpowers\specs\2026-07-04-backend-skills-expansion-design.md`
- dppt-web 项目：`C:\Users\Administrator\Desktop\_Projects\try\dppt-web\`
- 工作区：`C:\Users\Administrator\Desktop\_Projects\try`
- 缓存区：`D:\缓存区\`
- 已安装 skills：`python-fastapi-ddd-skill`、`python-fastapi-ddd-presentation-skill`、`python-fastapi-ddd-testing-skill`、`python-fastapi-ddd-tooling-skill`

## Visual/Browser Findings

- 无
