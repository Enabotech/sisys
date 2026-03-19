#!/bin/bash
# ArgoCD Image Updater Harbor Secret 创建脚本
# Story 0.7: Task 5 - Harbor 镜像仓库集成
# 修复：MEDIUM-4 - 完善 Harbor Secret 配置
# 创建日期：2026-03-19

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
HARBOR_URL="${HARBOR_URL:-https://harbor.sisys.local}"
HARBOR_PROJECT="${HARBOR_PROJECT:-sisys}"
HARBOR_ROBOT_NAME="${HARBOR_ROBOT_NAME:-argocd-pull}"
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ArgoCD Image Updater Harbor Secret 创建脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 函数：检查 kubectl 是否可用
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}错误：kubectl 未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ kubectl 可用${NC}"
}

# 函数：检查 Harbor 是否可访问
check_harbor() {
    echo -e "${YELLOW}检查 Harbor 连接...${NC}"
    if curl -k -s -o /dev/null -w "%{http_code}" "$HARBOR_URL" | grep -q "200\|401\|403"; then
        echo -e "${GREEN}✓ Harbor 可访问：$HARBOR_URL${NC}"
    else
        echo -e "${RED}✗ Harbor 不可访问：$HARBOR_URL${NC}"
        echo -e "${YELLOW}提示：请检查 Harbor URL 是否正确${NC}"
        exit 1
    fi
}

# 函数：获取 Harbor Admin Token
get_harbor_token() {
    echo ""
    echo -e "${YELLOW}请输入 Harbor Admin Token:${NC}"
    echo -e "${YELLOW}获取方式：登录 Harbor → 用户设置 → 访问令牌 → 新建访问令牌${NC}"
    read -s -p "Token: " HARBOR_ADMIN_TOKEN
    echo ""
    
    if [ -z "$HARBOR_ADMIN_TOKEN" ]; then
        echo -e "${RED}错误：Token 不能为空${NC}"
        exit 1
    fi
}

# 函数：创建 Robot Account（如果不存在）
create_robot_account() {
    echo ""
    echo -e "${YELLOW}检查 Robot Account: robot\$${HARBOR_PROJECT}+${HARBOR_ROBOT_NAME}${NC}"
    
    # 使用 Harbor API 检查 Robot Account
    ROBOT_EXISTS=$(curl -k -s -H "Authorization: Bearer $HARBOR_ADMIN_TOKEN" \
        "$HARBOR_URL/api/v2.0/robots?name=${HARBOR_ROBOT_NAME}" | \
        grep -c "\"name\":\"robot\$${HARBOR_PROJECT}+${HARBOR_ROBOT_NAME}\"" || true)
    
    if [ "$ROBOT_EXISTS" -gt 0 ]; then
        echo -e "${GREEN}✓ Robot Account 已存在${NC}"
    else
        echo -e "${YELLOW}创建 Robot Account...${NC}"
        
        # 创建 Robot Account
        ROBOT_RESPONSE=$(curl -k -s -X POST \
            -H "Authorization: Bearer $HARBOR_ADMIN_TOKEN" \
            -H "Content-Type: application/json" \
            "$HARBOR_URL/api/v2.0/robots" \
            -d "{
                \"name\": \"${HARBOR_ROBOT_NAME}\",
                \"description\": \"ArgoCD Image Updater 拉取镜像\",
                \"project_id\": 0,
                \"level\": \"system\",
                \"permissions\": [
                    {
                        \"kind\": \"project\",
                        \"namespace\": \"${HARBOR_PROJECT}\",
                        \"access\": [
                            {
                                \"resource\": \"repository\",
                                \"action\": \"pull\"
                            }
                        ]
                    }
                ]
            }")
        
        ROBOT_TOKEN=$(echo "$ROBOT_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        
        if [ -n "$ROBOT_TOKEN" ]; then
            echo -e "${GREEN}✓ Robot Account 创建成功${NC}"
            HARBOR_ROBOT_TOKEN="$ROBOT_TOKEN"
        else
            echo -e "${YELLOW}Robot Account 可能已存在，继续使用手动输入的 Token${NC}"
            read -s -p "请输入 Robot Account Token: " HARBOR_ROBOT_TOKEN
            echo ""
        fi
    fi
}

# 函数：获取 Robot Account Token
get_robot_token() {
    if [ -z "${HARBOR_ROBOT_TOKEN:-}" ]; then
        echo ""
        echo -e "${YELLOW}请输入 Robot Account Token:${NC}"
        echo -e "${YELLOW}获取方式：Harbor → 项目 → 机器人账户 → 复制令牌${NC}"
        read -s -p "Token: " HARBOR_ROBOT_TOKEN
        echo ""
        
        if [ -z "$HARBOR_ROBOT_TOKEN" ]; then
            echo -e "${RED}错误：Token 不能为空${NC}"
            exit 1
        fi
    fi
}

# 函数：创建 Kubernetes Secret
create_secret() {
    echo ""
    echo -e "${YELLOW}创建 Kubernetes Secret...${NC}"
    
    # 准备凭据
    HARBOR_CREDENTIALS="robot\$${HARBOR_PROJECT}+${HARBOR_ROBOT_NAME}:${HARBOR_ROBOT_TOKEN}"
    
    # Base64 编码
    HARBOR_CREDENTIALS_B64=$(echo -n "$HARBOR_CREDENTIALS" | base64)
    
    # 创建 Secret YAML
    cat > /tmp/argocd-image-updater-secret.yaml <<EOF
---
# ArgoCD Image Updater Harbor Secret
# 创建日期：$(date -Iseconds)
# Story 0.7: Task 5
apiVersion: v1
kind: Secret
metadata:
  name: argocd-image-updater-secret
  namespace: ${ARGOCD_NAMESPACE}
  labels:
    app.kubernetes.io/name: argocd-image-updater
    app.kubernetes.io/part-of: argocd-image-updater
  annotations:
    description: "Harbor 凭据 - ArgoCD Image Updater 使用"
    created-by: "configure-image-updater-secret.sh"
    created-date: "$(date -Iseconds)"
type: Opaque
data:
  # Harbor 凭据 (base64 编码)
  # 格式：robot$<project>+<robot_name>:<token>
  harbor: ${HARBOR_CREDENTIALS_B64}
EOF
    
    # 应用 Secret
    kubectl apply -f /tmp/argocd-image-updater-secret.yaml
    
    echo -e "${GREEN}✓ Secret 创建成功${NC}"
    
    # 验证 Secret
    echo ""
    echo -e "${YELLOW}验证 Secret...${NC}"
    kubectl get secret argocd-image-updater-secret -n "$ARGOCD_NAMESPACE"
    
    echo -e "${GREEN}✓ Secret 验证成功${NC}"
}

# 函数：重启 Image Updater
restart_image_updater() {
    echo ""
    echo -e "${YELLOW}重启 ArgoCD Image Updater...${NC}"
    
    kubectl rollout restart deployment argocd-image-updater -n "$ARGOCD_NAMESPACE"
    
    echo -e "${GREEN}✓ Image Updater 重启成功${NC}"
    
    # 等待重启完成
    echo -e "${YELLOW}等待 Pod 就绪...${NC}"
    kubectl rollout status deployment argocd-image-updater -n "$ARGOCD_NAMESPACE" --timeout=60s
    
    echo -e "${GREEN}✓ Image Updater 就绪${NC}"
}

# 主函数
main() {
    echo ""
    
    # 检查
    check_kubectl
    check_harbor
    
    # 获取凭据
    get_harbor_token
    create_robot_account
    get_robot_token
    
    # 创建 Secret
    create_secret
    
    # 重启
    restart_image_updater
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}配置完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}下一步:${NC}"
    echo "1. 验证 Image Updater 日志：kubectl logs -n $ARGOCD_NAMESPACE -l app.kubernetes.io/name=argocd-image-updater"
    echo "2. 配置 Application 注解以启用自动更新"
    echo "3. 推送新镜像测试自动更新功能"
    echo ""
}

# 执行主函数
main
