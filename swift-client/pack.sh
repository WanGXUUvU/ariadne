#!/bin/bash
set -e

# 1. 确保最新编译
echo "正在编译项目..."
swift build -c release

# 2. 创建标准的 .app 目录结构
APP_NAME="AriadneClient.app"
MACOS_DIR="$APP_NAME/Contents/MacOS"
RESOURCES_DIR="$APP_NAME/Contents/Resources"

echo "创建应用包结构..."
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# 3. 复制编译好的 Release 二进制文件
cp .build/release/AriadneClient "$MACOS_DIR/AriadneClient"

# 4. 生成 Info.plist 配置文件
cat > "$APP_NAME/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AriadneClient</string>
    <key>CFBundleIdentifier</key>
    <string>com.ariadne.client</string>
    <key>CFBundleName</key>
    <string>AriadneClient</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>26.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF

codesign --force --deep --sign - "$APP_NAME" >/dev/null

echo "打包成功！已生成: $APP_NAME"
echo "你可以直接双击运行它，或者运行 'open $APP_NAME'。"
