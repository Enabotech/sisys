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
**When** 运行 `docker compose up -d` 和 `poetry install`
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
- 快速设置指南：`QUICK_SETUP.md`（2026-03-02 新增）
- **安全提示：** 开发环境可使用默认密码，生产环境必须修改！

## Known Issues & Solutions

### Issue 1: Qdrant 健康检查显示问题

**现象：** `docker compose ps` 显示 Qdrant 为 "Up" 而非 "Up (healthy)"

**原因：** Qdrant Alpine 镜像缺少 curl/wget，健康检查已禁用

**解决方案：** 通过 API 验证 Qdrant 运行状态
```bash
curl http://localhost:6333/
# 预期返回：{"title":"qdrant - vector search engine"}
```

### Issue 2: Docker Compose 命令版本

**现象：** 文档中使用 `docker compose`（无连字符），旧教程使用 `docker-compose`（有连字符）

**说明：**
- `docker compose` = v2 插件版本（推荐，现代标准）
- `docker-compose` = v1 独立版本（已过时）
- Docker Desktop 和 Docker Engine 都支持 `docker compose`

### Issue 3: Python 版本不兼容（WSL 2 Ubuntu 22.04）

**问题：** Ubuntu 22.04 默认 Python 3.10，项目要求 3.11+

**解决方案：**
```bash
# 安装 Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### Issue 4: 脚本目录结构（architecture.md 规范）

**说明：** 根据 architecture.md 第 13.9 节定义，scripts 目录结构如下：

```
scripts/
├── database/              # 数据库脚本
│   └── init-db.sql        # 数据库初始化脚本
├── deployment/            # 部署脚本
├── monitoring/            # 监控脚本
│   └── health_check.py    # 健康检查脚本
└── tools/                 # 工具脚本
```

**注意：** 所有脚本路径应使用完整子目录路径（如 `scripts/database/init-db.sql`）

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

## 📝 文档修订历史

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|---------|--------|
| 1.0.0 | 2026-02-28 | 初始版本 | 开发团队 |
| 1.1.0 | 2026-03-01 | Story 完成，添加 Implementation Tasks | 开发团队 |
| 1.2.0 | 2026-03-02 | 一致性修订：docker compose 命令、路径修正、Known Issues、安全提示 | AI 架构师 |
| 1.3.0 | 2026-03-02 | 脚本目录结构对齐 architecture.md 第 13.9 节 | AI 架构师 |
| 1.4.0 | 2026-03-02 | docker 目录结构对齐 architecture.md 第 13.11 节 | AI 架构师 |
