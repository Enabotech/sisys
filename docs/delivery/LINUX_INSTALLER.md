# Linux 安装程序制作指南

本文档介绍如何为 Sisyphus 系统创建 Linux 安装程序。

## 目录

- [1. 概述](#1-概述)
- [2. 技术选型](#2-技术选型)
- [3. DEB 包制作 (Debian/Ubuntu)](#3-deb-包制作-debianubuntu)
- [4. RPM 包制作 (RHEL/CentOS/Fedora)](#4-rpm-包制作-rhelcentosfedora)
- [5. AppImage 制作](#5-appimage-制作)
- [6. Flatpak 制作](#6-flatpak-制作)
- [7. Snap 包制作](#7-snap-包制作)
- [8. 通用安装脚本](#8-通用安装脚本)
- [9. 故障排查](#9-故障排查)

---

## 1. 概述

Linux 安装程序需要支持：

- 主流发行版（Debian、Ubuntu、RHEL、Fedora、Arch）
- 多种包格式（DEB、RPM、AppImage、Flatpak、Snap）
- 系统服务配置（systemd）
- 依赖自动安装
- 卸载支持

---

## 2. 技术选型

| 格式 | 适用发行版 | 优点 | 缺点 |
|-----|-----------|------|------|
| DEB | Debian/Ubuntu/Mint | 原生支持，依赖管理好 | 仅限 DEB 系 |
| RPM | RHEL/CentOS/Fedora | 原生支持，企业级 | 仅限 RPM 系 |
| AppImage | 所有发行版 | 通用，无需安装 | 无系统集成 |
| Flatpak | 所有发行版 | 沙盒安全，通用 | 体积较大 |
| Snap | 所有发行版 | 自动更新，通用 | Canonical 专有 |

**推荐**: 同时提供 DEB/RPM（原生）和 AppImage（通用）

---

## 3. DEB 包制作 (Debian/Ubuntu)

### 3.1 目录结构

```
sisys_0.3.0_amd64/
├── DEBIAN/
│   ├── control
│   ├── preinst
│   ├── postinst
│   ├── prerm
│   └── postrm
├── usr/
│   ├── bin/
│   │   └── sisys
│   ├── lib/
│   │   └── sisys/
│   │       ├── lib/
│   │       ├── configs/
│   │       └── share/
│   └── share/
│       ├── applications/
│       │   └── sisys.desktop
│       └── icons/
│           └── hicolor/
│               └── scalable/
│                   └── apps/
│                       └── sisys.svg
└── etc/
    └── sisys/
        └── default.yaml
```

### 3.2 control 文件

```
# DEBIAN/control
Package: sisys
Version: 0.3.0
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.10), python3-pip, python3-venv, curl, git
Recommends: docker.io, kubectl
Suggests: argocd
Maintainer: Sisyphus Team <support@sisys.example.com>
Description: Sisyphus Intelligent Development Assistant
 Sisyphus is an intelligent development assistant that provides
 automated CI/CD, Kubernetes management, and development tools.
 .
 Features:
  - Automated CI/CD pipeline
  - Kubernetes cluster management
  - Harbor registry integration
  - ArgoCD GitOps deployment
Homepage: https://sisys.example.com
License: MIT
```

### 3.3 安装脚本

```bash
#!/bin/bash
# DEBIAN/preinst

#!/bin/sh
set -e

# 备份旧配置
if [ -f /etc/sisys/default.yaml ]; then
    cp /etc/sisys/default.yaml /etc/sisys/default.yaml.backup.$(date +%Y%m%d%H%M%S)
fi

# 停止旧服务
systemctl stop sisys.service 2>/dev/null || true

exit 0
```

```bash
#!/bin/bash
# DEBIAN/postinst

#!/bin/sh
set -e

case "$1" in
    configure)
        # 创建用户和组
        if ! getent group sisys > /dev/null; then
            groupadd --system sisys
        fi

        if ! getent passwd sisys > /dev/null; then
            useradd --system \
                --gid sisys \
                --home-dir /var/lib/sisys \
                --create-home \
                --shell /bin/false \
                sisys
        fi

        # 设置权限
        chown -R sisys:sisys /var/lib/sisys
        chown -R sisys:sisys /var/log/sisys
        chmod 755 /usr/bin/sisys

        # 安装 systemd 服务
        if [ -f /usr/lib/systemd/system/sisys.service ]; then
            systemctl daemon-reload
            systemctl enable sisys.service
        fi

        # 刷新桌面数据库
        update-desktop-database 2>/dev/null || true
        update-icon-caches /usr/share/icons/* 2>/dev/null || true
        ;;
esac

exit 0
```

```bash
#!/bin/bash
# DEBIAN/prerm

#!/bin/sh
set -e

case "$1" in
    remove|upgrade)
        # 停止服务
        systemctl stop sisys.service 2>/dev/null || true
        systemctl disable sisys.service 2>/dev/null || true
        ;;
    deconfigure)
        # 完全卸载时停止服务
        systemctl stop sisys.service 2>/dev/null || true
        systemctl disable sisys.service 2>/dev/null || true
        ;;
esac

exit 0
```

```bash
#!/bin/bash
# DEBIAN/postrm

#!/bin/sh
set -e

case "$1" in
    remove)
        # 保留配置和数据
        echo "Configuration files preserved in /etc/sisys/"
        echo "Data preserved in /var/lib/sisys/"
        ;;
    purge)
        # 完全清除
        rm -rf /etc/sisys
        rm -rf /var/lib/sisys
        rm -rf /var/log/sisys

        # 删除用户和组
        userdel sisys 2>/dev/null || true
        groupdel sisys 2>/dev/null || true
        ;;
    upgrade)
        # 升级后重启服务
        systemctl start sisys.service 2>/dev/null || true
        ;;
esac

exit 0
```

### 3.4 systemd 服务文件

```ini
# usr/lib/systemd/system/sisys.service
[Unit]
Description=Sisyphus Development Assistant
Documentation=https://docs.sisys.example.com
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=sisys
Group=sisys
ExecStart=/usr/bin/sisys run --config /etc/sisys/default.yaml
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sisys

# 安全设置
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/sisys /var/log/sisys
PrivateTmp=true

# 资源限制
MemoryLimit=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

### 3.5 Desktop 文件

```ini
# usr/share/applications/sisys.desktop
[Desktop Entry]
Name=Sisyphus
GenericName=Development Assistant
Comment=Intelligent Development Assistant with CI/CD and Kubernetes support
Exec=/usr/bin/sisys gui
Icon=sisys
Type=Application
Categories=Development;Utility;
Keywords=development;kubernetes;ci/cd;docker;
StartupNotify=true
StartupWMClass=sisys
```

### 3.6 构建 DEB 包

```bash
#!/bin/bash
# build-deb.sh

set -e

PACKAGE_NAME="sisys"
VERSION="0.3.0"
ARCHITECTURE="amd64"

echo "=== Building DEB package ==="

# 清理
rm -rf build-deb
mkdir -p build-deb

# 创建目录结构
DEB_DIR="build-deb/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}"
mkdir -p "${DEB_DIR}"/{DEBIAN,usr/bin,usr/lib/sisys,etc/sisys,var/lib/sisys,var/log/sisys,usr/share/applications,usr/share/icons/hicolor/scalable/apps,usr/lib/systemd/system}

# 复制文件
cp dist/sisys "${DEB_DIR}/usr/bin/"
cp -r dist/lib/* "${DEB_DIR}/usr/lib/sisys/"
cp configs/default.yaml "${DEB_DIR}/etc/sisys/"
cp scripts/debian/{control,preinst,postinst,prerm,postrm} "${DEB_DIR}/DEBIAN/"
cp sisys.service "${DEB_DIR}/usr/lib/systemd/system/"
cp sisys.desktop "${DEB_DIR}/usr/share/applications/"
cp assets/sisys.svg "${DEB_DIR}/usr/share/icons/hicolor/scalable/apps/"

# 设置权限
chmod 755 "${DEB_DIR}/usr/bin/sisys"
chmod 755 "${DEB_DIR}/DEBIAN"/*

# 构建 DEB
cd build-deb
dpkg-deb --build "${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}"
cd ..

echo "DEB package created: build-deb/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}.deb"

# 验证
lintian build-deb/${PACKAGE_NAME}_${VERSION}_${ARCHITECTURE}.deb || true
```

### 3.7 安装 DEB 包

```bash
# 安装
sudo dpkg -i sisys_0.3.0_amd64.deb

# 或自动解决依赖
sudo apt install ./sisys_0.3.0_amd64.deb

# 验证
dpkg -l | grep sisys
sisys --version

# 卸载
sudo apt remove sisys

# 完全清除
sudo apt purge sisys
```

---

## 4. RPM 包制作 (RHEL/CentOS/Fedora)

### 4.1 SPEC 文件

```spec
# sisys.spec
Name:           sisys
Version:        0.3.0
Release:        1%{?dist}
Summary:        Sisyphus Intelligent Development Assistant
License:        MIT
URL:            https://sisys.example.com
Source0:        %{name}-%{version}.tar.gz

BuildArch:      x86_64

# 依赖
Requires:       python3 >= 3.10
Requires:       python3-pip
Requires:       curl
Requires:       git
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

%description
Sisyphus is an intelligent development assistant that provides
automated CI/CD, Kubernetes management, and development tools.

%prep
%setup -q

%build
# 无需编译，Python 应用

%install
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/lib/sisys
mkdir -p %{buildroot}/etc/sisys
mkdir -p %{buildroot}/var/lib/sisys
mkdir -p %{buildroot}/var/log/sisys
mkdir -p %{buildroot}/usr/lib/systemd/system
mkdir -p %{buildroot}/usr/share/applications

install -m 755 sisys %{buildroot}/usr/bin/
cp -r lib/* %{buildroot}/usr/lib/sisys/
cp configs/default.yaml %{buildroot}/etc/sisys/
install -m 644 sisys.service %{buildroot}/usr/lib/systemd/system/
install -m 644 sisys.desktop %{buildroot}/usr/share/applications/

%pre
# 安装前脚本
getent group sisys >/dev/null || groupadd -r sisys
getent passwd sisys >/dev/null || useradd -r -g sisys -d /var/lib/sisys -s /sbin/nologin sisys

%post
%systemd_post sisys.service
chmod 755 /usr/bin/sisys
chown -R sisys:sisys /var/lib/sisys /var/log/sisys

%preun
%systemd_preun sisys.service

%postun
%systemd_postun_with_restart sisys.service

%files
/usr/bin/sisys
/usr/lib/sisys/
/etc/sisys/default.yaml
%config(noreplace) /etc/sisys/default.yaml
/usr/lib/systemd/system/sisys.service
/usr/share/applications/sisys.desktop
%dir /var/lib/sisys
%dir /var/log/sisys

%changelog
* Wed Mar 11 2026 Sisyphus Team <support@sisys.example.com> - 0.3.0
- Initial package
```

### 4.2 构建 RPM 包

```bash
#!/bin/bash
# build-rpm.sh

set -e

PACKAGE_NAME="sisys"
VERSION="0.3.0"

echo "=== Building RPM package ==="

# 设置构建环境
RPM_BUILD_DIR=$(pwd)/rpm-build
mkdir -p ${RPM_BUILD_DIR}/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# 准备源码包
tar -czf ${RPM_BUILD_DIR}/SOURCES/${PACKAGE_NAME}-${VERSION}.tar.gz \
    --exclude=rpm-build \
    --exclude=build-* \
    .

# 复制 SPEC 文件
cp sisys.spec ${RPM_BUILD_DIR}/SPECS/

# 构建 RPM
rpmbuild --define "_topdir ${RPM_BUILD_DIR}" \
    -bb ${RPM_BUILD_DIR}/SPECS/sisys.spec

# 输出结果
echo "RPM package created:"
ls -la ${RPM_BUILD_DIR}/RPMS/x86_64/*.rpm
```

### 4.3 安装 RPM 包

```bash
# 安装
sudo rpm -ivh sisys-0.3.0-1.el9.x86_64.rpm

# 或使用 dnf（自动解决依赖）
sudo dnf install ./sisys-0.3.0-1.el9.x86_64.rpm

# 验证
rpm -qa | grep sisys
sisys --version

# 卸载
sudo dnf remove sisys
```

---

## 5. AppImage 制作

### 5.1 AppDir 结构

```
Sisyphus.AppDir/
├── AppRun          # 启动脚本
├── sisys.desktop   # Desktop 文件
├── sisys.svg       # 图标
├── usr/
│   ├── bin/
│   │   └── sisys
│   ├── lib/
│   │   └── sisys/
│   └── share/
└── lib/            # 依赖库
```

### 5.2 AppRun 脚本

```bash
#!/bin/bash
# AppRun

HERE="$(cd "$(dirname "$0")" && pwd)"
export APPIMAGE="${HERE}"

# 设置环境变量
export PYTHONPATH="${HERE}/usr/lib/sisys:${PYTHONPATH}"
export PATH="${HERE}/usr/bin:${PATH}"
export SISYS_HOME="${HERE}/usr/lib/sisys"

# 执行主程序
exec "${HERE}/usr/bin/sisys" "$@"
```

### 5.3 构建 AppImage

```bash
#!/bin/bash
# build-appimage.sh

set -e

APP_NAME="Sisyphus"
VERSION="0.3.0"

echo "=== Building AppImage ==="

# 清理
rm -rf AppDir build
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/lib/sisys

# 复制文件
cp dist/sisys AppDir/usr/bin/
cp -r dist/lib/* AppDir/usr/lib/sisys/
cp configs/default.yaml AppDir/usr/lib/sisys/

# 复制 Desktop 文件和图标
cp sisys.desktop AppDir/
cp assets/sisys.svg AppDir/

# 创建 AppRun
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${HERE}/usr/lib/sisys:${PYTHONPATH}"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/sisys" "$@"
EOF
chmod +x AppDir/AppRun

# 下载 appimagetool
wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage

# 构建 AppImage
ARCH=x86_64 ./appimagetool-x86_64.AppImage \
    AppDir \
    build/${APP_NAME}-${VERSION}-x86_64.AppImage

echo "AppImage created: build/${APP_NAME}-${VERSION}-x86_64.AppImage"
```

### 5.4 使用 AppImage

```bash
# 赋予执行权限
chmod +x Sisyphus-0.3.0-x86_64.AppImage

# 运行
./Sisyphus-0.3.0-x86_64.AppImage

# 集成到系统（可选）
./Sisyphus-0.3.0-x86_64.AppImage --appimage-install

# 或使用 appimaged
# 安装 appimaged 后自动识别 AppImage
```

---

## 6. Flatpak 制作

### 6.1 Manifest 文件

```yaml
# com.sisyphus.app.yml
app-id: com.sisyphus.app
runtime: org.freedesktop.Platform
runtime-version: '23.08'
sdk: org.freedesktop.Sdk
command: sisys

finish-args:
  - --share=network
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  - --filesystem=home
  - --filesystem=xdg-config/sisys:create
  - --talk-name=org.freedesktop.Flatpak

modules:
  - name: sisys
    buildsystem: simple
    build-commands:
      - install -D sisys /app/bin/sisys
      - install -D sisys.desktop /app/share/applications/com.sisyphus.app.desktop
      - install -D sisys.svg /app/share/icons/hicolor/scalable/apps/com.sisyphus.app.svg
      - cp -r lib /app/lib/sisys
    sources:
      - type: archive
        url: https://github.com/sisyphus/sisys/releases/download/v0.3.0/sisys-0.3.0-linux.tar.gz
        sha256: abc123...
      - type: file
        path: sisys.desktop
        dest-filename: sisys.desktop
      - type: file
        path: sisys.svg
        dest-filename: sisys.svg
```

### 6.2 构建 Flatpak

```bash
#!/bin/bash
# build-flatpak.sh

set -e

echo "=== Building Flatpak ==="

# 安装依赖
flatpak install -y flathub org.freedesktop.Platform//23.08
flatpak install -y flathub org.freedesktop.Sdk//23.08

# 构建
flatpak-builder --force-clean \
    --repo=repo \
    build-dir \
    com.sisyphus.app.yml

# 创建 bundle
flatpak build-bundle repo Sisyphus-0.3.0.flatpak com.sisyphus.app

echo "Flatpak created: Sisyphus-0.3.0.flatpak"
```

### 6.3 安装 Flatpak

```bash
# 安装
flatpak install Sisyphus-0.3.0.flatpak

# 运行
flatpak run com.sisyphus.app

# 创建快捷方式
flatpak override --user --filesystem=home com.sisyphus.app
```

---

## 7. Snap 包制作

### 7.1 snapcraft.yaml

```yaml
# snap/snapcraft.yaml
name: sisys
version: '0.3.0'
summary: Sisyphus Intelligent Development Assistant
description: |
  Sisyphus is an intelligent development assistant that provides
  automated CI/CD, Kubernetes management, and development tools.

base: core22
confinement: strict
grade: stable

apps:
  sisys:
    command: bin/sisys
    plugs:
      - home
      - network
      - docker
      - kubernetes
    environment:
      PYTHONPATH: $SNAP/usr/lib/sisys
      SISYS_HOME: $SNAP_DATA

  gui:
    command: bin/sisys-gui
    plugs:
      - desktop
      - desktop-legacy
      - wayland
      - x11
      - home
      - network

parts:
  sisys:
    plugin: dump
    source: .
    organize:
      dist/sisys: bin/sisys
      dist/lib: usr/lib/sisys
      configs: etc/sisys

    stage-packages:
      - python3
      - python3-pip
      - python3-venv
      - curl
      - git

    override-build: |
      snapcraftctl build
      pip3 install --target=$SNAPCRAFT_PART_INSTALL/usr/lib/sisys -r requirements.txt

plugs:
  docker:
    interface: docker
  kubernetes:
    interface: kubernetes
```

### 7.2 构建 Snap

```bash
#!/bin/bash
# build-snap.sh

set -e

echo "=== Building Snap ==="

# 安装 snapcraft
sudo snap install snapcraft --classic

# 构建
snapcraft --use-lxd

# 或使用 multipass
snapcraft

echo "Snap created: sisys_0.3.0_amd64.snap"
```

### 7.3 安装 Snap

```bash
# 本地安装
sudo snap install --dangerous sisys_0.3.0_amd64.snap

# 从 Snap Store 安装（发布后）
sudo snap install sisys

# 连接接口
sudo snap connect sisys:docker
sudo snap connect sisys:kubernetes
sudo snap connect sisys:home
```

---

## 8. 通用安装脚本

### 8.1 安装脚本

```bash
#!/bin/bash
# install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Sisyphus"
VERSION="0.3.0"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检测发行版
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_VERSION=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
    else
        DISTRO="unknown"
    fi
    echo $DISTRO
}

# 检查依赖
check_dependencies() {
    log_info "Checking dependencies..."

    local missing=()

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi

    # 检查 curl
    if ! command -v curl &> /dev/null; then
        missing+=("curl")
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_warn "Missing dependencies: ${missing[*]}"
        log_info "Please install them first:"

        case $(detect_distro) in
            ubuntu|debian)
                echo "  sudo apt install ${missing[*]}"
                ;;
            fedora)
                echo "  sudo dnf install ${missing[*]}"
                ;;
            rhel|centos)
                echo "  sudo yum install ${missing[*]}"
                ;;
            arch|manjaro)
                echo "  sudo pacman -S ${missing[*]}"
                ;;
        esac
        exit 1
    fi

    log_info "All dependencies satisfied."
}

# 安装函数
install_app() {
    local install_dir="${INSTALL_DIR:-/opt/sisys}"

    log_info "Installing ${APP_NAME} ${VERSION} to ${install_dir}..."

    # 创建目录
    sudo mkdir -p "${install_dir}"
    sudo mkdir -p /etc/sisys
    sudo mkdir -p /var/lib/sisys
    sudo mkdir -p /var/log/sisys

    # 复制文件
    sudo cp -r "${SCRIPT_DIR}/dist/"* "${install_dir}/"
    sudo cp "${SCRIPT_DIR}/configs/default.yaml" /etc/sisys/

    # 创建符号链接
    sudo ln -sf "${install_dir}/sisys" /usr/local/bin/sisys

    # 设置权限
    sudo chmod 755 "${install_dir}/sisys"

    # 安装 systemd 服务
    if [ -f "${SCRIPT_DIR}/sisys.service" ]; then
        sudo cp "${SCRIPT_DIR}/sisys.service" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable sisys.service
        log_info "Systemd service installed."
    fi

    log_info "${APP_NAME} installed successfully!"
    log_info "Run 'sisys --help' to get started."
}

# 卸载函数
uninstall_app() {
    local install_dir="${INSTALL_DIR:-/opt/sisys}"

    log_info "Uninstalling ${APP_NAME}..."

    # 停止服务
    sudo systemctl stop sisys.service 2>/dev/null || true
    sudo systemctl disable sisys.service 2>/dev/null || true

    # 删除文件
    sudo rm -rf "${install_dir}"
    sudo rm -f /usr/local/bin/sisys
    sudo rm -f /etc/systemd/system/sisys.service

    # 询问是否删除配置
    read -p "Remove configuration files? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -rf /etc/sisys
        sudo rm -rf /var/lib/sisys
        sudo rm -rf /var/log/sisys
    fi

    sudo systemctl daemon-reload

    log_info "${APP_NAME} uninstalled."
}

# 主程序
main() {
    echo "================================"
    echo "  ${APP_NAME} Installer"
    echo "  Version: ${VERSION}"
    echo "================================"
    echo

    case "${1:-install}" in
        install)
            check_dependencies
            install_app
            ;;
        uninstall)
            uninstall_app
            ;;
        *)
            echo "Usage: $0 {install|uninstall}"
            exit 1
            ;;
    esac
}

main "$@"
```

---

## 9. 故障排查

### 9.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|-----|---------|---------|
| 依赖不满足 | 发行版版本过旧 | 升级系统或使用 AppImage |
| 服务无法启动 | 端口被占用 | `sudo lsof -i :PORT` 检查 |
| 权限错误 | 用户权限不足 | 检查文件所有者和权限 |
| systemd 服务失败 | 配置错误 | `journalctl -u sisys` 查看日志 |

### 9.2 诊断命令

```bash
# 检查安装
which sisys
sisys --version

# 检查服务状态
systemctl status sisys.service

# 查看日志
journalctl -u sisys.service -f
tail -f /var/log/sisys/app.log

# 检查依赖
ldd /opt/sisys/sisys
python3 -c "import sys; print(sys.path)"

# 检查端口
sudo lsof -i :8080
sudo netstat -tlnp | grep sisys

# 重新安装
sudo dpkg --reconfigure sisys  # DEB
sudo rpm --rebuild sisys.spec  # RPM
```

### 9.3 卸载脚本

```bash
#!/bin/bash
# uninstall.sh

set -e

echo "Uninstalling Sisyphus..."

# 停止服务
sudo systemctl stop sisys.service 2>/dev/null || true
sudo systemctl disable sisys.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/sisys.service
sudo systemctl daemon-reload

# 删除文件
sudo rm -rf /opt/sisys
sudo rm -f /usr/local/bin/sisys

# 删除配置（可选）
if [ "$1" == "--purge" ]; then
    sudo rm -rf /etc/sisys
    sudo rm -rf /var/lib/sisys
    sudo rm -rf /var/log/sisys
    echo "Configuration and data removed."
else
    echo "Configuration preserved in /etc/sisys"
fi

echo "Uninstallation complete."
```

---

## 附录：完整构建流程

```bash
#!/bin/bash
# build-all-linux.sh

set -e

VERSION="0.3.0"

echo "=== Linux Build Process ==="

# 1. 构建应用
echo "[1/6] Building application..."
cd ..
./build-linux.sh
cd installer

# 2. 构建 DEB
echo "[2/6] Building DEB package..."
./build-deb.sh

# 3. 构建 RPM
echo "[3/6] Building RPM package..."
./build-rpm.sh

# 4. 构建 AppImage
echo "[4/6] Building AppImage..."
./build-appimage.sh

# 5. 构建 Flatpak（可选）
echo "[5/6] Building Flatpak..."
./build-flatpak.sh || echo "Flatpak build skipped"

# 6. 构建 Snap（可选）
echo "[6/6] Building Snap..."
./build-snap.sh || echo "Snap build skipped"

echo ""
echo "=== Build Complete ==="
echo "Packages created:"
ls -la build-deb/*.deb
ls -la rpm-build/RPMS/x86_64/*.rpm
ls -la build/*.AppImage
ls -la *.flatpak 2>/dev/null || true
ls -la *.snap 2>/dev/null || true
```
