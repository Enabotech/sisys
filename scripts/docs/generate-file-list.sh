#!/bin/bash
# Harbor 文件清单生成脚本
# Story 0.6: Harbor 镜像仓库部署
#
# 修复 MEDIUM-003: File List 与实际文件不一致
# 问题描述：Story 文件中的 File List 手动维护，容易与实际文件不一致
# 解决方案：自动扫描实际文件并生成 Markdown 表格
#
# 使用方式:
#   ./scripts/docs/generate-file-list.sh harbor
#
# 输出：Markdown 格式的文件清单表格

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

# 支持的组件
COMPONENTS=("harbor" "gitea" "argocd" "all")

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

# 显示使用帮助
show_help() {
    echo "=============================================================================="
    echo "Harbor 文件清单生成脚本"
    echo "=============================================================================="
    echo ""
    echo "使用方式:"
    echo "  $0 <component>"
    echo ""
    echo "支持的组件:"
    echo "  harbor  - Harbor 镜像仓库"
    echo "  gitea   - Gitea 代码托管"
    echo "  argocd  - ArgoCD 持续部署"
    echo "  all     - 所有组件"
    echo ""
    echo "示例:"
    echo "  $0 harbor    # 生成 Harbor 文件清单"
    echo "  $0 all       # 生成所有组件文件清单"
    echo ""
}

# 获取文件描述 (从文件第一行注释)
get_file_description() {
    local file="$1"
    local desc=""

    # 尝试从第一行注释获取描述
    desc=$(head -1 "$file" 2>/dev/null | grep -oP '(?<=# ).*' || echo "")

    # 如果没有注释，尝试从文件名推断
    if [[ -z "$desc" ]]; then
        case "$(basename "$file")" in
            values.yaml) desc="Helm Chart 配置" ;;
            ingress*.yaml) desc="Ingress 路由配置" ;;
            networkpolicy.yaml) desc="网络策略配置" ;;
            middleware.yaml) desc="Traefik Middleware 配置" ;;
            secrets*.yaml) desc="Kubernetes Secret 配置" ;;
            kustomization.yaml) desc="Kustomize 组合配置" ;;
            namespace.yaml) desc="命名空间配置" ;;
            *-job.yaml) desc="Kubernetes Job 配置" ;;
            *.py) desc="Python 测试文件" ;;
            *.sh) desc="Shell 脚本" ;;
            *.md) desc="文档" ;;
            *) desc="配置文件" ;;
        esac
    fi

    echo "$desc"
}

# 获取文件操作类型
get_operation_type() {
    local file="$1"

    if [[ "$file" == *".yaml" || "$file" == *".yml" ]]; then
        echo "✅ 已创建"
    elif [[ "$file" == *".py" ]]; then
        echo "✅ 已创建"
    elif [[ "$file" == *".sh" ]]; then
        echo "✅ 已创建"
    elif [[ "$file" == *".md" ]]; then
        echo "✅ 已创建"
    else
        echo "📄 已创建"
    fi
}

# 生成 Harbor 文件清单
generate_harbor_file_list() {
    local harbor_dir="$PROJECT_ROOT/deploy/kubernetes/harbor"
    local scripts_dir="$PROJECT_ROOT/scripts"
    local tests_dir="$PROJECT_ROOT/tests/deployment"
    local docs_dir="$PROJECT_ROOT/docs/deployment"

    echo "### File List"
    echo ""
    echo "**自动生成:** 运行 \`./scripts/docs/generate-file-list.sh harbor\` 生成最新文件清单"
    echo ""
    echo "**部署配置文件:**"
    echo ""
    echo "| 文件路径 | 操作类型 | 说明 | 行数 |"
    echo "|---------|---------|------|------|"

    # 扫描 deploy/kubernetes/harbor 目录
    if [[ -d "$harbor_dir" ]]; then
        for file in "$harbor_dir"/*.yaml; do
            if [[ -f "$file" ]]; then
                local filename=$(basename "$file")
                local relpath="deploy/kubernetes/harbor/$filename"
                local lines=$(wc -l < "$file")
                local desc=$(get_file_description "$file")
                local op=$(get_operation_type "$file")
                echo "| \`$relpath\` | $op | $desc | $lines |"
            fi
        done
    fi

    echo ""
    echo "**脚本文件:**"
    echo ""
    echo "| 文件路径 | 操作类型 | 说明 | 行数 |"
    echo "|---------|---------|------|------|"

    # 扫描 scripts/deployment/harbor 目录
    if [[ -d "$scripts_dir/deployment/harbor" ]]; then
        for file in "$scripts_dir/deployment/harbor"/*.sh; do
            if [[ -f "$file" ]]; then
                local filename=$(basename "$file")
                local relpath="scripts/deployment/harbor/$filename"
                local lines=$(wc -l < "$file")
                local desc=$(get_file_description "$file")
                local op=$(get_operation_type "$file")
                echo "| \`$relpath\` | $op | $desc | $lines |"
            fi
        done
    fi

    # 扫描 scripts/security 目录
    if [[ -d "$scripts_dir/security" ]]; then
        for file in "$scripts_dir/security"/*.sh; do
            if [[ -f "$file" ]]; then
                local filename=$(basename "$file")
                local relpath="scripts/security/$filename"
                local lines=$(wc -l < "$file")
                local desc=$(get_file_description "$file")
                local op=$(get_operation_type "$file")
                echo "| \`$relpath\` | $op | $desc | $lines |"
            fi
        done
    fi

    echo ""
    echo "**测试文件:**"
    echo ""
    echo "| 文件路径 | 操作类型 | 说明 | 行数 |"
    echo "|---------|---------|------|------|"

    # 扫描 tests/deployment 目录
    if [[ -d "$tests_dir" ]]; then
        for file in "$tests_dir"/test_harbor*.py; do
            if [[ -f "$file" ]]; then
                local filename=$(basename "$file")
                local relpath="tests/deployment/$filename"
                local lines=$(wc -l < "$file")
                # 从 Python 文件 docstring 获取描述
                local desc=$(grep -m1 '^"""' "$file" 2>/dev/null | sed 's/^"""//' | head -c 50 || echo "测试文件")
                local op=$(get_operation_type "$file")
                echo "| \`$relpath\` | $op | $desc... | $lines |"
            fi
        done
    fi

    echo ""
    echo "**文档文件:**"
    echo ""
    echo "| 文件路径 | 操作类型 | 说明 | 行数 |"
    echo "|---------|---------|------|------|"

    # 扫描 docs/deployment 目录
    if [[ -d "$docs_dir" ]]; then
        for file in "$docs_dir"/HARBOR*.md; do
            if [[ -f "$file" ]]; then
                local filename=$(basename "$file")
                local relpath="docs/deployment/$filename"
                local lines=$(wc -l < "$file")
                local desc=$(head -1 "$file" 2>/dev/null | sed 's/^# //' || echo "文档")
                local op=$(get_operation_type "$file")
                echo "| \`$relpath\` | $op | $desc | $lines |"
            fi
        done
        # 如果没有 HARBOR 开头的文档，尝试其他文档
        if ! ls "$docs_dir"/HARBOR*.md 1> /dev/null 2>&1; then
            for file in "$docs_dir"/*.md; do
                if [[ -f "$file" ]]; then
                    local filename=$(basename "$file")
                    local relpath="docs/deployment/$filename"
                    local lines=$(wc -l < "$file")
                    local desc=$(head -1 "$file" 2>/dev/null | sed 's/^# //' || echo "文档")
                    local op=$(get_operation_type "$file")
                    echo "| \`$relpath\` | $op | $desc | $lines |"
                fi
            done
        fi
    fi

    echo ""
}

# 生成所有组件文件清单
generate_all_file_list() {
    echo "## 完整文件清单"
    echo ""
    echo "### Harbor 镜像仓库"
    generate_harbor_file_list
    # 未来可以添加其他组件
    # echo "### Gitea 代码托管"
    # generate_gitea_file_list
    # echo "### ArgoCD 持续部署"
    # generate_argocd_file_list
}

# =============================================================================
# 主流程
# =============================================================================

main() {
    if [[ $# -lt 1 ]]; then
        show_help
        exit 1
    fi

    local component="$1"

    case "$component" in
        harbor)
            log_info "生成 Harbor 文件清单..."
            generate_harbor_file_list
            log_success "Harbor 文件清单生成完成"
            ;;
        all)
            log_info "生成所有组件文件清单..."
            generate_all_file_list
            log_success "所有组件文件清单生成完成"
            ;;
        *)
            log_error "未知组件：$component"
            show_help
            exit 1
            ;;
    esac
}

# 执行主流程
main "$@"
