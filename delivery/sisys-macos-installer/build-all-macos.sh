#!/bin/bash
# SISYS 通用构建脚本
# 用途：在 macOS 上构建完整的 DMG 和 PKG 安装包

set -euo pipefail

# 配置
APP_NAME="SISYS"
VERSION="0.15"
BUILD_DIR="$(pwd)/build"
DIST_DIR="$(pwd)/dist"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "[$1] ${2}"; }

echo "SISYS 构建工具 v0.15"

# 检查 macOS
if [[ "$(uname)" != "Darwin" ]]; then
    log "ERROR" "此脚本只能在 macOS 上运行"
    exit 1
fi

# 检查 Sisys.app
if [ ! -d "$DIST_DIR/Sisys.app" ]; then
    log "ERROR" "Sisys.app 未找到"
    exit 1
fi

log "INFO" "开始构建..."

# 清理
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 构建 DMG
log "INFO" "构建 DMG..."
hdiutil create \
    -volname "SISYS Installer" \
    -srcfolder "$DIST_DIR/Sisys.app" \
    -ov -format UDZO \
    "$BUILD_DIR/sisys-${VERSION}.dmg"

log "SUCCESS" "DMG 构建完成: $BUILD_DIR/sisys-${VERSION}.dmg"

# 生成校验
shasum -a 256 "$BUILD_DIR/sisys-${VERSION}.dmg" > "$BUILD_DIR/sisys-${VERSION}.dmg.sha256"

log "SUCCESS" "构建完成！"
