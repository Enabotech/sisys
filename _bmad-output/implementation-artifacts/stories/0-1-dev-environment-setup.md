---
story_id: 0-1-dev-environment-setup
epic: epic-0
title: 开发环境搭建
status: done
created: 2026-02-28
completed: 2026-02-28
---

# Story 0.1: 开发环境搭建

## User Story

As a **开发工程师**,
I want **统一的开发环境和工具链（Python 3.11+, Poetry, Docker, IDE 配置）**,
So that **团队可以高效协作开发**。

## Acceptance Criteria

**Given** 新项目启动
**When** 运行 `docker-compose up` 和 `poetry install`
**Then** 所有开发依赖安装完成，开发环境可正常运行
**And** IDE 配置（.vscode/.idea）提供代码规范、调试配置

## Implementation Tasks

- [ ] 创建 `docker-compose.yml` 文件，配置以下服务：
  - PostgreSQL 15+
  - Redis 7.0+
  - Qdrant 1.7+
  - MinIO
  - Neo4j 5.x
- [ ] 创建 `pyproject.toml` 文件，配置 Poetry 依赖
- [ ] 创建 `.vscode/settings.json` 和 `.idea/` 配置
- [ ] 创建 `.env.example` 环境变量模板
- [ ] 编写开发环境搭建文档（README.md）
- [ ] 测试所有服务正常启动

## Technical Notes

- Python 版本：3.11+
- 使用 Poetry 进行依赖管理
- Docker 容器化开发环境
- IDE 配置包括代码规范、调试配置、Git 集成

## Definition of Done

- [ ] 所有 Acceptance Criteria 通过
- [ ] Docker Compose 所有服务正常启动
- [ ] Poetry install 成功执行
- [ ] IDE 配置测试通过
- [ ] 文档完整

## References

- Epic 0: Iteration 0
- Related: Story 0.2 (CI/CD 流水线), Story 0.3 (测试框架搭建)
