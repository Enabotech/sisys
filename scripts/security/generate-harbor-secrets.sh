#!/bin/bash
# Harbor 密码生成脚本
# 用途：生成安全的随机密码并创建 Kubernetes Secret 文件
#
# 安全提示:
# - 生成的密码文件应存储到密码管理器
# - 明文文件应在使用后立即删除
# - 生产环境应使用 sops 加密后存储

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/.secrets"
HARBOR_NS="harbor"

# 密码强度配置
PASSWORD_LENGTH=20
MIN_UPPER=2
MIN_LOWER=2
MIN_DIGIT=2
MIN_SPECIAL=2

# =============================================================================
# 函数定义
# =============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $*${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $*${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $*${NC}"
}

log_error() {
    echo -e "${RED}❌ $*${NC}"
}

# 生成符合复杂度要求的密码
generate_secure_password() {
    local length=$1
    local password=""
    local max_attempts=100
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        # 生成包含所有字符类型的密码
        password=$(openssl rand -base64 $length 2>/dev/null | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c $length)

        # 验证复杂度
        local upper=$(echo "$password" | tr -cd 'A-Z' | wc -c)
        local lower=$(echo "$password" | tr -cd 'a-z' | wc -c)
        local digit=$(echo "$password" | tr -cd '0-9' | wc -c)
        local special=$(echo "$password" | tr -cd '!@#$%^&*' | wc -c)

        if [[ $upper -ge $MIN_UPPER && $lower -ge $MIN_LOWER &&
              $digit -ge $MIN_DIGIT && $special -ge $MIN_SPECIAL ]]; then
            echo "$password"
            return 0
        fi

        attempt=$((attempt + 1))
    done

    log_error "无法在 $max_attempts 次内生成符合复杂度要求的密码"
    return 1
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    local missing_deps=()

    if ! command -v openssl &> /dev/null; then
        missing_deps+=("openssl")
    fi

    if ! command -v kubectl &> /dev/null; then
        log_warning "kubectl 未安装，将跳过集群检查"
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "缺少依赖：${missing_deps[*]}"
        exit 1
    fi

    log_success "依赖检查通过"
}

# 创建输出目录
setup_output_dir() {
    log_info "创建输出目录：$OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"
    chmod 700 "$OUTPUT_DIR"
}

# 生成密码
generate_passwords() {
    log_info "生成 Harbor 安全密码..."
    echo ""

    # 生成密钥
    SECRET_KEY=$(openssl rand -base64 32)
    ADMIN_PASSWORD=$(generate_secure_password $PASSWORD_LENGTH)
    POSTGRES_PASSWORD=$(generate_secure_password $PASSWORD_LENGTH)
    REDIS_PASSWORD=$(generate_secure_password $PASSWORD_LENGTH)
    REGISTRY_SECRET=$(openssl rand -base64 32)

    log_success "密码生成完成"
}

# 创建 Kubernetes Secret YAML
create_secret_yaml() {
    local timestamp=$(date -Iseconds)
    local next_rotation=$(date -d '+90 days' -Iseconds 2>/dev/null || date -v+90d -Iseconds 2>/dev/null || echo "unknown")

    cat > "$OUTPUT_DIR/harbor-secret.yaml" <<EOF
---
# Harbor Kubernetes Secrets
# =============================================================================
# 重要安全提示:
# 1. 此文件包含敏感密码，不应提交到版本控制系统
# 2. 生产环境应使用 sops 加密：sops -e harbor-secret.yaml > secrets.enc.yaml
# 3. 加密后删除明文文件：shred -u harbor-secret.yaml
# 4. 将密码存储到密码管理器 (如 1Password, Bitwarden)
# =============================================================================
# 生成时间：$timestamp
# 下次轮换：$next_rotation
# 生成脚本：scripts/security/generate-harbor-secrets.sh
apiVersion: v1
kind: Secret
metadata:
  name: harbor-secret
  namespace: $HARBOR_NS
  labels:
    app: harbor
    story: "0.6"
  annotations:
    story: "0.6-harbor-image-registry"
    managed-by: "generate-harbor-secrets.sh"
    last-rotation: "$timestamp"
    next-rotation: "$next_rotation"
    description: "Harbor 密钥 - 包含管理员密码、数据库密码、Redis 密码等"
type: Opaque
stringData:
  # Harbor 核心密钥 (用于加密 Harbor 内部敏感信息)
  SECRET_KEY: "$SECRET_KEY"

  # Harbor 管理员密码
  # 要求：12 位 + 大小写 + 数字 + 符号
  # 首次登录后强制修改
  HARBOR_ADMIN_PASSWORD: "$ADMIN_PASSWORD"

  # PostgreSQL 数据库密码
  POSTGRES_PASSWORD: "$POSTGRES_PASSWORD"
  POSTGRES_USERNAME: "postgres"
  POSTGRES_DATABASE: "registry"

  # Redis 密码
  REDIS_PASSWORD: "$REDIS_PASSWORD"

  # Registry 认证密钥
  REGISTRY_CREDENTIAL_SECRET: "$REGISTRY_SECRET"
EOF

    chmod 600 "$OUTPUT_DIR/harbor-secret.yaml"
    log_success "创建 Secret 文件：$OUTPUT_DIR/harbor-secret.yaml"
}

# 创建凭证记录文件
create_credentials_file() {
    local timestamp=$(date)

    cat > "$OUTPUT_DIR/harbor-credentials.txt" <<EOF
# =============================================================================
# Harbor 系统凭证
# =============================================================================
# 生成时间：$timestamp
# 重要：此文件应存储在安全的密码管理器中 (如 1Password, Bitwarden)
# 严禁提交到版本控制系统！
# =============================================================================

# Harbor Web 界面
# ---------------------------------------------------------------------------
URL: https://harbor.sisys.local
用户名：admin
密码：$ADMIN_PASSWORD
首次登录：强制修改密码

# 数据库连接 (PostgreSQL)
# ---------------------------------------------------------------------------
主机：harbor-database.harbor.svc.cluster.local
端口：5432
数据库：registry
用户名：postgres
密码：$POSTGRES_PASSWORD

# Redis 连接
# ---------------------------------------------------------------------------
主机：harbor-redis.harbor.svc.cluster.local
端口：6379
密码：$REDIS_PASSWORD

# Harbor 内部密钥
# ---------------------------------------------------------------------------
SECRET_KEY: $SECRET_KEY
REGISTRY_SECRET: $REGISTRY_SECRET

# =============================================================================
# 密码轮换记录
# =============================================================================
# 轮换日期              | 操作人         | 备注
# ---------------------------------------------------------------------------
# $(date -Iseconds) | auto-generated | 初始密码生成
#
# 下次轮换日期：$(date -d '+90 days' -Iseconds 2>/dev/null || date -v+90d -Iseconds 2>/dev/null || echo "unknown")
# =============================================================================

# 安全提示:
# 1. 定期轮换密码 (建议 90 天)
# 2. 离职人员访问权限立即回收
# 3. 密码泄露时立即轮换
# 4. 使用密码管理器存储，不要明文记录
EOF

    chmod 400 "$OUTPUT_DIR/harbor-credentials.txt"
    log_success "创建凭证文件：$OUTPUT_DIR/harbor-credentials.txt"
}

# 显示生成的密码
display_password() {
    echo ""
    echo "=============================================================================="
    echo -e "${GREEN}🔑 初始管理员密码${NC}"
    echo "=============================================================================="
    echo ""
    echo -e "  用户名：${BLUE}admin${NC}"
    echo -e "  密码：${RED}$ADMIN_PASSWORD${NC}"
    echo ""
    echo "  ⚠️  重要提示:"
    echo "     - 首次登录后强制修改密码"
    echo "     - 将此密码存储到密码管理器"
    echo "     - 不要将此密码提交到版本控制系统"
    echo ""
    echo "=============================================================================="
}

# 显示安全提示
display_security_notice() {
    echo ""
    echo "=============================================================================="
    echo -e "${YELLOW}⚠️  安全提示${NC}"
    echo "=============================================================================="
    echo ""
    echo "📁 生成的文件:"
    echo "   - $OUTPUT_DIR/harbor-secret.yaml (Kubernetes Secret)"
    echo "   - $OUTPUT_DIR/harbor-credentials.txt (管理员凭证)"
    echo ""
    echo "🔐 建议操作:"
    echo "   1. 立即将 harbor-credentials.txt 存储到密码管理器"
    echo "   2. 使用 sops 加密 harbor-secret.yaml:"
    echo "      sops -e $OUTPUT_DIR/harbor-secret.yaml > $PROJECT_ROOT/deploy/kubernetes/harbor/secrets.enc.yaml"
    echo "   3. 删除明文文件:"
    echo "      shred -u $OUTPUT_DIR/harbor-credentials.txt"
    echo ""
    echo "📋 应用 Secret 到集群:"
    echo "   kubectl apply -f $OUTPUT_DIR/harbor-secret.yaml"
    echo ""
    echo "🔄 密码轮换:"
    echo "   下次轮换日期：$(date -d '+90 days' -Iseconds 2>/dev/null || date -v+90d -Iseconds 2>/dev/null || echo "unknown")"
    echo "   运行相同脚本生成新密码"
    echo ""
    echo "=============================================================================="
}

# =============================================================================
# 主流程
# =============================================================================

main() {
    echo "=============================================================================="
    echo -e "${BLUE}🔐 Harbor 密码生成脚本${NC}"
    echo "=============================================================================="
    echo ""

    check_dependencies
    setup_output_dir
    generate_passwords
    create_secret_yaml
    create_credentials_file
    display_password
    display_security_notice

    log_success "密码生成完成！"
}

# 执行主流程
main "$@"
