#!/bin/bash
# SISYS DMG 构建脚本
# 用途：使用 hdiutil 创建 DMG 安装包
# 运行环境：macOS

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
APP_NAME="SISYS"
VERSION="0.15"
BUILD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/build"
DIST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/dist"
DMG_NAME="sisys-${VERSION}.dmg"
VOLUME_NAME="SISYS Installer"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    local level="$1"; shift
    case "$level" in
        INFO)    echo -e "${BLUE}[INFO]${NC} $*" ;;
        SUCCESS) echo -e "${GREEN}[✓]${NC} $*" ;;
        WARNING) echo -e "${YELLOW}[⚠]${NC} $*" ;;
        ERROR)   echo -e "${RED}[✗]${NC} $*" ;;
    esac
}

# ============================================================================
# 前置检查
# ============================================================================
check_prerequisites() {
    log INFO "检查前置条件..."
    
    # 检查是否在 macOS 上运行
    if [[ "$(uname)" != "Darwin" ]]; then
        log ERROR "此脚本只能在 macOS 上运行"
        exit 1
    fi
    
    # 检查 Sisys.app 是否存在
    if [ ! -d "$DIST_DIR/Sisys.app" ]; then
        log ERROR "Sisys.app 未找到: $DIST_DIR/Sisys.app"
        exit 1
    fi
    
    log SUCCESS "前置检查通过"
}

# ============================================================================
# 创建临时 DMG 目录
# ============================================================================
create_staging_area() {
    log INFO "创建临时目录..."
    
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    
    local staging="$BUILD_DIR/staging"
    mkdir -p "$staging"
    
    # 复制 Sisys.app
    cp -r "$DIST_DIR/Sisys.app" "$staging/"
    
    # 创建 Applications 符号链接
    ln -s /Applications "$staging/Applications"
    
    log SUCCESS "临时目录已创建: $staging"
}

# ============================================================================
# 创建 DMG 背景图（可选）
# ============================================================================
create_background() {
    log INFO "创建 DMG 背景图..."
    
    local background_dir="$BUILD_DIR/background"
    mkdir -p "$background_dir"
    
    # 尝试使用 macOS 原生 sips 工具创建背景图
    if command -v sips &> /dev/null; then
        # 创建空白图片
        sips -s format png --out "$background_dir/dmg-background.png" \
            /System/Library/CoreServices/Installer.app/Contents/Resources/Installer.icns 2>/dev/null || \
        log WARNING "使用默认背景（sips 失败）"
    else
        # 使用 Python 创建简单的背景图（不依赖 PIL）
        python3 << 'PYTHON_EOF'
import struct
import zlib

def create_minimal_png(filename, width=600, height=400, color=(240, 244, 248)):
    """创建最小 PNG 图片"""
    # PNG 文件头
    signature = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    
    # IDAT chunk (图片数据)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # filter byte
        for x in range(width):
            raw_data += bytes(color)
    
    compressed = zlib.compress(raw_data)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    
    # IEND chunk
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    
    # 写入文件
    with open(filename, 'wb') as f:
        f.write(signature + ihdr_chunk + idat_chunk + iend_chunk)
    
    print(f"背景图已创建: {filename}")

create_minimal_png("build/background/dmg-background.png")
PYTHON_EOF
    fi
    
    log SUCCESS "背景图创建完成"
}

# ============================================================================
# 创建 .DS_Store（自定义 DMG 布局）
# ============================================================================
create_ds_store() {
    log INFO "创建 .DS_Store..."
    
    # 在 macOS 上，可以使用 AppleScript 或手动创建
    # 这里创建简单的布局配置
    cat > "$BUILD_DIR/.DS_Store.config" << 'EOF'
# DMG 窗口配置
# 窗口大小: 600x400
# 图标大小: 100x100
# Sisys.app 位置: (150, 180)
# Applications 链接位置: (450, 180)
EOF
    
    log SUCCESS ".DS_Store 配置已创建"
}

# ============================================================================
# 构建 DMG
# ============================================================================
build_dmg() {
    log INFO "构建 DMG..."
    
    local staging="$BUILD_DIR/staging"
    local dmg_path="$BUILD_DIR/$DMG_NAME"
    
    # 删除旧 DMG
    rm -f "$dmg_path"
    
    # 创建 DMG
    log INFO "正在创建 DMG 文件..."
    
    hdiutil create \
        -volname "$VOLUME_NAME" \
        -srcfolder "$staging" \
        -ov \
        -format UDZO \
        -compression-level 9 \
        -fs HFS+ \
        "$dmg_path"
    
    log SUCCESS "DMG 创建完成: $dmg_path"
}

# ============================================================================
# 生成 SHA256 校验
# ============================================================================
generate_checksum() {
    log INFO "生成 SHA256 校验..."
    
    local dmg_path="$BUILD_DIR/$DMG_NAME"
    
    shasum -a 256 "$dmg_path" > "$BUILD_DIR/${DMG_NAME}.sha256"
    
    log SUCCESS "SHA256 校验已生成: ${DMG_NAME}.sha256"
}

# ============================================================================
# 显示构建结果
# ============================================================================
show_results() {
    echo ""
    log SUCCESS "DMG 构建完成！"
    echo ""
    
    local dmg_path="$BUILD_DIR/$DMG_NAME"
    local dmg_size=$(du -h "$dmg_path" | cut -f1)
    
    echo -e "${BLUE}文件信息:${NC}"
    echo "  文件名: $DMG_NAME"
    echo "  大小: $dmg_size"
    echo "  路径: $dmg_path"
    echo ""
    echo -e "${BLUE}校验和:${NC}"
    cat "$BUILD_DIR/${DMG_NAME}.sha256"
    echo ""
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}         ${GREEN}SISYS DMG 构建工具 v0.15${NC}                        ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_prerequisites
    create_staging_area
    create_background
    create_ds_store
    build_dmg
    generate_checksum
    show_results
}

main "$@"
