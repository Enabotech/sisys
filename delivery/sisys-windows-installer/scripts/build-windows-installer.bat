@echo off
REM ============================================================================
REM SISYS Windows 安装包构建脚本
REM 功能：编译 Inno Setup 脚本生成安装包
REM ============================================================================

setlocal enabledelayedexpansion

echo ================================================================================
echo SISYS Windows Installer Build
echo ================================================================================
echo.

REM 设置路径
set "INNO_PATH=C:\Program Files (x86)\Inno Setup 6"
set "SCRIPT_DIR=%~dp0"
set "OUTPUT_DIR=%SCRIPT_DIR%Output"

REM 检查 Inno Setup 是否已安装
if not exist "%INNO_PATH%\ISCC.exe" (
    echo ❌ 错误: Inno Setup 6 未安装
    echo.
    echo 💡 请下载并安装 Inno Setup 6:
    echo    https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 1
)

REM 清理旧输出
if exist "%OUTPUT_DIR%" (
    echo 🗑️  清理旧构建输出...
    rmdir /s /q "%OUTPUT_DIR%"
)
mkdir "%OUTPUT_DIR%"

REM 检查源文件是否存在
echo 🔍 检查源文件...
if not exist "%SCRIPT_DIR%installer\Sisys.iss" (
    echo ❌ 错误: Inno Setup 脚本不存在
    exit /b 1
)

if not exist "%SCRIPT_DIR%configs\docker-compose.yml" (
    echo ❌ 错误: docker-compose.yml 不存在
    exit /b 1
)

if not exist "%SCRIPT_DIR%scripts\check-docker.ps1" (
    echo ❌ 错误: check-docker.ps1 不存在
    exit /b 1
)

echo ✅ 源文件检查通过
echo.

REM 编译安装程序
echo 🔨 编译安装包...
"%INNO_PATH%\ISCC.exe" "%SCRIPT_DIR%installer\Sisys.iss"

if %ERRORLEVEL% neq 0 (
    echo ❌ 错误: 安装包编译失败
    exit /b 1
)

REM 验证输出
echo.
echo 📦 验证构建输出...
if exist "%OUTPUT_DIR%\SISYS-Setup-*.exe" (
    echo ✅ 构建成功!
    echo.

    REM 显示文件大小
    for %%F in ("%OUTPUT_DIR%\SISYS-Setup-*.exe") do (
        set "FILE_SIZE=%%~zF"
        set /a "FILE_MB=!FILE_SIZE!/1048576"
        echo 📊 安装包大小: !FILE_MB! MB
    )

    echo.
    echo 📁 输出目录: %OUTPUT_DIR%
    dir "%OUTPUT_DIR%\*.exe"
    echo.

    echo ================================================================================
    echo ✅ 构建完成！
    echo ================================================================================
    echo.
    echo 💡 下一步:
    echo    1. 测试安装包: 运行 Output\SISYS-Setup-*.exe
    echo    2. 验证安装流程
    echo    3. 发布到下载服务器
    echo.
) else (
    echo ❌ 错误: 未找到输出文件
    exit /b 1
)

endlocal
