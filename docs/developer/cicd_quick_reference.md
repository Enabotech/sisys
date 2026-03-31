# CI/CD 流水线快速参考卡片

**版本：** 1.0.0
**最后更新：** 2026-03-02
**Story 0.2 实现**

---

## 🚀 快速开始

### 1. 本地测试

```bash
# 运行所有测试
./scripts/testing/run_tests.sh --all

# 仅运行单元测试
./scripts/testing/run_tests.sh --unit

# 生成覆盖率报告
./scripts/testing/run_coverage.sh --open
```

### 2. 安装 Pre-commit

```bash
# 安装 pre-commit
poetry install --with dev

# 安装 git 钩子
pre-commit install

# 手动运行 pre-commit
pre-commit run --all-files
```

详细使用指南请参考 [预提交 Hooks 规范](./pre-commit-hooks.md)。

### 3. 触发 CI/CD

```bash
# 提交代码（自动触发 CI）
git add .
git commit -m "feat: add new feature"
git push origin feature-branch

# 触发 CD（部署到生产）
git commit -m "release: v1.0.0 [deploy-prod]"
git push origin main
```

---

## 📁 文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| CI 工作流 | `.github/workflows/ci.yml` | 持续集成（PR/推送触发） |
| CD 工作流 | `.github/workflows/cd.yml` | 持续部署（main 分支触发） |
| 生产 Dockerfile | `docker/dockerfile.prod` | 多阶段构建生产镜像 |
| 生产 Compose | `docker/docker-compose.prod.yml` | 生产环境编排 |
| 测试 Compose | `docker/docker-compose.test.yml` | 测试环境编排 |
| 测试脚本 | `scripts/testing/run_tests.sh` | 运行测试 |
| 覆盖率脚本 | `scripts/testing/run_coverage.sh` | 生成覆盖率报告 |
| 清理脚本 | `scripts/testing/clean_test_data.py` | 清理测试数据 |
| Pre-commit | `.pre-commit-config.yaml` | 代码质量钩子 |

---

## 🔧 环境变量

### 开发环境 (.env)

```bash
# PostgreSQL
POSTGRES_USER=sisys_dev
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=sisys
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Qdrant
QDRANT_PORT=6333

# MinIO
MINIO_ROOT_USER=sisys_minio_admin
MINIO_ROOT_PASSWORD=minio_password
MINIO_PORT=9000

# Neo4j
NEO4J_AUTH=neo4j/neo4j_password
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687

# Application
APP_PORT=8000
```

### GitHub Secrets

在 GitHub 仓库设置中添加：

```
CODECOV_TOKEN=your_codecov_token
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=...
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=secure_password
```

---

## 📊 CI 流水线 Job

| Job | 名称 | 超时 | 说明 |
|-----|------|------|------|
| 1 | Code Quality | 10 分钟 | Ruff, MyPy, 领域层检查 |
| 2 | Unit Tests | 15 分钟 | 单元测试 + 覆盖率 |
| 3 | Integration Tests | 30 分钟 | 集成测试（Docker 容器） |
| 4 | Security Scan | 10 分钟 | Bandit, Safety, Trivy |
| 5 | Build Docker | 20 分钟 | 多阶段构建，推送 GHCR |
| 6 | Upload Coverage | 10 分钟 | 上传 Codecov |

---

## 📦 CD 流水线 Job

| Job | 名称 | 超时 | 环境 | 说明 |
|-----|------|------|------|------|
| 1 | Build Production | 20 分钟 | - | 生产镜像构建 |
| 2 | Deploy Test | 15 分钟 | Test | 部署到测试环境 |
| 3 | Notify | 5 分钟 | - | 发送通知（Slack/钉钉） |
| 4 | Deploy Production | 20 分钟 | Production | 生产部署（需审批） |

---

## ✅ 健康检查

### 本地服务健康

```bash
# 检查所有服务
docker compose ps

# 查看应用日志
docker compose logs app

# 测试健康端点
curl http://localhost:8000/health

# 测试 PostgreSQL
docker exec sisys-postgres pg_isready -U sisys_dev

# 测试 Redis
docker exec sisys-redis redis-cli ping

# 测试 MinIO
curl http://localhost:9000/minio/health/live
```

### 测试环境健康

```bash
# 查看测试环境状态
docker compose -f docker-compose.test.yml ps

# 查看测试环境日志
docker compose -f docker-compose.test.yml logs app
```

### 生产环境健康

```bash
# 查看生产环境状态
docker compose -f docker-compose.prod.yml ps

# 查看生产环境日志
docker compose -f docker-compose.prod.yml logs app
```

---

## 🐛 故障排查

### CI 失败

```bash
# 本地重现 CI
./scripts/testing/run_tests.sh --all --coverage

# 查看 pre-commit 问题
pre-commit run --all-files --verbose

# 检查领域层依赖
python -c "
import ast
# ... (见 ci.yml 中的检查脚本)
"
```

### CD 失败

```bash
# 查看部署日志
docker compose -f docker-compose.test.yml logs app

# 检查 Docker 镜像
docker images | grep sisys

# 重新部署
docker compose -f docker-compose.test.yml down
docker compose -f docker-compose.test.yml up -d
```

### 覆盖率低于门槛

```bash
# 查看哪些文件覆盖率低
./scripts/testing/run_coverage.sh --open

# 在浏览器中查看 htmlcov/index.html
# 红色 = 覆盖率低
# 绿色 = 覆盖率高
```

---

## 🔒 安全最佳实践

### 1. Secrets 管理

```bash
# ✅ 好：使用 GitHub Secrets
echo "${{ secrets.GITHUB_TOKEN }}"

# ❌ 坏：硬编码 secrets
echo "my_secret_password"
```

### 2. 最小权限原则

```yaml
# ✅ 好：最小权限
permissions:
  contents: read
  packages: write

# ❌ 坏：过度权限
permissions: write-all
```

### 3. 镜像扫描

```bash
# 本地扫描镜像
trivy image ghcr.io/sisys/sisys:latest

# 查看 SBOM
cat sbom.spdx.json
```

---

## 📈 监控指标

### GitHub Actions

访问：`https://github.com/your-org/sisys/actions`

- 构建成功率
- 平均构建时间
- 失败趋势分析

### Codecov

访问：`https://app.codecov.io/gh/your-org/sisys`

- 代码覆盖率趋势
- 文件覆盖率详情
- PR 覆盖率变化

### 应用监控

```bash
# Prometheus 指标
curl http://localhost:9090/metrics

# Grafana 仪表盘
open http://localhost:3000
```

---

## 🎯 下一步

### Story 0.3: 测试框架搭建

- [ ] 创建 pytest 配置
- [ ] 实现测试 fixture
- [ ] 创建测试模板
- [ ] 配置覆盖率门禁

### 后续改进

- [ ] 添加性能测试（locust）
- [ ] 添加负载测试（k6）
- [ ] 添加契约测试（Pact）
- [ ] 添加混沌工程（可选）

---

## 📚 参考文档

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Pytest 文档](https://docs.pytest.org/)
- [Pre-commit 文档](https://pre-commit.com/)
- [Codecov 文档](https://docs.codecov.com/)

---

**🎉 CI/CD 流水线已就绪！**

**开始开发 → 提交代码 → 自动测试 → 自动部署**
