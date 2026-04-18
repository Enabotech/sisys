# ============================================================================
# 端口配置脚本
# 功能：检测端口占用情况并自动选择可用端口
# ============================================================================

param(
    [int]$DefaultPort = 8080,
    [int]$DefaultHttpsPort = 443,
    [string]$EnvFile = ".env"
)

function Test-PortInUse {
    <#
    .SYNOPSIS
        检测端口是否被占用

    .PARAMETER Port
        要检测的端口号

    .OUTPUTS
        Boolean - True 表示端口被占用，False 表示端口空闲
    #>
    param(
        [int]$Port
    )

    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $false  # 端口空闲
    } catch {
        return $true   # 端口被占用
    }
}

function Find-AvailablePort {
    <#
    .SYNOPSIS
        查找可用端口

    .PARAMETER StartPort
        起始端口号

    .PARAMETER MaxAttempts
        最大尝试次数

    .OUTPUTS
        int - 可用端口号
    #>
    param(
        [int]$StartPort,
        [int]$MaxAttempts = 20
    )

    $port = $StartPort
    $attempts = 0

    while ($attempts -lt $MaxAttempts) {
        if (-not (Test-PortInUse -Port $port)) {
            return $port
        }

        $port++
        $attempts++
    }

    # 如果默认范围都不可用，返回 -1
    return -1
}

function Update-EnvFile {
    <#
    .SYNOPSIS
        更新 .env 文件中的端口配置

    .PARAMETER EnvFilePath
        .env 文件路径

    .PARAMETER Port
        新端口号
    #>
    param(
        [string]$EnvFilePath,
        [int]$Port
    )

    if (Test-Path $EnvFilePath) {
        $content = Get-Content $EnvFilePath -Raw
        $content = $content -replace "SISYS_PORT=\d+", "SISYS_PORT=$Port"
        $content | Set-Content $EnvFilePath -NoNewline
        Write-Host "✅ 已更新 .env 文件中的端口配置为 $Port" -ForegroundColor Green
    } else {
        Write-Host "⚠️  .env 文件不存在，创建新文件" -ForegroundColor Yellow
        "SISYS_PORT=$Port" | Set-Content $EnvFilePath -NoNewline
    }
}

# ============================================================================
# 主逻辑
# ============================================================================

Write-Host "🔍 正在检测端口占用情况..." -ForegroundColor Cyan
Write-Host ""

# 检测默认端口
$httpPortInUse = Test-PortInUse -Port $DefaultPort
$httpsPortInUse = Test-PortInUse -Port $DefaultHttpsPort

if ($httpPortInUse) {
    Write-Host "⚠️  端口 $DefaultPort 已被占用" -ForegroundColor Yellow

    # 查找可用端口
    $availablePort = Find-AvailablePort -StartPort ($DefaultPort + 1)

    if ($availablePort -gt 0) {
        Write-Host "✅ 自动选择可用端口: $availablePort" -ForegroundColor Green
        Write-Host ""

        # 更新 .env 文件
        $envPath = Join-Path $PSScriptRoot "..\configs\$EnvFile"
        Update-EnvFile -EnvFilePath $envPath -Port $availablePort
    } else {
        Write-Host "❌ 无法找到可用端口，请手动配置" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ 端口 $DefaultPort 可用" -ForegroundColor Green
}

if ($httpsPortInUse) {
    Write-Host "⚠️  端口 $DefaultHttpsPort 已被占用" -ForegroundColor Yellow
} else {
    Write-Host "✅ 端口 $DefaultHttpsPort 可用" -ForegroundColor Green
}

Write-Host ""
Write-Host "📊 端口状态总结:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host "HTTP 端口: $DefaultPort $(if ($httpPortInUse) { '(已占用)' } else { '(可用)' })"
Write-Host "HTTPS 端口: $DefaultHttpsPort $(if ($httpsPortInUse) { '(已占用)' } else { '(可用)' })"
Write-Host ""

exit 0
