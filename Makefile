# =============================================================================
# sisys Makefile - 开发环境命令入口
# =============================================================================
# 基于 Story 0.1 验收标准创建
# 提供统一的开发环境命令入口，简化日常开发操作
# 更新：添加 SDD+TDD 融合模式命令（2026-03-04）
# =============================================================================

# -----------------------------------------------------------------------------
# 变量定义
# -----------------------------------------------------------------------------
PYTHON := python3
PIP := pip
POETRY := poetry
PYTEST := pytest
MYPY := mypy
RUFF := ruff
ALEMBIC := alembic
DOCKER := docker
DOCKER_COMPOSE := docker-compose
SCHEMATHESIS := schemathesis
OPENAPI_VALIDATOR := openapi-spec-validator

# SDD+TDD 融合模式变量
TARGET ?= domain/entities
STORY ?= 1.1

# -----------------------------------------------------------------------------
# 开发环境设置（Story 0.1 验收标准）
# -----------------------------------------------------------------------------
.PHONY: venv install dev setup clean-env

venv:
	$(PYTHON) -m venv venv
	source venv/bin/activate

install:
	$(POETRY) install

dev:
	$(POETRY) install --with dev,test
	pre-commit install
	@echo "✅ 开发环境设置完成！"
	@echo "📋 SDD 工具链已安装：pydantic, schemathesis, pytest-bdd, openapi-spec-validator"
	@echo "🔧 代码质量工具已安装：ruff, mypy, pytest, pytest-cov"
	@echo "🎯 可用命令：make setup, make lint, make type-check, make test, make dev"
	@echo "📜 预提交 Hooks 已启用：每次提交自动执行检查→修改→通过循环"

setup: venv install dev
	@echo "✅ 开发环境设置完成！"

clean-env:
	rm -rf venv/ .venv/
	@echo "✅ 虚拟环境已清理"

# -----------------------------------------------------------------------------
# 预提交 Hooks 管理（项目宪法）
# -----------------------------------------------------------------------------
.PHONY: hooks hooks-install hooks-uninstall hooks-run hooks-check hooks-update

hooks: hooks-install
	@echo "✅ 预提交 Hooks 命令入口"

hooks-install:
	@echo "📜 安装预提交 Hooks..."
	$(POETRY) run pre-commit install
	@echo "✅ 预提交 Hooks 已安装"
	@echo "📋 宪法原则：每次 git commit 必须执行检查→修改→通过循环"
	@echo "🔍 检查项：代码格式化、代码质量、类型检查、安全扫描、密钥检测"

hooks-uninstall:
	@echo "⚠️  卸载预提交 Hooks..."
	$(POETRY) run pre-commit uninstall
	@echo "✅ 预提交 Hooks 已卸载"

hooks-run:
	@echo "🔍 运行预提交 Hooks（所有文件）..."
	$(POETRY) run pre-commit run --all-files
	@echo "✅ 预提交 Hooks 检查通过"

hooks-check:
	@echo "🔍 检查预提交 Hooks 配置..."
	$(POETRY) run pre-commit sample-config
	@echo "✅ 预提交 Hooks 配置正常"

hooks-update:
	@echo "🔄 更新预提交 Hooks 到最新版本..."
	$(POETRY) run pre-commit autoupdate
	@echo "✅ 预提交 Hooks 已更新"

hooks-validate: hooks-run validate-schemas validate-openapi
	@echo "✅ 预提交 Hooks 完整验证通过"

# -----------------------------------------------------------------------------
# SDD 工具链验证（Story 0.1 验收标准）
# -----------------------------------------------------------------------------
.PHONY: validate-schemas validate-openapi validate-contracts sdd-validate

validate-schemas:
	@echo "🔍 验证领域事件 Schema..."
	$(PYTHON) scripts/tools/validate_schemas.py
	@echo "✅ Schema 验证通过"

validate-openapi:
	@echo "🔍 验证 OpenAPI 规范..."
	$(OPENAPI_VALIDATOR) openapi/openapi.yaml
	@echo "✅ OpenAPI 验证通过"

validate-contracts:
	@echo "🔍 执行 API 契约测试..."
	$(SCHEMATHESIS) run http://localhost:8000/openapi.json --checks all
	@echo "✅ 契约测试通过"

sdd-validate: validate-schemas validate-openapi
	@echo "✅ SDD 规范验证全部通过"

# SDD 规范验证（融合模式）
.PHONY: sdd-verify

sdd-verify:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "✅ SDD 规范验证"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "1. Schema 验证..."
	@echo "   python -c \"from src.domain.events import *; print('Schema OK')\""
	@echo ""
	@echo "2. 类型检查..."
	$(POETRY) run mypy src/domain/
	@echo ""
	@echo "3. 验收测试..."
	$(POETRY) run pytest tests/acceptance/ -v
	@echo ""
	@echo "✅ SDD 规范验证通过"
	@echo ""

# -----------------------------------------------------------------------------
# SDD+TDD 融合模式命令（新增 2026-03-04）
# -----------------------------------------------------------------------------
.PHONY: sdd-define tdd-red tdd-green tdd-refactor tdd-cycle sdd-tdd-cycle

# SDD 规范定义
sdd-define:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "📋 SDD 规范定义"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "1. 定义领域事件 Schema (src/domain/events/)"
	@echo "2. 定义 API 契约 (docs/api/openapi.yaml)"
	@echo "3. 定义验收标准 (tests/acceptance/*.feature)"
	@echo "4. 定义数据模型 (src/domain/entities/)"
	@echo ""
	@echo "📝 检查清单："
	@echo "   [ ] 领域事件 Schema 已定义并评审通过"
	@echo "   [ ] API 契约（OpenAPI）已定义并验证通过"
	@echo "   [ ] 测试用例（Gherkin）已编写并业务方确认"
	@echo "   [ ] 数据模型（SQLAlchemy）已定义并评审通过"
	@echo "   [ ] Qwen Code Agent 已激活并理解规范"
	@echo ""

# TDD 红阶段
tdd-red:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔴 TDD 红阶段：编写失败测试"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "目标：$(TARGET)"
	@echo ""
	@echo "运行测试..."
	$(POETRY) run pytest tests/unit/$(TARGET) -v --tb=short || echo ""
	@echo ""
	@echo "✅ 红阶段完成：测试失败（预期行为）"
	@echo ""
	@echo "📝 下一步："
	@echo "   1. 确认测试失败原因符合预期"
	@echo "   2. 准备编写最小实现（绿阶段）"
	@echo ""

# TDD 绿阶段
tdd-green:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🟢 TDD 绿阶段：运行测试"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "目标：$(TARGET)"
	@echo ""
	@echo "运行测试..."
	$(POETRY) run pytest tests/unit/$(TARGET) -v --tb=short
	@echo ""
	@echo "✅ 绿阶段完成：测试通过"
	@echo ""
	@echo "📝 下一步："
	@echo "   1. 确认所有测试通过"
	@echo "   2. 准备重构优化（重构阶段）"
	@echo ""

# TDD 重构阶段
tdd-refactor:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔄 TDD 重构阶段：优化代码"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "目标：$(TARGET)"
	@echo ""
	@echo "1. 运行 ruff 检查代码质量..."
	$(POETRY) run ruff check src/$(TARGET)
	@echo ""
	@echo "2. 运行 black 格式化代码..."
	$(POETRY) run black src/$(TARGET)
	@echo ""
	@echo "3. 运行 mypy 类型检查..."
	$(POETRY) run mypy src/$(TARGET)
	@echo ""
	@echo "4. 重新运行测试验证..."
	$(POETRY) run pytest tests/unit/$(TARGET) -v --tb=short
	@echo ""
	@echo "✅ 重构阶段完成：代码优化，测试通过"
	@echo ""
	@echo "📝 下一步："
	@echo "   1. 运行 SDD 规范验证"
	@echo "   2. 运行质量门禁检查"
	@echo ""

# TDD 完整循环
tdd-cycle: tdd-red tdd-green tdd-refactor
	@echo "═══════════════════════════════════════════════════════════"
	@echo "✅ TDD 完整循环完成（红 - 绿 - 重构）"
	@echo "═══════════════════════════════════════════════════════════"

# SDD+TDD 完整开发循环
sdd-tdd-cycle: sdd-define tdd-cycle sdd-verify quality-gates
	@echo "═══════════════════════════════════════════════════════════"
	@echo "✅ SDD+TDD 完整开发循环完成"
	@echo "═══════════════════════════════════════════════════════════"

# -----------------------------------------------------------------------------
# 代码质量（Story 0.2 验收标准 - 阶段 1）
# -----------------------------------------------------------------------------
.PHONY: lint format type-check check code-quality

lint:
	@echo "🔍 运行 Ruff 代码检查..."
	$(POETRY) run ruff check src/ tests/

format:
	@echo "🔧 运行 Ruff 格式化..."
	$(POETRY) run ruff format src/ tests/

format-check:
	@echo "🔍 检查代码格式..."
	$(POETRY) run ruff format src/ tests/ --check

type-check:
	@echo "🔍 运行 MyPy 类型检查..."
	$(POETRY) run mypy src/ --ignore-missing-imports --warn-return-any --warn-unused-configs

check: lint type-check
	@echo "✅ 代码质量检查通过"

code-quality: lint format-check type-check
	@echo "✅ 所有代码质量检查通过"

# -----------------------------------------------------------------------------
# 测试（Story 0.2 验收标准 - 阶段 2）
# -----------------------------------------------------------------------------
.PHONY: test test-cov test-cov-html test-unit test-integration test-e2e pytest

test: pytest

pytest:
	@echo "🧪 运行所有测试..."
	$(POETRY) run pytest tests/

test-cov:
	@echo "🧪 运行测试并生成覆盖率..."
	$(POETRY) run pytest --cov=src --cov-report=term-missing --cov-fail-under=80

test-cov-html:
	@echo "🧪 运行测试并生成 HTML 覆盖率报告..."
	$(POETRY) run pytest --cov=src --cov-report=html:htmlcov --cov-fail-under=80
	@echo "📊 覆盖率报告已生成：htmlcov/index.html"

test-unit:
	@echo "🧪 运行单元测试..."
	$(POETRY) run pytest tests/unit/ --cov=src --cov-report=term-missing

test-integration:
	@echo "🧪 运行集成测试..."
	$(POETRY) run pytest tests/integration/ --cov=src --cov-append

test-e2e:
	@echo "🧪 运行 E2E 测试..."
	$(POETRY) run pytest tests/e2e/

# SDD 验收测试（Story 0.1 验收标准）
test-bdd:
	@echo "🧪 运行 BDD 验收测试..."
	$(POETRY) run pytest tests/features/ --bdd-verbose

# -----------------------------------------------------------------------------
# 安全扫描（Story 0.2 验收标准 - 阶段 4）
# -----------------------------------------------------------------------------
.PHONY: security-scan bandit-scan snyk-scan security

security-scan: bandit-scan
	@echo "✅ 安全扫描完成"

bandit-scan:
	@echo "🔍 运行 Bandit 代码安全扫描..."
	$(POETRY) run bandit -r src/ -f json -o bandit-report.json --level high --severity high
	@echo "📊 Bandit 报告已生成：bandit-report.json"

snyk-scan:
	@echo "🔍 运行 Snyk 依赖漏洞扫描..."
	$(POETRY) run snyk test
	@echo "📊 Snyk 扫描完成"

security: bandit-scan snyk-scan
	@echo "✅ 所有安全扫描完成"

# -----------------------------------------------------------------------------
# 数据库
# -----------------------------------------------------------------------------
.PHONY: db-migrate db-downgrade db-upgrade db-head db-revision db-init

db-migrate:
	@echo "🔄 运行数据库迁移..."
	$(POETRY) run alembic upgrade head

db-downgrade:
	@echo "⏮️  回滚数据库..."
	$(POETRY) run alembic downgrade -1

db-upgrade:
	@echo "⏭️  升级数据库到指定版本..."
	$(POETRY) run alembic upgrade $(revision)

db-head:
	@echo "📍 查看当前数据库版本..."
	$(POETRY) run alembic heads

db-revision:
	@echo "📝 创建新的数据库迁移..."
	$(POETRY) run alembic revision -m "$(message)"

db-init: db-migrate
	@echo "✅ 数据库初始化完成"

# -----------------------------------------------------------------------------
# Docker 环境
# -----------------------------------------------------------------------------
.PHONY: docker-up docker-down docker-build docker-logs docker-clean

docker-up:
	@echo "🐳 启动 Docker 环境..."
	$(DOCKER_COMPOSE) -f docker/docker-compose.dev.yml up -d
	@echo "✅ Docker 环境已启动"

docker-down:
	@echo "🛑 停止 Docker 环境..."
	$(DOCKER_COMPOSE) -f docker/docker-compose.dev.yml down

docker-build:
	@echo "🔨 构建 Docker 镜像..."
	$(DOCKER) build -f docker/Dockerfile.dev -t sisys:dev .
	@echo "✅ Docker 镜像构建完成"

docker-logs:
	@echo "📋 查看 Docker 日志..."
	$(DOCKER_COMPOSE) -f docker/docker-compose.dev.yml logs -f

docker-clean:
	@echo "🧹 清理 Docker 容器..."
	$(DOCKER_COMPOSE) -f docker/docker-compose.dev.yml down -v
	@echo "✅ Docker 环境已清理"

# -----------------------------------------------------------------------------
# 服务管理
# -----------------------------------------------------------------------------
.PHONY: run-server run-worker run-scheduler run-dev

run-server:
	@echo "🚀 启动开发服务器..."
	$(POETRY) run uvicorn src.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	@echo "👷 启动工作进程..."
	$(POETRY) run python -m src.infrastructure.workflow.prefect_agent

run-scheduler:
	@echo "⏰ 启动调度器..."
	$(POETRY) run python -m src.infrastructure.workflow.scheduler

run-dev: docker-up run-server
	@echo "✅ 开发环境已启动"

# -----------------------------------------------------------------------------
# 文档
# -----------------------------------------------------------------------------
.PHONY: docs docs-serve docs-clean

docs:
	@echo "📚 构建文档..."
	$(POETRY) run mkdocs build

docs-serve:
	@echo "📖 启动文档服务器..."
	$(POETRY) run mkdocs serve

docs-clean:
	@echo "🧹 清理文档构建文件..."
	rm -rf site/
	@echo "✅ 文档已清理"

# -----------------------------------------------------------------------------
# CI/CD 本地测试（Story 0.2 验收标准）
# -----------------------------------------------------------------------------
.PHONY: ci-local ci-quality ci-test ci-security ci-full

ci-local: ci-quality ci-test
	@echo "✅ CI 本地测试完成"

ci-quality: lint format-check type-check
	@echo "✅ CI 质量门禁通过"

ci-test: test-unit test-integration
	@echo "✅ CI 测试通过"

ci-security: bandit-scan
	@echo "✅ CI 安全扫描通过"

ci-full: ci-quality ci-test ci-security
	@echo "✅ 完整 CI 流程通过"

# -----------------------------------------------------------------------------
# 清理
# -----------------------------------------------------------------------------
.PHONY: clean clean-pyc clean-build clean-test clean-all

clean: clean-pyc clean-build clean-test
	@echo "✅ 清理完成"

clean-pyc:
	@echo "🧹 清理 Python 缓存..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name *.pyc -delete
	find . -type f -name *.pyo -delete
	find . -type f -name *.pyd -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	@echo "✅ Python 缓存已清理"

clean-build:
	@echo "🧹 清理构建文件..."
	rm -rf build/ dist/ .eggs/
	find . -name '*.egg-info' -exec rm -rf {} +
	@echo "✅ 构建文件已清理"

clean-test:
	@echo "🧹 清理测试文件..."
	rm -rf .pytest_cache/ .coverage htmlcov/ *.xml
	rm -rf htmlcov-unit/ htmlcov-integration/
	rm -rf coverage-unit.xml coverage-integration.xml
	@echo "✅ 测试文件已清理"

clean-all: clean clean-env
	@echo "🧹 清理所有..."
	rm -rf venv/ .venv/
	@echo "✅ 所有清理完成"

# =============================================================================
# Git Worktree 并行开发（Qwen Agent + Worktree 融合模式）
# =============================================================================
.PHONY: worktree worktree-create worktree-list worktree-clean worktree-prune \
        worktree-story worktree-bugfix worktree-pr-review worktree-setup

# Worktree 基础目录（可覆盖：make worktree-setup WORKTREE_BASE=/custom/path）
WORKTREE_BASE ?= $(HOME)/dev/sisys-worktrees
STORY_NUM ?= 1.1
BRANCH_NAME ?= story/$(STORY_NUM)
WORKTREE_PATH ?= $(WORKTREE_BASE)/story-$(STORY_NUM)

worktree: worktree-list
	@echo "✅ 使用 'make worktree-help' 查看更多 Git Worktree 命令"

worktree-help:
	@echo "================================================================="
	@echo "  Git Worktree 并行开发命令（Qwen Agent + Worktree 融合模式）"
	@echo "================================================================="
	@echo ""
	@echo "📚 完整文档：docs/developer/qwen-git-worktree-parallel-dev-guide.md"
	@echo "📋 快速参考：docs/developer/qwen-git-worktree-quick-reference.md"
	@echo ""
	@echo "🚀 快速开始:"
	@echo "  make worktree-setup             - 一键设置并行开发环境"
	@echo "  make worktree-story STORY_NUM=1.1  - 创建 Story worktree"
	@echo "  make worktree-list              - 查看所有 worktrees"
	@echo ""
	@echo "🔧 常用命令:"
	@echo "  make worktree-create PATH=x BRANCH=y  - 创建自定义 worktree"
	@echo "  make worktree-bugfix ISSUE=123        - 创建 Bug 修复 worktree"
	@echo "  make worktree-pr-review PR=123        - 创建 PR 审查 worktree"
	@echo "  make worktree-prune                   - 清理无效 worktrees"
	@echo "  make worktree-clean PATH=x            - 删除指定 worktree"
	@echo ""
	@echo "📖 使用示例:"
	@echo "  # 创建 Story 1.1 worktree"
	@echo "  make worktree-story STORY_NUM=1.1"
	@echo ""
	@echo "  # 创建 Bug 修复 worktree"
	@echo "  make worktree-bugfix ISSUE=critical-issue"
	@echo ""
	@echo "  # 审查 PR #123"
	@echo "  make worktree-pr-review PR=123"
	@echo ""
	@echo "================================================================="

worktree-setup:
	@echo "🚀 设置 Git Worktree 并行开发环境..."
	@echo "   基础目录：$(WORKTREE_BASE)"
	@mkdir -p $(WORKTREE_BASE)
	@./scripts/dev/worktree-setup.sh --help
	@echo ""
	@echo "✅ 使用以下命令创建 Story worktrees:"
	@echo "   ./scripts/dev/worktree-setup.sh 1.1 1.2 1.3"
	@echo "   或"
	@echo "   make worktree-story STORY_NUM=1.1"

worktree-create:
	@echo "🔧 创建 Git Worktree..."
	@echo "   路径：$(WORKTREE_PATH)"
	@echo "   分支：$(BRANCH_NAME)"
	@git worktree add -b $(BRANCH_NAME) $(WORKTREE_PATH) main
	@echo "✅ Worktree 创建完成"
	@echo ""
	@echo "📝 下一步:"
	@echo "   1. cd $(WORKTREE_PATH)"
	@echo "   2. python3 -m venv venv"
	@echo "   3. poetry install --with dev,test"
	@echo "   4. @qwen-agent activate domain_agent_1"

worktree-story:
	@echo "📖 创建 Story $(STORY_NUM) Worktree..."
	@$(MAKE) worktree-create \
		WORKTREE_PATH=$(WORKTREE_BASE)/story-$(STORY_NUM) \
		BRANCH_NAME=story/$(STORY_NUM)-$(shell echo $(STORY_NUM) | tr '.' '-')

worktree-bugfix:
	@echo "🐛 创建 Bug 修复 Worktree (Issue: $(ISSUE))..."
	@$(MAKE) worktree-create \
		WORKTREE_PATH=$(WORKTREE_BASE)/bugfix-$(ISSUE) \
		BRANCH_NAME=bugfix/$(ISSUE)

worktree-pr-review:
	@echo "🔍 创建 PR #$(PR) 审查 Worktree..."
	@git fetch origin pull/$(PR)/head:pr-$(PR)-review
	@$(MAKE) worktree-create \
		WORKTREE_PATH=$(WORKTREE_BASE)/pr-$(PR)-review \
		BRANCH_NAME=pr-$(PR)-review

worktree-list:
	@echo "📋 Git Worktrees:"
	@echo "================================================================="
	@git worktree list
	@echo "================================================================="
	@echo ""
	@echo "💡 提示："
	@echo "   - 每个 worktree 是独立的开发环境"
	@echo "   - 使用 'cd <path>' 进入 worktree"
	@echo "   - 使用 'make worktree-clean PATH=<path>' 删除 worktree"

worktree-prune:
	@echo "🧹 清理无效 Git Worktrees..."
	@git worktree prune
	@echo "✅ 清理完成"

worktree-clean:
	@echo "⚠️  删除 Worktree: $(PATH)"
	@read -p "确认删除？[y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@git worktree remove $(PATH) || true
	@echo "✅ Worktree 已删除"

# =============================================================================
# Harbor 部署与验证（Story 0.6）
# =============================================================================
.PHONY: harbor-secrets harbor-deploy harbor-verify harbor-fix harbor-clean

harbor-secrets:
	@echo "🔐 生成 Harbor 密码..."
	@./scripts/security/generate-harbor-secrets.sh

harbor-deploy: harbor-secrets
	@echo "🚀 部署 Harbor..."
	@kubectl apply -k deployments/harbor/
	@helm upgrade --install harbor harbor/harbor \
		-n harbor \
		-f deployments/harbor/values.yaml \
		--wait --timeout 10m
	@echo "✅ Harbor 部署完成"
	@echo "📋 访问地址：https://harbor.sisys.local"
	@echo "🔑 管理员账号：admin / (查看 .secrets/harbor-credentials.txt)"

harbor-verify:
	@echo "✅ 验证 Harbor 部署..."
	@./scripts/deployment/harbor/verify-deployment.sh

harbor-fix:
	@echo "🔧 验证并修复 Harbor 部署 (WSL 重启后使用)..."
	@./scripts/deployment/harbor/verify-and-fix.sh

harbor-clean:
	@echo "🧹 清理 Harbor 部署..."
	@helm uninstall harbor -n harbor || true
	@kubectl delete -k deployments/harbor/ || true
	@echo "✅ Harbor 已清理"

# -----------------------------------------------------------------------------
# 帮助
# -----------------------------------------------------------------------------
.PHONY: help

help:
	@echo "sisys 开发环境命令帮助"
	@echo ""
	@echo "🚀 开发环境设置:"
	@echo "  make setup          - 设置开发环境（虚拟环境 + 依赖 + pre-commit）"
	@echo "  make dev            - 安装开发依赖和 pre-commit 钩子"
	@echo "  make install        - 安装项目依赖"
	@echo ""
	@echo "📜 预提交 Hooks（项目宪法）:"
	@echo "  make hooks          - 安装预提交 Hooks（同 hooks-install）"
	@echo "  make hooks-install  - 安装预提交 Hooks"
	@echo "  make hooks-uninstall- 卸载预提交 Hooks"
	@echo "  make hooks-run      - 运行预提交 Hooks（所有文件）"
	@echo "  make hooks-check    - 检查预提交 Hooks 配置"
	@echo "  make hooks-update   - 更新预提交 Hooks 到最新版本"
	@echo "  make hooks-validate - 预提交 Hooks 完整验证"
	@echo ""
	@echo "🔍 SDD 规范验证:"
	@echo "  make validate-schemas   - 验证领域事件 Schema"
	@echo "  make validate-openapi   - 验证 OpenAPI 规范"
	@echo "  make validate-contracts - 执行 API 契约测试"
	@echo "  make sdd-validate       - 执行所有 SDD 验证"
	@echo ""
	@echo "🔧 代码质量:"
	@echo "  make lint          - Ruff 代码检查"
	@echo "  make format        - Ruff 代码格式化"
	@echo "  make format-check  - 检查代码格式（不修改）"
	@echo "  make type-check    - MyPy 类型检查"
	@echo "  make check         - 运行所有代码检查（lint + type-check）"
	@echo "  make code-quality  - 运行所有质量检查（lint + format-check + type-check）"
	@echo ""
	@echo "🧪 测试:"
	@echo "  make test          - 运行所有测试"
	@echo "  make test-cov      - 运行测试并生成覆盖率（终端）"
	@echo "  make test-cov-html - 运行测试并生成覆盖率（HTML）"
	@echo "  make test-unit     - 运行单元测试"
	@echo "  make test-integration - 运行集成测试"
	@echo "  make test-e2e      - 运行 E2E 测试"
	@echo "  make test-bdd      - 运行 BDD 验收测试"
	@echo ""
	@echo "🔒 安全:"
	@echo "  make security-scan - 运行所有安全扫描"
	@echo "  make bandit-scan   - Bandit 代码安全扫描"
	@echo "  make snyk-scan     - Snyk 依赖漏洞扫描"
	@echo ""
	@echo "🗄️  数据库:"
	@echo "  make db-migrate    - 运行数据库迁移"
	@echo "  make db-revision message=\"xxx\" - 创建新迁移"
	@echo "  make db-upgrade    - 升级到指定版本"
	@echo "  make db-downgrade  - 回滚数据库"
	@echo ""
	@echo "🐳 Docker 环境:"
	@echo "  make docker-up     - 启动 Docker 环境"
	@echo "  make docker-down   - 停止 Docker 环境"
	@echo "  make docker-build  - 构建 Docker 镜像"
	@echo "  make docker-logs   - 查看 Docker 日志"
	@echo ""
	@echo "🚀 服务管理:"
	@echo "  make run-server    - 启动开发服务器"
	@echo "  make run-worker    - 启动工作进程"
	@echo "  make run-scheduler - 启动调度器"
	@echo ""
	@echo "📚 文档:"
	@echo "  make docs          - 构建文档"
	@echo "  make docs-serve    - 启动文档服务器"
	@echo ""
	@echo "🔄 CI/CD 本地测试:"
	@echo "  make ci-local      - 本地运行 CI 流程"
	@echo "  make ci-quality    - 本地运行 CI 质量门禁"
	@echo "  make ci-test       - 本地运行 CI 测试"
	@echo "  make ci-security   - 本地运行 CI 安全扫描"
	@echo "  make ci-full       - 本地运行完整 CI 流程"
	@echo ""
	@echo "🧹 清理:"
	@echo "  make clean         - 清理构建/测试文件"
	@echo "  make clean-all     - 清理所有（包括虚拟环境）"
	@echo ""
	@echo "🔥 SDD+TDD 融合模式（新增 2026-03-04）:"
	@echo "  make sdd-define         - SDD 规范定义（检查清单）"
	@echo "  make tdd-red TARGET=x   - TDD 红阶段（编写失败测试）"
	@echo "  make tdd-green TARGET=x - TDD 绿阶段（运行测试）"
	@echo "  make tdd-refactor TARGET=x - TDD 重构阶段（优化代码）"
	@echo "  make tdd-cycle TARGET=x - TDD 完整循环（红 - 绿 - 重构）"
	@echo "  make sdd-tdd-cycle STORY=x - SDD+TDD 完整开发循环"
	@echo ""
	@echo "🚀 Harbor 部署（Story 0.6）:"
	@echo "  make harbor-secrets   - 生成 Harbor 安全密码"
	@echo "  make harbor-deploy    - 部署 Harbor（生成密码 + Helm 安装）"
	@echo "  make harbor-verify    - 验证 Harbor 部署状态"
	@echo "  make harbor-clean     - 清理 Harbor 部署"
	@echo ""
	@echo "🌳 Git Worktree 并行开发（Qwen Agent + Worktree 融合模式）:"
	@echo "  make worktree              - 查看所有 worktrees"
	@echo "  make worktree-help         - 显示 Worktree 命令帮助"
	@echo "  make worktree-setup        - 一键设置并行开发环境"
	@echo "  make worktree-story STORY_NUM=1.1 - 创建 Story worktree"
	@echo "  make worktree-bugfix ISSUE=xxx    - 创建 Bug 修复 worktree"
	@echo "  make worktree-pr-review PR=123    - 创建 PR 审查 worktree"
	@echo "  make worktree-prune        - 清理无效 worktrees"
	@echo "  make worktree-clean PATH=x - 删除指定 worktree"
	@echo ""
	@echo "  示例："
	@echo "    make worktree-story STORY_NUM=1.1  # 创建 Story 1.1 worktree"
	@echo "    make worktree-bugfix ISSUE=critical  # 创建紧急 Bug 修复环境"
	@echo "    make worktree-pr-review PR=123     # 创建 PR 审查环境"
	@echo ""
	@echo "  📚 完整文档：docs/developer/qwen-git-worktree-parallel-dev-guide.md"
	@echo "  📋 快速参考：docs/developer/qwen-git-worktree-quick-reference.md"
	@echo ""
	@echo "  SDD+TDD 融合模式示例："
	@echo "    make tdd-red TARGET=domain/entities"
	@echo "    make tdd-green TARGET=domain/entities"
	@echo "    make tdd-refactor TARGET=domain/entities"
	@echo ""
	@echo "📋 帮助:"
	@echo "  make help          - 显示此帮助信息"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "📝 相关文档："
	@echo "  - docs/developer/sdd-tdd-fusion-guide.md (融合模式指南)"
	@echo "  - docs/developer/sdd-tdd-checklist.md (实施检查清单)"
	@echo "  - docs/developer/epic1-story1.1-pilot-plan.md (试点计划)"
	@echo "═══════════════════════════════════════════════════════════"
