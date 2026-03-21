#!/bin/bash
# ArgoCD Gitea 集成配置脚本
# 用于配置 Gitea Personal Access Token 和 Webhook

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
GITEA_URL="https://gitea.sisys.local"
GITEA_API="${GITEA_URL}/api/v1"
GITEA_USERNAME="${GITEA_USERNAME:-admin}"
GITEA_PASSWORD="${GITEA_PASSWORD:-admin}"
GITEA_REPO="${GITEA_REPO:-sisys/sisys}"

ARGOCD_NAMESPACE="argocd"
ARGOCD_SERVER="argocd-server"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ArgoCD Gitea 集成配置${NC}"
echo -e "${GREEN}========================================${NC}"

# 函数：检查 kubectl 命令
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}错误：kubectl 未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ kubectl 已安装${NC}"
}

# 函数：检查 ArgoCD 是否运行
check_argocd_running() {
    echo "检查 ArgoCD 运行状态..."
    if ! kubectl get pods -n ${ARGOCD_NAMESPACE} | grep -q "argocd-server"; then
        echo -e "${RED}错误：ArgoCD server 未运行${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ ArgoCD server 运行正常${NC}"
}

# 函数：检查 Gitea 是否可访问
check_gitea_accessible() {
    echo "检查 Gitea 可访问性..."
    if ! curl -k -s -o /dev/null -w "%{http_code}" "${GITEA_URL}" | grep -q "200\|302"; then
        echo -e "${YELLOW}警告：Gitea 可能不可访问，请检查 hosts 配置和 NodePort${NC}"
        echo "尝试通过 NodePort 访问..."
        GITEA_URL="http://localhost:nodeport"
        GITEA_API="${GITEA_URL}/api/v1"
    fi
    echo -e "${GREEN}✓ Gitea 可访问${NC}"
}

# 函数：创建 Gitea Personal Access Token
create_gitea_token() {
    echo ""
    echo -e "${YELLOW}步骤 1: 创建 Gitea Personal Access Token${NC}"

    # 使用 API 创建 Token
    echo "正在创建 Token..."
    TOKEN_RESPONSE=$(curl -k -s -X POST "${GITEA_API}/users/${GITEA_USERNAME}/tokens" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"argocd-webhook-$(date +%Y%m%d%H%M%S)\",
            \"scopes\": [\"repo\", \"admin:repo_hook\"]
        }" \
        -u "${GITEA_USERNAME}:${GITEA_PASSWORD}")

    # 检查是否成功
    if echo "$TOKEN_RESPONSE" | grep -q "sha1"; then
        ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.sha1')
        echo -e "${GREEN}✓ Gitea Personal Access Token 创建成功${NC}"
        echo "Token: ${ACCESS_TOKEN:0:10}...（已隐藏）"

        # 将 Token 存储到 Kubernetes Secret
        echo "存储 Token 到 Kubernetes Secret..."
        kubectl create secret generic argocd-gitea-token \
            -n ${ARGOCD_NAMESPACE} \
            --from-literal=token="${ACCESS_TOKEN}" \
            --dry-run=client -o yaml | kubectl apply -f -

        echo -e "${GREEN}✓ Token 已存储到 Secret: argocd-gitea-token${NC}"
    else
        echo -e "${RED}✗ 创建 Token 失败${NC}"
        echo "响应：${TOKEN_RESPONSE}"
        echo ""
        echo -e "${YELLOW}请手动创建 Token:${NC}"
        echo "1. 登录 Gitea: ${GITEA_URL}"
        echo "2. 进入 设置 -> 应用"
        echo "3. 点击 '生成新 Token'"
        echo "4. 选择权限：repo, admin:repo_hook"
        echo "5. 复制 Token 并运行以下命令："
        echo "   kubectl create secret generic argocd-gitea-token \\"
        echo "       -n ${ARGOCD_NAMESPACE} \\"
        echo "       --from-literal=token='YOUR_TOKEN_HERE'"
        exit 1
    fi
}

# 函数：配置 ArgoCD 仓库凭据
configure_argocd_repo() {
    echo ""
    echo -e "${YELLOW}步骤 2: 配置 ArgoCD 仓库凭据${NC}"

    # 获取 Token
    ACCESS_TOKEN=$(kubectl get secret argocd-gitea-token -n ${ARGOCD_NAMESPACE} -o jsonpath='{.data.token}' | base64 -d)

    if [ -z "$ACCESS_TOKEN" ]; then
        echo -e "${RED}错误：无法获取 Gitea Token${NC}"
        exit 1
    fi

    # 使用 kubectl 配置 ArgoCD 仓库
    echo "配置 ArgoCD 仓库凭据..."
    kubectl apply -f - <<EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: argocd-gitea-creds
  namespace: ${ARGOCD_NAMESPACE}
  labels:
    argocd.argoproj.io/secret-type: repo-creds
type: Opaque
stringData:
  username: ${GITEA_USERNAME}
  password: ${ACCESS_TOKEN}
  url: https://gitea.sisys.local/sisys
EOF

    echo -e "${GREEN}✓ ArgoCD 仓库凭据配置完成${NC}"

    # 添加仓库到 ArgoCD
    echo "添加仓库到 ArgoCD..."
    kubectl exec -n ${ARGOCD_NAMESPACE} deploy/${ARGOCD_SERVER} -- \
        argocd repo add https://gitea.sisys.local/sisys/sisys.git \
        --username ${GITEA_USERNAME} \
        --password ${ACCESS_TOKEN} \
        --insecure-skip-server-verification

    echo -e "${GREEN}✓ Gitea 仓库已添加到 ArgoCD${NC}"
}

# 函数：配置 Gitea Webhook
configure_gitea_webhook() {
    echo ""
    echo -e "${YELLOW}步骤 3: 配置 Gitea Webhook${NC}"

    # 获取 Token
    ACCESS_TOKEN=$(kubectl get secret argocd-gitea-token -n ${ARGOCD_NAMESPACE} -o jsonpath='{.data.token}' | base64 -d)

    # 获取 ArgoCD Webhook URL
    ARGOCD_WEBHOOK_URL="${GITEA_URL}/api/webhook"

    echo "创建 Gitea Webhook..."
    WEBHOOK_RESPONSE=$(curl -k -s -X POST "${GITEA_API}/repos/${GITEA_REPO}/hooks" \
        -H "Content-Type: application/json" \
        -H "Authorization: token ${ACCESS_TOKEN}" \
        -d "{
            \"active\": true,
            \"type\": \"gitea\",
            \"config\": {
                \"url\": \"${ARGOCD_WEBHOOK_URL}\",
                \"content_type\": \"json\",
                \"insecure_ssl\": true
            },
            \"events\": [
                \"push\",
                \"create\",
                \"delete\"
            ]
        }")

    # 检查是否成功
    if echo "$WEBHOOK_RESPONSE" | grep -q "id"; then
        WEBHOOK_ID=$(echo "$WEBHOOK_RESPONSE" | jq -r '.id')
        echo -e "${GREEN}✓ Gitea Webhook 创建成功 (ID: ${WEBHOOK_ID})${NC}"
        echo "Webhook URL: ${ARGOCD_WEBHOOK_URL}"
        echo "触发事件：push, create, delete"
    else
        echo -e "${YELLOW}警告：Webhook 创建可能失败或已存在${NC}"
        echo "响应：${WEBHOOK_RESPONSE}"
        echo ""
        echo -e "${YELLOW}请手动创建 Webhook:${NC}"
        echo "1. 进入 Gitea 仓库：${GITEA_URL}/${GITEA_REPO}"
        echo "2. 进入 设置 -> Webhook"
        echo "3. 点击 '添加 Webhook'"
        echo "4. 选择 'Gitea' 类型"
        echo "5. 配置 URL: ${ARGOCD_WEBHOOK_URL}"
        echo "6. 选择触发事件：Push, Create, Delete"
    fi
}

# 函数：验证配置
verify_configuration() {
    echo ""
    echo -e "${YELLOW}步骤 4: 验证配置${NC}"

    # 验证 ArgoCD 仓库列表
    echo "验证 ArgoCD 仓库连接..."
    kubectl exec -n ${ARGOCD_NAMESPACE} deploy/${ARGOCD_SERVER} -- \
        argocd repo list

    echo ""
    echo -e "${GREEN}✓ 配置验证完成${NC}"
}

# 主函数
main() {
    echo ""
    check_kubectl
    check_argocd_running
    check_gitea_accessible

    create_gitea_token
    configure_argocd_repo
    configure_gitea_webhook
    verify_configuration

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}ArgoCD Gitea 集成配置完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "下一步:"
    echo "1. 创建 ArgoCD Application"
    echo "2. 测试代码推送触发同步"
    echo ""
    echo "访问 ArgoCD: https://argocd.sisys.local"
    echo "访问 Gitea: ${GITEA_URL}"
}

# 执行主函数
main
