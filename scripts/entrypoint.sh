#!/bin/bash
# 应用入口脚本
# 功能：初始化应用环境并启动服务

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 环境检查
log_info "环境检查..."
log_info "Python 版本：$(python3 --version)"
log_info "运行用户：$(whoami)"

# GPU 检查
if command -v nvidia-smi &> /dev/null; then
    log_info "GPU 可用:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -n 1
else
    log_warn "GPU 不可用，使用 CPU 模式"
fi

# 环境变量检查
if [ -n "$DATABASE_URL" ]; then
    log_info "数据库连接：已配置"
else
    log_warn "DATABASE_URL 未配置"
fi

if [ -n "$REDIS_URL" ]; then
    log_info "Redis 连接：已配置"
else
    log_warn "REDIS_URL 未配置"
fi

# 执行数据库迁移 (如果有)
if [ -f "scripts/migrate.sh" ]; then
    log_info "执行数据库迁移..."
    bash scripts/migrate.sh || log_warn "数据库迁移失败"
fi

# 启动应用
log_info "启动应用..."
exec "$@"
