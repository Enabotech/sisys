#!/bin/bash
# ============================================================
# Gitea Runner 监控脚本
# ============================================================
# Story: 0.8 - Gitea Runner Configuration
# Task: 8 - Monitoring and Logging Configuration
#
# 用途：监控 Runner 状态、日志和 Pipeline 执行
#
# 使用方法:
#   bash scripts/deployment/gitea-runner/monitor-runner.sh [command]
#
# 可用命令:
#   status    - 查看 Runner 状态
#   logs      - 查看 Runner 日志
#   metrics   - 查看监控指标
#   alert     - 配置告警
#   dashboard - 生成监控仪表板数据
#
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
NAMESPACE="gitea-actions"
STATEFULSET="gitea-org-runner"
LABEL="app=gitea-org-runner"

# 帮助信息
show_help() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Gitea Runner 监控脚本                                 ║${NC}"
    echo -e "${BLUE}║   Story 0-8 - Task 8                                    ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "用法：$0 [command]"
    echo ""
    echo "可用命令:"
    echo "  status    - 查看 Runner 状态"
    echo "  logs      - 查看 Runner 日志"
    echo "  metrics   - 查看监控指标"
    echo "  alert     - 配置告警（可选）"
    echo "  dashboard - 生成监控仪表板数据"
    echo "  help      - 显示帮助信息"
    echo ""
}

# 查看 Runner 状态
show_status() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Gitea Runner 状态                                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Pod 状态
    echo -e "${YELLOW}📊 Pod 状态:${NC}"
    kubectl get pods -n "$NAMESPACE" -l "$LABEL" -o wide
    echo ""

    # StatefulSet 状态
    echo -e "${YELLOW}📊 StatefulSet 状态:${NC}"
    kubectl get statefulset -n "$NAMESPACE" "$STATEFULSET" -o wide
    echo ""

    # 副本信息
    echo -e "${YELLOW}📊 副本信息:${NC}"
    REPLICAS=$(kubectl get statefulset -n "$NAMESPACE" "$STATEFULSET" -o jsonpath='{.status.replicas}')
    READY_REPLICAS=$(kubectl get statefulset -n "$NAMESPACE" "$STATEFULSET" -o jsonpath='{.status.readyReplicas}')
    echo "   期望副本数：$REPLICAS"
    echo "   就绪副本数：$READY_REPLICAS"

    if [ "$REPLICAS" -eq "$READY_REPLICAS" ]; then
        echo -e "   ${GREEN}✅ 所有 Runner 就绪${NC}"
    else
        echo -e "   ${RED}❌ Runner 未完全就绪${NC}"
    fi
    echo ""
}

# 查看 Runner 日志
show_logs() {
    POD_NAME="${1:-gitea-org-runner-0}"
    TAIL_LINES="${2:-50}"

    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Gitea Runner 日志 ($POD_NAME)                          ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail="$TAIL_LINES"
}

# 实时跟踪日志
follow_logs() {
    POD_NAME="${1:-gitea-org-runner-0}"

    echo -e "${BLUE}实时跟踪日志... (Ctrl+C 退出)${NC}"
    kubectl logs -n "$NAMESPACE" "$POD_NAME" -f --tail=20
}

# 查看监控指标
show_metrics() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Gitea Runner 监控指标                                 ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # CPU 使用率
    echo -e "${YELLOW}📊 CPU 使用率:${NC}"
    kubectl top pods -n "$NAMESPACE" -l "$LABEL" 2>/dev/null || echo "   ⚠️  metrics-server 未安装"
    echo ""

    # 内存使用率
    echo -e "${YELLOW}📊 内存使用率:${NC}"
    kubectl top pods -n "$NAMESPACE" -l "$LABEL" 2>/dev/null || echo "   ⚠️  metrics-server 未安装"
    echo ""

    # Prometheus 检查
    echo -e "${YELLOW}📊 Prometheus 监控:${NC}"
    PROMETHEUS_PODS=$(kubectl get pods -A -l app.kubernetes.io/name=prometheus 2>/dev/null | grep -c Running || echo "0")
    if [ "$PROMETHEUS_PODS" -gt 0 ]; then
        echo "   ✅ Prometheus 已部署 ($PROMETHEUS_PODS 个 Pod)"
    else
        echo "   ⚠️  Prometheus 未部署 (可选)"
    fi
    echo ""
}

# 配置告警
configure_alerts() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Gitea Runner 告警配置                                 ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo "告警配置需要以下组件（可选）:"
    echo "  1. Prometheus - 监控指标收集"
    echo "  2. Alertmanager - 告警管理"
    echo "  3. 通知渠道 - 邮件/钉钉/企业微信"
    echo ""

    echo "配置步骤:"
    echo "  1. 创建 ServiceMonitor 配置"
    echo "  2. 创建告警规则"
    echo "  3. 配置 Alertmanager 路由"
    echo "  4. 测试告警通知"
    echo ""

    echo "参考配置："
    echo "  - deployments/gitea-runner/servicemonitor.yaml"
    echo "  - deployments/gitea-runner/alerting-rules.yaml"
    echo ""
}

# 生成监控仪表板数据
generate_dashboard() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Gitea Runner 监控仪表板数据                           ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 收集数据
    echo "收集监控数据..."
    echo ""

    # Runner 状态
    RUNNING_PODS=$(kubectl get pods -n "$NAMESPACE" -l "$LABEL" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l || echo "0")
    TOTAL_PODS=$(kubectl get pods -n "$NAMESPACE" -l "$LABEL" --no-headers 2>/dev/null | wc -l || echo "0")

    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│  Gitea Runner 监控仪表板                                   │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│  运行中 Pod:    $RUNNING_PODS / $TOTAL_PODS                                │"
    echo "│  命名空间：     $NAMESPACE                                  │"
    echo "│  StatefulSet:  $STATEFULSET                               │"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""

    # 资源使用（如果 metrics-server 可用）
    echo "资源使用:"
    kubectl top pods -n "$NAMESPACE" -l "$LABEL" 2>/dev/null || echo "  ⚠️  metrics-server 未安装"
    echo ""
}

# 主函数
case "${1:-status}" in
    status)
        show_status
        ;;
    logs)
        if [ "$2" = "-f" ]; then
            follow_logs "${3:-gitea-org-runner-0}"
        else
            show_logs "${2:-gitea-org-runner-0}" "${3:-50}"
        fi
        ;;
    metrics)
        show_metrics
        ;;
    alert)
        configure_alerts
        ;;
    dashboard)
        generate_dashboard
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ 未知命令：$1${NC}"
        show_help
        exit 1
        ;;
esac
