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

# 启动逻辑
main() {
    if [ $# -gt 0 ]; then
        # 如果有参数，执行参数（支持 K8s 覆盖）
        exec "$@"
    elif [ -d "/app/src/app" ]; then
        # 如果应用代码存在，启动应用
        log_info "检测到 SISYS 应用程序，启动应用..."
        exec poetry run python -m src.app
    else
        # 开发平台占位模式：启动简易 HTTP 服务器响应探针
        log_warn "SISYS 开发中，8080端口启动 HTTP 响应服务..."
        exec python3 -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Development Placeholder OK')
    def log_message(self, format, *args): pass
HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
"
    fi
}

main "$@"
