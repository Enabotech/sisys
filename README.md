# SISYS - 企业战略规划管理系统

> **🚀 新开发者？5 分钟快速开始：** [阅读 **QUICK_SETUP.md**](docs/delivery/QUICK_SETUP.md)

AI-driven strategic planning and decision intelligence platform for enterprises.

**最新版本：** Epic 0 重构完成 (2026-03-05) ✅

---

## 📋 导航 Navigation

### 快速开始
| 文档 | 用途 | 目标读者 | 阅读时间 |
|------|------|---------|---------|
| [**QUICK_SETUP.md**](docs/delivery/QUICK_SETUP.md) | 5 分钟快速设置 | 新开发者 | 5 分钟 |

### 开发环境
| 文档 | 用途 | 目标读者 | 阅读时间 |
|------|------|---------|---------|
| [**WSL2_QUICK_REFERENCE.md**](docker/WSL2_QUICK_REFERENCE.md) | WSL 2 快速参考卡片 | WSL 2 用户 | 2 分钟 |
| [**Qwen + Git Worktree 并行开发指南**](docs/developer/qwen-git-worktree-parallel-dev-guide.md) | Qwen Code + Worktree 多任务并行开发 | 所有开发者 | 30 分钟 |
| [**Qwen + Worktree 快速参考**](docs/developer/qwen-git-worktree-quick-reference.md) | 快速命令查询卡片 | 所有开发者 | 5 分钟 |

### 架构文档
| 文档 | 用途 | 目标读者 | 阅读时间 |
|------|------|---------|---------|
| [**企业战略规划管理系统架构设计文档**](_bmad-output/planning-artifacts/architecture.md) | 完整架构设计文档 | 架构师/开发者 | 60 分钟 |

**快速选择：**
- 🆕 **第一次设置？** → 阅读 [**QUICK_SETUP.md**](docs/delivery/QUICK_SETUP.md)
- 📖 **了解项目？** → 继续阅读本 README
- 🏗️ **了解架构？** → 阅读 [**企业战略规划管理系统架构设计文档**](_bmad-output/planning-artifacts/architecture.md)
- 🚀 **并行开发？** → 阅读 [**Qwen + Git Worktree 并行开发指南**](docs/developer/qwen-git-worktree-parallel-dev-guide.md)

---

## 📁 项目结构 Project Structure

**完整目录结构：** 详见 [architecture.md](architecture.md#13-目录结构) 第 13 章（权威来源）

**快速概览（六边形架构）：**
```
sisys/
├── src/                          # 六边形架构核心
│   ├── domain/                   # 领域层（零外部依赖 - FR-AR-01）
│   ├── application/              # 应用层（用例编排）
│   ├── infrastructure/           # 基础设施层（五层存储/消息总线）
│   └── interfaces/               # 接口层（CLI/REST API）
├── tests/                        # 测试（unit/integration/e2e）
├── scripts/                      # 脚本（database/deployment/testing/monitoring）
├── docker/                       # Docker 配置（dev/prod/test）
├── .github/workflows/            # GitHub Actions（CI/CD）
├── configs/                      # 应用配置（base/development/production/testing）
└── docs/                         # 文档（architecture/api/user_guides/developer）
```

**关键架构约束：**
- ✅ 领域层不依赖任何外部框架（FR-AR-01）
- ✅ 基础设施层实现领域层接口
- ✅ 五层存储：Redis → PostgreSQL → Qdrant → MinIO → Neo4j
- ✅ 事件驱动：RabbitMQ + Redis 双通道总线

---

## 📞 联系与支持 Supports

For issues or questions, please contact the development team.

---

## 📝 修订历史 Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-02-28 | Initial release | Development Team |

---

**Status**: ✅ Development Environment Ready
**Version**: 0.1.0
**Last Updated**: 2026-03-02
