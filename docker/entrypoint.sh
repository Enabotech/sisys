#!/bin/bash
set -e

# =========================================
# SISYS 开发环境入口脚本
# =========================================
# 用途：
# 1. 开发模式：默认启动 bash，支持交互式开发
# 2. 应用模式：运行指定的 Python/Node.js 命令
# 3. CI/CD 模式：执行构建、测试等任务
# =========================================

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印欢迎信息
print_welcome() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  SISYS 开发环境${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓${NC} Python:  $(python --version 2>&1)"
    echo -e "${GREEN}✓${NC} Node.js: $(node --version)"
    echo -e "${GREEN}✓${NC} npm:     $(npm --version)"
    echo -e "${GREEN}✓${NC} Poetry:  $(poetry --version)"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# 检查是否在 Poetry 虚拟环境中
check_poetry_env() {
    if [ -d ".venv" ]; then
        echo -e "${YELLOW}⚠ 检测到本地 Poetry 虚拟环境${NC}"
        echo -e "${YELLOW}  提示：使用 'poetry shell' 激活环境${NC}"
        echo ""
    fi
}

# 主逻辑
main() {
    # 如果有参数，执行参数中的命令
    if [ $# -gt 0 ]; then
        exec "$@"
    fi

    # 默认行为：交互式 bash
    print_welcome
    check_poetry_env
    
    echo -e "${YELLOW}💡 常用命令:${NC}"
    echo "  poetry install          - 安装项目依赖"
    echo "  poetry shell            - 激活虚拟环境"
    echo "  poetry run python app   - 运行应用"
    echo "  poetry run pytest       - 运行测试"
    echo "  exit                    - 退出容器"
    echo ""
    
    exec /bin/bash
}

main "$@"
