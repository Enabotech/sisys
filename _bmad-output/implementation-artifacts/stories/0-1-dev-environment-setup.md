---
story_id: 0-1-dev-environment-setup
epic: epic-0
title: 开发环境搭建
status: done
created: 2026-02-28
completed: 2026-03-01
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

- [x] 创建 `docker/docker-compose.yml` 文件，配置以下服务： ✅
  - PostgreSQL 15+
  - Redis 7.0+
  - Qdrant 1.7+
  - MinIO
  - Neo4j 5.x
- [x] 创建 `pyproject.toml` 文件，配置 Poetry 依赖 ✅
- [x] 创建 `.vscode/settings.json` 和 `.idea/` 配置 ✅
- [x] 创建 `.env.example` 环境变量模板 ✅
- [x] 编写开发环境搭建文档（README.md） ✅
- [x] 创建健康检查脚本 `scripts/monitoring/health_check.py` ✅
- [x] 创建数据库初始化脚本 `scripts/database/init-db.sql` ✅
- [x] 创建 src 目录结构（六边形架构） ✅
- [x] 创建测试目录结构和验收测试 `tests/e2e/test_story_01.py` ✅
- [x] 创建 WSL 2 自动化安装脚本 `docker/setup-wsl2.ps1` 和 `docker/setup-wsl2-docker.sh` ✅
- [x] 创建 WSL 2 快速参考文档 `docker/WSL2_QUICK_REFERENCE.md` ✅

## Technical Notes

- Python 版本：3.11+
- 使用 Poetry 进行依赖管理
- **Docker 环境方案（两种可选）：**
  - **方案 1**: Docker Desktop on Windows 11（推荐简单性）
  - **方案 2**: WSL 2 + Ubuntu 22.04 + Docker Engine（推荐开发性能）
- IDE 配置包括代码规范、调试配置、Git 集成
- 详细 WSL 2 设置指南：`docker/WSL2_SETUP.md`

## Definition of Done

- [ ] 所有 Acceptance Criteria 通过
- [ ] Docker Compose 所有服务正常启动
- [ ] Poetry install 成功执行
- [ ] IDE 配置测试通过
- [ ] 文档完整

## Documentation

**设置文档：**
- [QUICK_SETUP.md](../../../QUICK_SETUP.md) - 5 分钟快速设置（推荐新开发者）
- [README.md](../../../README.md) - 项目综合说明
- [docker/WSL2_SETUP.md](../../../docker/WSL2_SETUP.md) - WSL 2 详细设置指南
- [docker/WSL2_QUICK_REFERENCE.md](../../../docker/WSL2_QUICK_REFERENCE.md) - WSL 2 快速参考卡片

**架构文档：**
- [_bmad-output/planning-artifacts/architecture.md](../../../_bmad-output/planning-artifacts/architecture.md) - 完整架构设计

## References

- Epic 0: Iteration 0
- Related: Story 0.2 (CI/CD 流水线), Story 0.3 (测试框架搭建)
