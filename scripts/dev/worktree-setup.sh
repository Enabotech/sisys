#!/bin/bash
# =============================================================================
# sisys-worktree-setup.sh - Git Worktree 并行开发环境快速设置脚本
# =============================================================================
# 用途：快速创建多个 Story 的并行开发环境
# 使用示例：
#   ./scripts/dev/worktree-setup.sh story-1.1 story-1.2 story-1.3
#   ./scripts/dev/worktree-setup.sh --stories 1.1,1.2,1.3
# =============================================================================

set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKTREE_BASE="${SISYS_WORKTREE_BASE:-$HOME/dev/sisys-worktrees}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示使用帮助
show_help() {
    cat << EOF
sisys Git Worktree 并行开发环境设置脚本

用法:
  $0 [选项] <story 编号列表>

选项:
  -h, --help              显示帮助信息
  -b, --base <path>       设置 worktree 基础目录 (默认：\$HOME/dev/sisys-worktrees)
  -c, --clean             清理已存在的 worktree
  -d, --dry-run           预览将执行的操作，不实际创建
  -v, --verbose           显示详细输出

示例:
  # 创建单个 Story worktree
  $0 1.1

  # 创建多个 Story worktrees
  $0 1.1 1.2 1.3

  # 使用逗号分隔
  $0 --stories 1.1,1.2,1.3

  # 自定义 worktree 目录
  $0 -b ~/dev/worktrees 1.1 1.2

  # 清理并重新创建
  $0 -c 1.1

参数:
  story 编号    Story 编号，如 1.1, 1.2, 1.3 等

EOF
}

# 解析命令行参数
PARSE_ARGS=()
CLEAN_EXISTING=false
DRY_RUN=false
VERBOSE=false
STORY_LIST=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -b|--base)
            WORKTREE_BASE="$2"
            shift 2
            ;;
        -c|--clean)
            CLEAN_EXISTING=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --stories)
            IFS=',' read -ra STORIES <<< "$2"
            STORY_LIST+=("${STORIES[@]}")
            shift 2
            ;;
        *)
            STORY_LIST+=("$1")
            shift
            ;;
    esac
done

# 验证输入
if [ ${#STORY_LIST[@]} -eq 0 ]; then
    log_error "请至少指定一个 Story 编号"
    show_help
    exit 1
fi

# 检查 Git 版本
check_git_version() {
    log_info "检查 Git 版本..."
    GIT_VERSION=$(git --version | awk '{print $3}')
    REQUIRED_VERSION="2.9.0"

    if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$GIT_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
        log_error "Git 版本过低 (当前：$GIT_VERSION, 要求：>= $REQUIRED_VERSION)"
        exit 1
    fi

    log_success "Git 版本符合要求：$GIT_VERSION"
}

# 检查 Python 环境
check_python() {
    log_info "检查 Python 环境..."
    if ! command -v python3 &> /dev/null; then
        log_error "未找到 python3"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version)
    log_success "Python 环境：$PYTHON_VERSION"
}

# 创建 worktree 基础目录
create_worktree_base() {
    if [ ! -d "$WORKTREE_BASE" ]; then
        log_info "创建 worktree 基础目录：$WORKTREE_BASE"
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] mkdir -p $WORKTREE_BASE"
        else
            mkdir -p "$WORKTREE_BASE"
        fi
    fi
}

# 创建单个 Story worktree
create_story_worktree() {
    local STORY_NUM=$1
    local BRANCH_NAME="story/$STORY_NUM-$(echo $STORY_NUM | tr '.' '-')"
    local WORKTREE_PATH="$WORKTREE_BASE/story-$STORY_NUM"

    log_info "处理 Story $STORY_NUM..."

    # 标准化分支名称（1.1 -> story/1-1-hexagonal-architecture 等）
    case $STORY_NUM in
        "1.1")
            BRANCH_NAME="story/1.1-hexagonal-architecture"
            ;;
        "1.2")
            BRANCH_NAME="story/1.2-domain-events"
            ;;
        "1.3")
            BRANCH_NAME="story/1.3-event-bus"
            ;;
        *)
            BRANCH_NAME="story/$STORY_NUM"
            ;;
    esac

    # 检查 worktree 是否已存在
    if [ -d "$WORKTREE_PATH" ]; then
        if [ "$CLEAN_EXISTING" = true ]; then
            log_warning "Worktree 已存在，将清理：$WORKTREE_PATH"
            if [ "$DRY_RUN" = true ]; then
                log_info "[DRY RUN] git worktree remove $WORKTREE_PATH"
            else
                git worktree remove "$WORKTREE_PATH" || true
            fi
        else
            log_warning "Worktree 已存在，跳过：$WORKTREE_PATH"
            return 0
        fi
    fi

    # 检查分支是否存在
    if ! git rev-parse --verify "$BRANCH_NAME" &> /dev/null; then
        log_info "创建新分支：$BRANCH_NAME"
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] git checkout -b $BRANCH_NAME"
        else
            git checkout -b "$BRANCH_NAME" || true
        fi
    fi

    # 创建 worktree
    log_info "创建 worktree: $WORKTREE_PATH ($BRANCH_NAME)"
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] git worktree add -b $BRANCH_NAME $WORKTREE_PATH main"
    else
        git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" main
    fi

    # 设置虚拟环境
    if [ "$DRY_RUN" = false ]; then
        log_info "设置 Python 虚拟环境..."
        (
            cd "$WORKTREE_PATH"
            python3 -m venv venv
            source venv/bin/activate
            poetry install --with dev,test
        )
    else
        log_info "[DRY RUN] cd $WORKTREE_PATH && python3 -m venv venv && poetry install"
    fi

    log_success "Story $STORY_NUM worktree 创建完成"
}

# 显示设置完成信息
show_completion_message() {
    echo ""
    log_success "=========================================="
    log_success "   Git Worktree 并行开发环境设置完成！"
    log_success "=========================================="
    echo ""
    echo "创建的 worktrees:"
    for STORY_NUM in "${STORY_LIST[@]}"; do
        echo "  - $WORKTREE_BASE/story-$STORY_NUM"
    done
    echo ""
    echo "快速开始指南:"
    echo ""
    echo "1. 进入 worktree 目录:"
    for STORY_NUM in "${STORY_LIST[@]}"; do
        echo "   cd $WORKTREE_BASE/story-$STORY_NUM"
    done
    echo ""
    echo "2. 激活 Qwen Code Agent:"
    echo "   @qwen-agent activate domain_agent_1"
    echo ""
    echo "3. 开始 SDD+TDD 开发循环:"
    echo "   make sdd-define"
    echo "   make tdd-red TARGET=domain/entities"
    echo "   make tdd-green TARGET=domain/entities"
    echo "   make tdd-refactor TARGET=domain/entities"
    echo ""
    echo "4. 查看完整指南:"
    echo "   cat docs/developer/qwen-git-worktree-parallel-dev-guide.md"
    echo ""
}

# 主函数
main() {
    echo "============================================"
    echo "  sisys Git Worktree 并行开发环境设置"
    echo "============================================"
    echo ""

    # 切换到项目根目录
    cd "$PROJECT_ROOT"

    # 执行检查
    check_git_version
    check_python
    create_worktree_base

    echo ""
    log_info "将为以下 Story 创建 worktrees: ${STORY_LIST[*]}"
    echo ""

    # 创建每个 Story 的 worktree
    for STORY_NUM in "${STORY_LIST[@]}"; do
        echo "----------------------------------------"
        create_story_worktree "$STORY_NUM"
        echo ""
    done

    # 显示完成信息
    show_completion_message
}

# 执行主函数
main
