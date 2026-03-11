# macOS 安装程序制作指南

本文档介绍如何为 Sisyphus 系统创建 macOS 安装程序。

## 目录

- [1. 概述](#1-概述)
- [2. 技术选型](#2-技术选型)
- [3. DMG 安装盘制作](#3-dmg-安装盘制作)
- [4. PKG 安装包制作](#4-pkg-安装包制作)
- [5. Homebrew 分发](#5-homebrew-分发)
- [6. 代码签名与公证](#6-代码签名与公证)
- [7. 自动更新](#7-自动更新)
- [8. 故障排查](#8-故障排查)

---

## 1. 概述

macOS 安装程序需要支持：

- DMG 拖拽安装
- PKG 向导式安装
- 代码签名和公证（Notarization）
- Apple Silicon (M1/M2) 和 Intel 双架构支持
- 自动更新机制
- 卸载支持

---

## 2. 技术选型

| 格式 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| DMG | 用户熟悉，拖拽安装 | 无权限控制 | 个人/开发者应用 |
| PKG | 系统级安装，权限控制 | 制作复杂 | 企业部署 |
| Homebrew | 开发者友好 | 需要审核 | 开源工具 |

**推荐**: 同时提供 DMG 和 PKG

---

## 3. DMG 安装盘制作

### 3.1 使用 create-dmg

```bash
# 安装 create-dmg
npm install -g create-dmg

# 或使用 Homebrew
brew install create-dmg
```

### 3.2 构建脚本

```bash
#!/bin/bash
# build-dmg.sh

set -e

APP_NAME="Sisyphus"
VERSION="0.3.0"
BUILD_DIR="build"
DIST_DIR="dist"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

echo "=== Building DMG for ${APP_NAME} ==="

# 清理
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# 复制应用
cp -r "${DIST_DIR}/Sisyphus.app" "${BUILD_DIR}/"

# 创建 DMG
create-dmg \
  --volname "${APP_NAME}" \
  --volicon "assets/sisys-icon.icns" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "Sisyphus.app" 180 180 \
  --app-drop-link 420 180 \
  --hide-extension "Sisyphus.app" \
  --background "assets/dmg-background.png" \
  --format UDZO \
  --compression-level 9 \
  "${BUILD_DIR}/${DMG_NAME}" \
  "${BUILD_DIR}/Sisyphus.app"

echo "DMG created: ${BUILD_DIR}/${DMG_NAME}"

# 计算校验和
shasum -a 256 "${BUILD_DIR}/${DMG_NAME}" > "${BUILD_DIR}/${DMG_NAME}.sha256"
```

### 3.3 自定义 DMG 背景

```bash
#!/bin/bash
# create-dmg-background.sh

# 创建 600x400 的背景图
mkdir -p assets

# 使用 Python 创建背景
python3 << 'EOF'
from PIL import Image, ImageDraw, ImageFont

# 创建背景
img = Image.new('RGB', (600, 400), color='#f0f0f0')
draw = ImageDraw.Draw(img)

# 添加渐变
for y in range(400):
    r = int(240 + (15 * y / 400))
    g = int(240 + (15 * y / 400))
    b = int(245 + (10 * y / 400))
    draw.line([(0, y), (600, y)], fill=(r, g, b))

# 添加文字
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Helvetica.ttc", 24)
except:
    font = ImageFont.load_default()

draw.text((200, 350), "Drag to Applications", fill=(100, 100, 100), font=font)

img.save('assets/dmg-background.png')
print("Background created successfully")
EOF
```

### 3.4 手动创建 DMG

```bash
#!/bin/bash
# build-dmg-manual.sh

APP_NAME="Sisyphus"
VERSION="0.3.0"

# 创建临时目录
mkdir -p dmg-root
cp -r "dist/${APP_NAME}.app" "dmg-root/"

# 创建符号链接到 Applications
ln -s /Applications dmg-root/Applications

# 创建 DMG
hdiutil create -volname "${APP_NAME}" \
  -srcfolder dmg-root \
  -ov -format UDZO \
  "${APP_NAME}-${VERSION}.dmg"

# 清理
rm -rf dmg-root
```

---

## 4. PKG 安装包制作

### 4.1 目录结构

```
pkg-root/
├── scripts/
│   ├── preinstall
│   ├── postinstall
│   └── uninstall
└── payload/
    └── Sisyphus.app/
```

### 4.2 安装脚本

```bash
#!/bin/bash
# pkg-root/scripts/preinstall

#!/bin/sh
# 预安装检查

# 检查 macOS 版本
OS_VERSION=$(sw_vers -productVersion)
REQUIRED_VERSION="11.0"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$OS_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: macOS $REQUIRED_VERSION or later required."
    exit 1
fi

# 检查磁盘空间
FREE_SPACE=$(df -k / | tail -1 | awk '{print $4}')
REQUIRED_SPACE=524288  # 512MB

if [ "$FREE_SPACE" -lt "$REQUIRED_SPACE" ]; then
    echo "Error: Insufficient disk space."
    exit 1
fi

exit 0
```

```bash
#!/bin/bash
# pkg-root/scripts/postinstall

#!/bin/sh
# 后安装配置

APP_NAME="Sisyphus"
INSTALL_DIR="/Applications/${APP_NAME}.app"

# 设置权限
chmod -R 755 "${INSTALL_DIR}"
chown -R root:wheel "${INSTALL_DIR}"

# 注册 LaunchAgent
LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.sisyphus.app.plist"
mkdir -p "$(dirname "${LAUNCH_AGENT}")"
cat > "${LAUNCH_AGENT}" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sisyphus.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/Contents/MacOS/sisys</string>
        <string>--background</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/sisyphus.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sisyphus.err</string>
</dict>
</plist>
EOF

# 加载 LaunchAgent
launchctl load "${LAUNCH_AGENT}"

# 添加到 Spotlight 索引
mdimport "${INSTALL_DIR}"

echo "Installation completed successfully."
exit 0
```

### 4.3 创建 PKG

```bash
#!/bin/bash
# build-pkg.sh

set -e

APP_NAME="Sisyphus"
VERSION="0.3.0"
IDENTIFIER="com.sisyphus.app"

# 创建 payload
mkdir -p pkg-root/payload
cp -r "dist/${APP_NAME}.app" "pkg-root/payload/"

# 复制脚本
mkdir -p pkg-root/scripts
cp scripts/preinstall pkg-root/scripts/
cp scripts/postinstall pkg-root/scripts/
chmod +x pkg-root/scripts/*

# 构建 pkg
pkgbuild \
  --root pkg-root/payload \
  --scripts pkg-root/scripts \
  --identifier "${IDENTIFIER}" \
  --version "${VERSION}" \
  --install-location "/Applications" \
  "build/${APP_NAME}-${VERSION}.pkg"

# 或使用 productbuild 创建带许可证的安装包
productbuild \
  --distribution distribution.xml \
  --resources resources \
  --package-path build \
  "build/${APP_NAME}-${VERSION}-installer.pkg"
```

### 4.4 分布配置文件

```xml
<!-- distribution.xml -->
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Sisyphus</title>
    <organization>com.sisyphus</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="true" allow-external-scripts="no"/>

    <welcome file="welcome.html" mime-type="text/html"/>
    <license file="license.html" mime-type="text/html"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>

    <installation-check script="system.compareVersions(system.version.ProductVersion, '11.0') >= 0;"/>

    <volume-check>
        <allowed-volume-types>
            <volume type="local"/>
        </allowed-volume-types>
    </volume-check>

    <choices-outline>
        <line choice="default">
            <line choice="com.sisyphus.app"/>
        </line>
    </choices-outline>

    <choice id="default"/>
    <choice id="com.sisyphus.app" visible="false">
        <pkg-ref id="com.sisyphus.app"/>
    </choice>

    <pkg-ref id="com.sisyphus.app" version="0.3.0" onConclusion="none">
        Sisyphus-0.3.0.pkg
    </pkg-ref>
</installer-gui-script>
```

---

## 5. Homebrew 分发

### 5.1 创建 Homebrew Tap

```bash
# 创建仓库
# GitHub: homebrew-sisyphus

# 目录结构
homebrew-sisyphus/
├── Formula/
│   └── sisys.rb
└── README.md
```

### 5.2 Formula 配置

```ruby
# Formula/sisys.rb
class Sisys < Formula
  desc "Sisyphus - Intelligent Development Assistant"
  homepage "https://sisys.example.com"
  url "https://github.com/sisyphus/sisys/releases/download/v0.3.0/sisys-0.3.0-macos.tar.gz"
  sha256 "abc123def456..."  # 使用实际校验和
  license "MIT"

  version "0.3.0"

  depends_on "python@3.12"
  depends_on "node" => :optional

  def install
    # 安装主程序
    libexec.install Dir["*"]

    # 创建可执行文件
    bin.install_symlink "#{libexec}/sisys" => "sisys"

    # 安装配置文件
    etc.install "configs/default.yaml" => "sisys/default.yaml"
  end

  def caveats
    <<~EOS
      To configure Sisyphus, edit:
        #{etc}/sisys/default.yaml

      To start the service:
        brew services start sisys
    EOS
  end

  service do
    run [opt_bin/"sisys", "--background"]
    keep_alive true
    log_path var/"log/sisys.log"
    error_log_path var/"log/sisys.err"
  end

  test do
    system "#{bin}/sisys", "--version"
  end
end
```

### 5.2 发布到 Homebrew

```bash
# 添加 Tap
brew tap sisyphus/homebrew-sisyphus

# 测试安装
brew install --build-from-source sisys

# 验证
brew test sisys

# 发布后用户可安装
brew install sisyphus/homebrew-sisyphus/sisys
```

---

## 6. 代码签名与公证

### 6.1 获取开发者证书

```bash
# 列出可用证书
security find-identity -v -s "Developer ID Application"

# 或使用 Xcode 自动管理
# Xcode -> Preferences -> Accounts -> 添加 Apple ID
```

### 6.2 签名应用

```bash
#!/bin/bash
# sign-app.sh

APP_NAME="Sisyphus"
CERT_NAME="Developer ID Application: Your Name (TEAM_ID)"
ENTITLEMENTS="entitlements.plist"

# 签名应用
codesign --force --options runtime \
  --entitlements "${ENTITLEMENTS}" \
  --sign "${CERT_NAME}" \
  --timestamp \
  "dist/${APP_NAME}.app/Contents/MacOS/sisys"

codesign --force --options runtime \
  --entitlements "${ENTITLEMENTS}" \
  --sign "${CERT_NAME}" \
  --timestamp \
  "dist/${APP_NAME}.app"

# 验证签名
codesign --verify --verbose "dist/${APP_NAME}.app"
```

### 6.3 权限文件

```xml
<!-- entitlements.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- 允许访问网络 -->
    <key>com.apple.security.network.client</key>
    <true/>

    <!-- 允许访问文件系统 -->
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>

    <!-- 允许运行无签名代码（如果需要） -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>

    <!-- 允许 JIT 编译（如果需要） -->
    <key>com.apple.security.cs.allow-jit</key>
    <true/>

    <!-- 禁用库验证（仅调试） -->
    <!-- <key>com.apple.security.cs.disable-library-validation</key> -->
    <!-- <true/> -->
</dict>
</plist>
```

### 6.4 公证应用

```bash
#!/bin/bash
# notarize-app.sh

APP_NAME="Sisyphus"
VERSION="0.3.0"
TEAM_ID="YOUR_TEAM_ID"
APPLE_ID="your.apple.id@example.com"
APP_PASSWORD="your-app-specific-password"

# 创建 ZIP 用于上传
ditto -c -k --keepParent "dist/${APP_NAME}.app" "dist/${APP_NAME}.app.zip"

# 提交公证
xcrun notarytool submit "dist/${APP_NAME}.app.zip" \
  --apple-id "${APPLE_ID}" \
  --password "${APP_PASSWORD}" \
  --team-id "${TEAM_ID}" \
  --wait

# 附加公证票
xcrun stapler staple "dist/${APP_NAME}.app"

# 验证
spctl --assess -vv "dist/${APP_NAME}.app"
```

### 6.5 公证 DMG

```bash
#!/bin/bash
# notarize-dmg.sh

DMG_FILE="build/Sisyphus-0.3.0.dmg"
TEAM_ID="YOUR_TEAM_ID"
APPLE_ID="your.apple.id@example.com"
APP_PASSWORD="your-app-specific-password"

# 提交 DMG 公证
xcrun notarytool submit "${DMG_FILE}" \
  --apple-id "${APPLE_ID}" \
  --password "${APP_PASSWORD}" \
  --team-id "${TEAM_ID}" \
  --wait

# 附加公证票
xcrun stapler staple "${DMG_FILE}"

# 验证
spctl --assess -vv "${DMG_FILE}"
```

---

## 7. 自动更新

### 7.1 Sparkle 框架集成

```swift
// AppDelegate.swift
import Sparkle

class AppDelegate: NSObject, NSApplicationDelegate {
    var updaterController: SPUStandardUpdaterController!

    func applicationDidFinishLaunching(_ notification: Notification) {
        // 初始化 Sparkle
        updaterController = SPUStandardUpdaterController(
            startingUpdater: true,
            updaterDelegate: self,
            userDriverDelegate: nil
        )
    }
}

extension AppDelegate: SPUUpdaterDelegate {
    func feedURLString(for updater: SPUUpdater) -> String? {
        return "https://sisys.example.com/updates/appcast.xml"
    }
}
```

### 7.2 Appcast 配置

```xml
<!-- appcast.xml -->
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
    <channel>
        <title>Sisyphus Updates</title>
        <link>https://sisys.example.com/updates/appcast.xml</link>
        <description>Most recent changes to Sisyphus</description>
        <language>en</language>

        <item>
            <title>Version 0.3.0</title>
            <description>
                <![CDATA[
                <ul>
                    <li>新增 K3S 集群支持</li>
                    <li>优化 Harbor 镜像管理</li>
                    <li>改进 ArgoCD 部署流程</li>
                    <li>修复多个已知问题</li>
                </ul>
                ]]>
            </description>
            <pubDate>Wed, 11 Mar 2026 12:00:00 +0800</pubDate>
            <releaseNotesLink>https://sisys.example.com/releases/0.3.0/notes.html</releaseNotesLink>
            <sparkle:minimumSystemVersion>11.0</sparkle:minimumSystemVersion>
            <sparkle:installerArguments>
                <argument>-apply</argument>
            </sparkle:installerArguments>

            <enclosure url="https://sisys.example.com/releases/0.3.0/Sisyphus-0.3.0.dmg"
                       sparkle:version="300"
                       sparkle:shortVersionString="0.3.0"
                       sparkle:osVersion="11.0"
                       length="52428800"
                       type="application/octet-stream"
                       sparkle:edSignature="abc123..."/>
        </item>
    </channel>
</rss>
```

### 7.3 生成 EdDSA 签名

```bash
# 生成密钥对
./generate_keys

# 签名 Appcast
./sign_update Sisyphus-0.3.0.dmg -o appcast.xml
```

---

## 8. 故障排查

### 8.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|-----|---------|---------|
| "应用已损坏" | 未公证或签名无效 | 重新公证应用 |
| 无法打开 | Gatekeeper 阻止 | 系统设置 -> 隐私与安全性 -> 仍要打开 |
| 安装失败 | 权限不足 | 使用 sudo 或 PKG 安装 |
| 更新失败 | 签名不匹配 | 确保使用相同证书签名 |

### 8.2 诊断命令

```bash
# 检查签名
codesign --verify --verbose /Applications/Sisyphus.app

# 检查公证状态
spctl --assess -vv /Applications/Sisyphus.app

# 查看 Gatekeeper 状态
spctl --status

# 临时禁用 Gatekeeper（仅测试）
sudo spctl --master-disable

# 重新启用
sudo spctl --master-enable

# 查看安装日志
log show --predicate 'process == "installer"' --last 1h

# 清理 LaunchAgent
launchctl remove com.sisyphus.app
rm ~/Library/LaunchAgents/com.sisyphus.app.plist
```

### 8.3 卸载脚本

```bash
#!/bin/bash
# uninstall.sh

APP_NAME="Sisyphus"
INSTALL_DIR="/Applications/${APP_NAME}.app"

echo "卸载 ${APP_NAME}..."

# 停止服务
launchctl remove com.sisyphus.app 2>/dev/null || true

# 删除应用
rm -rf "${INSTALL_DIR}"

# 删除配置文件
rm -rf ~/Library/Application\ Support/Sisyphus
rm -rf ~/Library/Preferences/com.sisyphus.app.plist
rm -rf ~/Library/Caches/com.sisyphus.app

# 删除 LaunchAgent
rm ~/Library/LaunchAgents/com.sisyphus.app.plist

# 删除日志
rm -rf /tmp/sisyphus.*

echo "卸载完成。"
```

---

## 附录：完整构建流程

```bash
#!/bin/bash
# build-all-macos.sh

set -e

APP_NAME="Sisyphus"
VERSION="0.3.0"
TEAM_ID="YOUR_TEAM_ID"
APPLE_ID="your.apple.id@example.com"

echo "=== macOS Build Process ==="

# 1. 构建应用
echo "[1/5] Building application..."
cd ..
./build-macos.sh
cd installer

# 2. 签名
echo "[2/5] Code signing..."
./sign-app.sh

# 3. 创建 DMG
echo "[3/5] Creating DMG..."
./build-dmg.sh

# 4. 创建 PKG
echo "[4/5] Creating PKG..."
./build-pkg.sh

# 5. 公证
echo "[5/5] Notarizing..."
./notarize-dmg.sh

echo ""
echo "=== Build Complete ==="
ls -la build/
```
