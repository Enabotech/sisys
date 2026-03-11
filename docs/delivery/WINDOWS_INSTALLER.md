# Windows 安装程序制作指南

本文档介绍如何为 Sisyphus 系统创建 Windows 安装程序。

## 目录

- [1. 概述](#1-概述)
- [2. 技术选型](#2-技术选型)
- [3. Inno Setup 配置](#3-inno-setup-配置)
- [4. NSIS 配置](#4-nsis-配置)
- [5. WiX Toolset 配置](#5-wix-toolset-配置)
- [6. 安装程序功能](#6-安装程序功能)
- [7. 代码签名](#7-代码签名)
- [8. 自动更新](#8-自动更新)
- [9. 故障排查](#9-故障排查)

---

## 1. 概述

Windows 安装程序需要支持以下功能：

- 一键安装，无需复杂配置
- 自动检测并安装依赖（Python、Node.js 等）
- 环境变量配置
- 服务注册（可选）
- 卸载支持
- 自动更新检查

---

## 2. 技术选型

| 工具 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| Inno Setup | 简单易用，脚本灵活 | 功能相对基础 | 中小型应用 |
| NSIS | 高度可定制，插件丰富 | 学习曲线陡峭 | 复杂安装逻辑 |
| WiX Toolset | MSI 标准，企业级 | 配置复杂 | 企业部署 |

**推荐**: Inno Setup（平衡易用性和功能）

---

## 3. Inno Setup 配置

### 3.1 安装脚本

```inno
; Sisyphus.iss
#define MyAppName "Sisyphus"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "Sisyphus Team"
#define MyAppURL "https://sisys.example.com"
#define MyAppExeName "sisys.exe"

[Setup]
; 基本设置
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 安装路径
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes

; 权限要求
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; 输出设置
OutputDir=Output
OutputBaseFilename=Sisyphus-Setup-{#MyAppVersion}
SetupIconFile=..\assets\sisys-icon.ico

; 压缩设置
Compression=lzma2
SolidCompression=yes
LZMAUseSeparateProcess=yes

; 日志
SetupLogging=yes
LogFilePath={log}\Sisyphus-Setup.log

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "installService"; Description: "安装为 Windows 服务"; GroupDescription: "服务选项"; Flags: unchecked
Name: "addToPath"; Description: "添加到系统 PATH"; GroupDescription: "环境变量"; Flags: checkedonce

[Files]
; 主程序
Source: "..\dist\sisys.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 配置文件
Source: "..\configs\default.yaml"; DestDir: "{app}\configs"; Flags: ignoreversion
Source: "..\configs\schema.json"; DestDir: "{app}\configs"; Flags: ignoreversion

; 文档
Source: "..\README.md"; DestDir: "{app}"; Flags: isreadme

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; 安装后运行
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; 安装服务（如果选择）
Filename: "{app}\sisys.exe"; Parameters: "service install"; Flags: runhidden; Tasks: installService

; 添加到 PATH
Filename: "{app}\{#MyAppExeName}"; Tasks: addToPath; Flags: skipifdoesnotexist

[Code]
// 自定义安装逻辑

// 检查是否已安装
function IsUpgrade(): Boolean;
var
  sPrevVersion: String;
begin
  Result := RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1', 'DisplayVersion', sPrevVersion);
  if Result then
    MsgBox('检测到已安装版本：' + sPrevVersion + #13#10 + '安装程序将进行升级安装。', mbInformation, MB_OK);
end;

// 检查 Python 是否已安装
function CheckPythonInstalled(): Boolean;
var
  sPythonPath: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore', 'InstallPath', sPythonPath);
  if not Result then
    Result := RegQueryStringValue(HKCU, 'SOFTWARE\Python\PythonCore', 'InstallPath', sPythonPath);
end;

// 下载并安装 Python（如果需要）
procedure InstallPython();
var
  ResultCode: Integer;
begin
  if not CheckPythonInstalled() then
  begin
    if MsgBox('未检测到 Python 环境。是否自动下载并安装 Python 3.12？', mbConfirmation, MB_YESNO) = idYes then
    begin
      // 下载 Python 安装程序
      DownloadFile('https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe',
                   ExpandConstant('{tmp}\python-installer.exe'));

      // 静默安装
      Exec(ExpandConstant('{tmp}\python-installer.exe'),
           '/quiet InstallAllUsers=1 PrependPath=1',
           '',
           SW_HIDE,
           ewWaitUntilTerminated,
           ResultCode);
    end;
  end;
end;

// 添加应用到 PATH
procedure AddToPath();
var
  PathValue: String;
begin
  // 读取当前 PATH
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', PathValue) then
    PathValue := '';

  // 添加应用目录
  if Pos(ExpandConstant('{app}'), PathValue) = 0 then
  begin
    if Length(PathValue) > 0 then
      PathValue := PathValue + ';';
    PathValue := PathValue + ExpandConstant('{app}');

    // 写入新 PATH
    RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', PathValue);

    // 通知系统环境变量已更改
    SendMessage(HWND_BROADCAST, WM_WININICHANGE, 0, 0);
  end;
end;

// 卸载时清理 PATH
procedure RemoveFromPath();
var
  PathValue: String;
  NewPathValue: String;
  PosStart: Integer;
begin
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', PathValue) then
  begin
    PosStart := Pos(ExpandConstant('{app}'), PathValue);
    if PosStart > 0 then
    begin
      // 移除应用路径
      NewPathValue := Copy(PathValue, 1, PosStart - 1);
      if PosStart + Length(ExpandConstant('{app}')) <= Length(PathValue) then
        NewPathValue := NewPathValue + Copy(PathValue, PosStart + Length(ExpandConstant('{app}')) + 1, Length(PathValue));

      // 清理多余的分号
      StringChangeEx(NewPathValue, ';;', ';', True);

      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPathValue);
      SendMessage(HWND_BROADCAST, WM_WININICHANGE, 0, 0);
    end;
  end;
end;

// 安装初始化
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addToPath') then
      AddToPath();
  end;
end;

// 卸载初始化
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RemoveFromPath();
  end;
end;

[UninstallDelete]
; 清理用户数据（可选）
; Type: filesandordirs; Name: "{userappdata}\Sisyphus"

[UninstallRun]
; 停止并移除服务
Filename: "{app}\sisys.exe"; Parameters: "service remove"; Flags: runhidden
```

### 3.2 构建脚本

```batch
@echo off
REM build-installer.bat

setlocal

REM 设置路径
set "INNO_PATH=C:\Program Files (x86)\Inno Setup 6"
set "OUTPUT_DIR=Output"

REM 清理旧输出
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"

REM 编译安装程序
echo Building installer...
"%INNO_PATH\ISCC.exe" /Q Sisyphus.iss

REM 验证输出
if exist "%OUTPUT_DIR%\Sisyphus-Setup-*.exe" (
    echo Build successful!
    dir "%OUTPUT_DIR%\*.exe"
) else (
    echo Build failed!
    exit /b 1
)

endlocal
```

### 3.3 多语言支持

```inno
[Messages]
; 自定义中文消息
chinesesimplified.BeveledLabel=Sisyphus 安装程序
chinesesimplified.SetupAppTitle=Sisyphus 安装
chinesesimplified.SetupWindowTitle=安装 Sisyphus
chinesesimplified.SelectDirLabel3=选择安装位置：
chinesesimplified.SelectDirBrowseLabel3=安装程序将安装到以下文件夹。
```

---

## 4. NSIS 配置

### 4.1 安装脚本

```nsis
; Sisyphus.nsi
!include "MUI2.nsh"
!include "x64.nsh"

; 基本设置
Name "Sisyphus"
OutFile "Output\Sisyphus-Setup-0.3.0.exe"
InstallDir "$PROGRAMFILES\Sisyphus"
InstallDirRegKey HKLM "Software\Sisyphus" ""
RequestExecutionLevel admin

; 界面设置
!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\sisys-icon.ico"
!define MUI_UNICON "..\assets\sisys-icon.ico"

; 页面
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; 语言
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"

; 节定义
Section "主程序" SecMain
  SectionIn RO

  SetOutPath "$INSTDIR"
  File /r "..\dist\*.*"

  SetOutPath "$INSTDIR\configs"
  File "..\configs\default.yaml"
  File "..\configs\schema.json"

  ; 创建卸载程序
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; 写入注册表
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sisyphus" "DisplayName" "Sisyphus"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sisyphus" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sisyphus" "DisplayVersion" "0.3.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sisyphus" "Publisher" "Sisyphus Team"
SectionEnd

Section "添加到 PATH" SecPath
  ; 添加安装目录到 PATH
  nsExec::ExecToLog 'setx PATH "%PATH%;$INSTDIR"'
SectionEnd

Section "创建快捷方式" SecShortcuts
  CreateDirectory "$SMPROGRAMS\Sisyphus"
  CreateShortcut "$SMPROGRAMS\Sisyphus\Sisyphus.lnk" "$INSTDIR\sisys.exe"
  CreateShortcut "$DESKTOP\Sisyphus.lnk" "$INSTDIR\sisys.exe"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; 卸载节
Section "Uninstall"
  ; 删除文件
  RMDir /r "$INSTDIR"

  ; 删除快捷方式
  Delete "$SMPROGRAMS\Sisyphus\Sisyphus.lnk"
  RMDir "$SMPROGRAMS\Sisyphus"
  Delete "$DESKTOP\Sisyphus.lnk"

  ; 删除注册表
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sisyphus"
SectionEnd
```

---

## 5. WiX Toolset 配置

### 5.1 WiX 项目文件

```xml
<!-- Product.wxs -->
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*"
           Name="Sisyphus"
           Language="1033"
           Version="0.3.0"
           Manufacturer="Sisyphus Team"
           UpgradeCode="A1B2C3D4-E5F6-7890-ABCD-EF1234567890">

    <Package InstallerVersion="500"
             Compressed="yes"
             InstallScope="perMachine"
             Description="Sisyphus Installation Package"/>

    <MajorUpgrade DowngradeErrorMessage="A newer version of Sisyphus is already installed."/>

    <MediaTemplate EmbedCab="yes"/>

    <Feature Id="ProductFeature" Title="Sisyphus" Level="1">
      <ComponentGroupRef Id="ProductComponents"/>
      <ComponentRef Id="ApplicationShortcut"/>
    </Feature>

    <!-- UI -->
    <UIRef Id="WixUI_Minimal"/>
    <WixVariable Id="WixUILicenseRtf" Value="..\LICENSE.rtf"/>
    <WixVariable Id="WixUIBannerBmp" Value="..\assets\banner.bmp"/>
    <WixVariable Id="WixUIDialogBmp" Value="..\assets\dialog.bmp"/>
  </Product>

  <Fragment>
    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFilesFolder">
        <Directory Id="INSTALLFOLDER" Name="Sisyphus"/>
      </Directory>
      <Directory Id="ProgramMenuFolder">
        <Directory Id="ApplicationProgramsFolder" Name="Sisyphus"/>
      </Directory>
    </Directory>
  </Fragment>

  <Fragment>
    <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
      <Component Id="MainExecutable" Guid="*">
        <File Id="sisys.exe" Source="..\dist\sisys.exe" KeyPath="yes"/>
        <File Id="configs" Source="..\configs\default.yaml"/>
      </Component>
    </ComponentGroup>

    <Component Id="ApplicationShortcut" Directory="ApplicationProgramsFolder">
      <Shortcut Id="ApplicationStartMenuShortcut"
                Name="Sisyphus"
                Description="Sisyphus Application"
                Target="[INSTALLFOLDER]sisys.exe"
                WorkingDirectory="INSTALLFOLDER"/>
      <RemoveFolder Id="ApplicationProgramsFolder" On="uninstall"/>
      <RegistryValue Root="HKCU"
                     Key="Software\Sisyphus"
                     Name="installed"
                     Type="integer"
                     Value="1"
                     KeyPath="yes"/>
    </Component>
  </Fragment>
</Wix>
```

### 5.2 构建命令

```batch
REM 构建 MSI
candle.exe -out obj\ Product.wxs
light.exe -out Output\Sisyphus-0.3.0.msi obj\Product.wixobj
```

---

## 6. 安装程序功能

### 6.1 依赖检测与安装

```inno
[Code]
// 检测并安装依赖

function CheckAndInstallDependencies(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  // 检查 Visual C++ Redistributable
  if not IsVCRedistInstalled() then
  begin
    Log('Installing Visual C++ Redistributable...');
    Exec(ExpandConstant('{tmp}\vc_redist.exe'), '/quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;

  // 检查 .NET Framework
  if not IsDotNetInstalled(48) then
  begin
    Log('Installing .NET Framework...');
    Exec(ExpandConstant('{tmp}\dotnet.exe'), '/quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
```

### 6.2 服务注册

```inno
[Code]
// 安装 Windows 服务

procedure InstallService();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{app}\sisys.exe'), 'service install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if ResultCode = 0 then
  begin
    // 启动服务
    Exec('sc.exe', 'start Sisyphus', '', SW_HIDE, ewNoWait, ResultCode);
    Log('Service installed and started successfully');
  end
  else
  begin
    Log('Failed to install service. Error code: ' + IntToStr(ResultCode));
  end;
end;
```

### 6.3 环境变量配置

```inno
[Code]
// 配置环境变量

procedure ConfigureEnvironmentVariables();
begin
  // 设置 SISYS_HOME
  RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'SISYS_HOME', ExpandConstant('{app}'));

  // 设置默认配置路径
  RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'SISYS_CONFIG', ExpandConstant('{userdocs}\Sisyphus\configs'));

  // 通知系统
  SendMessage(HWND_BROADCAST, WM_WININICHANGE, 0, 0);
end;
```

---

## 7. 代码签名

### 7.1 获取代码签名证书

```powershell
# 从证书颁发机构获取证书
# 或使用自签名证书（仅用于测试）

# 创建自签名证书
New-SelfSignedCertificate -Type CodeSigning `
  -Subject "CN=Sisyphus Team" `
  -KeyAlgorithm RSA `
  -KeyLength 2048 `
  -HashAlgorithm SHA256 `
  -CertStoreLocation "Cert:\CurrentUser\My" `
  -FriendlyName "Sisyphus Code Signing"
```

### 7.2 签名安装程序

```inno
[Setup]
; Inno Setup 签名配置
SignTool=SignTool
SignedUninstaller=yes

[Code]
// 或使用命令行签名
// signtool.exe sign /f certificate.pfx /p password /t http://timestamp.digicert.com installer.exe
```

```batch
REM 使用 signtool 签名
signtool sign /f SisyphusCert.pfx /p %CERT_PASSWORD% /tr http://timestamp.digicert.com /td sha256 /fd sha256 Output\Sisyphus-Setup-0.3.0.exe
```

---

## 8. 自动更新

### 8.1 更新检查配置

```python
# app/updater.py
import requests
import hashlib
from pathlib import Path

class Updater:
    def __init__(self):
        self.current_version = "0.3.0"
        self.update_server = "https://sisys.example.com"

    def check_for_updates(self) -> dict:
        """检查是否有新版本"""
        try:
            response = requests.get(
                f"{self.update_server}/api/v1/releases/latest",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def download_update(self, download_url: str, target_path: Path) -> bool:
        """下载更新文件"""
        try:
            response = requests.get(download_url, stream=True)
            response.raise_for_status()

            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            return False

    def verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """验证文件校验和"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest() == expected_checksum
```

### 8.2 安装程序内更新检查

```inno
[Code]
// 安装时检查更新

procedure CheckForUpdates();
var
  ResultCode: Integer;
begin
  // 调用更新检查 API
  if Exec(ExpandConstant('{app}\sisys.exe'), 'check-updates', '', SW_HIDE, ewNoWait, ResultCode) then
  begin
    Log('Update check initiated');
  end;
end;
```

---

## 9. 故障排查

### 9.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|-----|---------|---------|
| 安装失败，错误代码 5 | 权限不足 | 以管理员身份运行 |
| PATH 未更新 | 注册表写入失败 | 手动添加环境变量 |
| 服务无法启动 | 端口被占用 | 检查端口配置 |
| 杀毒软件拦截 | 误报 | 添加白名单 |

### 9.2 日志位置

```
安装日志：%TEMP%\Sisyphus-Setup.log
应用日志：%APPDATA%\Sisyphus\logs\
服务日志：%PROGRAMDATA%\Sisyphus\logs\
```

### 9.3 诊断命令

```powershell
# 检查安装状态
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* |
  Where-Object { $_.DisplayName -like "*Sisyphus*" }

# 检查服务状态
Get-Service Sisyphus

# 检查环境变量
[Environment]::GetEnvironmentVariable("Path", "User")

# 清理安装
& "$env:ProgramFiles\Sisyphus\uninstall.exe" /VERYSILENT
```

---

## 附录：完整构建流程

```batch
@echo off
REM build-all.bat - 完整构建流程

setlocal enabledelayedexpansion

echo === Sisyphus Windows Installer Build ===
echo.

REM 1. 清理
echo [1/5] Cleaning...
if exist "dist" rmdir /s /q dist
if exist "Output" rmdir /s /q Output
mkdir Output

REM 2. 构建应用
echo [2/5] Building application...
cd ..
call build-windows.bat
cd installer

REM 3. 验证输出
echo [3/5] Verifying build output...
if not exist "..\dist\sisys.exe" (
    echo ERROR: sisys.exe not found!
    exit /b 1
)

REM 4. 编译安装程序
echo [4/5] Compiling installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /Q Sisyphus.iss
if %ERRORLEVEL% neq 0 (
    echo ERROR: Installer compilation failed!
    exit /b 1
)

REM 5. 签名
echo [5/5] Signing installer...
signtool sign /f SisyphusCert.pfx /p %CERT_PASSWORD% /tr http://timestamp.digicert.com /td sha256 /fd sha256 "Output\Sisyphus-Setup-*.exe"

echo.
echo === Build Complete ===
dir Output\*.exe

endlocal
```
