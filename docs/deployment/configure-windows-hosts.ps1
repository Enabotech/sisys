# Gitea Windows 访问配置脚本
# 用途：在 Windows 上配置 hosts 文件以访问 WSL2 中的 Gitea

# 以管理员身份运行此脚本

$WSL2_IP = "172.21.110.12"
$HOSTS_FILE = "C:\Windows\System32\drivers\etc\hosts"
$HOST_ENTRY = "$WSL2_IP gitea.sisys.local"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Gitea Windows 访问配置" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "错误：需要管理员权限" -ForegroundColor Red
    Write-Host "请右键点击此脚本，选择'以管理员身份运行'" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}

Write-Host "✓ 管理员权限确认" -ForegroundColor Green
Write-Host ""

# 检查 hosts 文件是否存在
if (-not (Test-Path $HOSTS_FILE)) {
    Write-Host "错误：找不到 hosts 文件：$HOSTS_FILE" -ForegroundColor Red
    exit 1
}

Write-Host "✓ hosts 文件存在：$HOSTS_FILE" -ForegroundColor Green
Write-Host ""

# 检查是否已存在该条目
$hostsContent = Get-Content $HOSTS_FILE -Raw
if ($hostsContent -match [regex]::Escape($HOST_ENTRY)) {
    Write-Host "ℹ hosts 条目已存在：" -ForegroundColor Yellow
    Write-Host "  $HOST_ENTRY" -ForegroundColor Gray
    Write-Host ""
} else {
    # 添加条目
    Write-Host "正在添加 hosts 条目..." -ForegroundColor Cyan

    # 检查是否有末尾换行
    if (-not $hostsContent.EndsWith("`n")) {
        $hostsContent += "`n"
    }

    $hostsContent += "# Gitea (WSL2) - Added by setup script on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"
    $hostsContent += "$HOST_ENTRY`n"

    # 保存文件
    try {
        Set-Content -Path $HOSTS_FILE -Value $hostsContent -NoNewline -Force
        Write-Host "✓ hosts 条目添加成功" -ForegroundColor Green
        Write-Host ""
    } catch {
        Write-Host "错误：无法写入 hosts 文件" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Gray
        exit 1
    }
}

# 验证配置
Write-Host "正在验证配置..." -ForegroundColor Cyan
try {
    $pingResult = Test-Connection -ComputerName "gitea.sisys.local" -Count 1 -Quiet
    if ($pingResult) {
        Write-Host "✓ DNS 解析成功" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "⚠ DNS 解析失败，可能需要刷新 DNS 缓存" -ForegroundColor Yellow
        Write-Host ""

        # 刷新 DNS
        Write-Host "正在刷新 DNS 缓存..." -ForegroundColor Cyan
        Invoke-Expression "ipconfig /flushdns" | Out-Null
        Write-Host "✓ DNS 缓存已刷新" -ForegroundColor Green
        Write-Host ""
    }
} catch {
    Write-Host "⚠ 验证失败，但配置可能已生效" -ForegroundColor Yellow
    Write-Host ""
}

# 显示访问信息
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "配置完成！" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "现在可以在浏览器中访问 Gitea：" -ForegroundColor White
Write-Host ""
Write-Host "  HTTP:  http://gitea.sisys.local:30580" -ForegroundColor Cyan
Write-Host "  HTTPS: https://gitea.sisys.local:31448" -ForegroundColor Cyan
Write-Host ""
Write-Host "管理员登录信息：" -ForegroundColor White
Write-Host "  用户名：gitea_admin" -ForegroundColor Gray
Write-Host "  密码：Admin@123456" -ForegroundColor Gray
Write-Host ""
Write-Host "按 Enter 键退出..." -ForegroundColor Gray
Read-Host
