# ============================================================================
# 服务启动脚本
# 功能：启动 SISYS 服务并验证健康状态
# ============================================================================

param(
    [string]$ComposeFile = "docker-compose.yml",
    [int]$HealthCheckPort = 0,  # 修复 C7: 0 表示从.env 读取
    [int]$MaxRetries = 24,  # 修复 C5: 从 10 增加到 24（2 分钟）
    [int]$RetryDelay = 5
)

function Start-SISYSServices {
    <#
    .SYNOPSIS
        启动 SISYS 服务

    .DESCRIPTION
        使用 Docker Compose 启动所有服务
    #>

    Write-Host "🚀 正在启动 SISYS 服务..." -ForegroundColor Cyan

    $composePath = Join-Path $PSScriptRoot "..\configs\$ComposeFile"

    if (-not (Test-Path $composePath)) {
        Write-Host "❌ docker-compose.yml 文件不存在: $composePath" -ForegroundColor Red
        return $false
    }

    # 切换到配置目录
    Push-Location (Split-Path $composePath)

    try {
        # 启动服务
        docker compose up -d

        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ 服务启动失败" -ForegroundColor Red
            Write-Host "查看日志: docker compose logs" -ForegroundColor Yellow
            return $false
        }

        Write-Host "✅ 服务启动命令已发送" -ForegroundColor Green
        return $true
    } finally {
        Pop-Location
    }
}

function Test-ServiceHealth {
    <#
    .SYNOPSIS
        验证服务健康状态

    .DESCRIPTION
        通过 HTTP 健康检查端点验证服务是否正常启动
    #>

    Write-Host "🏥 正在验证服务健康..." -ForegroundColor Cyan

    $healthUrl = "http://localhost:$HealthCheckPort/health"
    $retryCount = 0

    while ($retryCount -lt $MaxRetries) {
        $retryCount++

        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5

            if ($response.StatusCode -eq 200) {
                Write-Host "✅ 服务健康检查通过" -ForegroundColor Green
                Write-Host "   URL: $healthUrl" -ForegroundColor Gray
                Write-Host "   响应: $($response.Content)" -ForegroundColor Gray
                return $true
            }
        } catch {
            Write-Host "⏳ 第 $retryCount/$MaxRetries 次尝试..." -ForegroundColor Yellow
            Start-Sleep -Seconds $RetryDelay
        }
    }

    Write-Host "❌ 服务健康检查失败（已尝试 $MaxRetries 次）" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 故障排查建议:" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "1. 查看服务状态: docker compose ps"
    Write-Host "2. 查看服务日志: docker compose logs -f"
    Write-Host "3. 检查磁盘空间: Get-PSDrive C"
    Write-Host "4. 重新启动服务: docker compose down && docker compose up -d"
    Write-Host ""

    return $false
}

function Show-ServiceStatus {
    <#
    .SYNOPSIS
        显示服务状态信息
    #>

    Write-Host ""
    Write-Host "📊 SISYS 服务状态" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

    try {
        $services = docker compose ps --format json 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host "服务列表:" -ForegroundColor Green

            # 解析并显示服务信息
            $services | ForEach-Object {
                Write-Host "  $_" -ForegroundColor Gray
            }
        } else {
            Write-Host "⚠️  无法获取服务状态" -ForegroundColor Yellow
            Write-Host "手动查看: docker compose ps" -ForegroundColor Gray
        }
    } catch {
        Write-Host "⚠️  服务状态检查失败" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "🌐 访问地址:" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "SISYS 欢迎页面: http://localhost:$HealthCheckPort/welcome"
    Write-Host "SISYS 登录页面: http://localhost:$HealthCheckPort/login"
    Write-Host "健康检查端点: http://localhost:$HealthCheckPort/health"
    Write-Host ""
}

# ============================================================================
# 主逻辑
# ============================================================================

Write-Host "🎯 SISYS 服务启动脚本" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# 修复 C7: 从 .env 读取实际端口
if ($HealthCheckPort -eq 0) {
    $envPath = Join-Path $PSScriptRoot "..\.env"
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath
        $portMatch = $envContent | Where-Object { $_ -match "^SISYS_PORT=(\d+)" }
        if ($portMatch) {
            $HealthCheckPort = ($portMatch -split "=")[1] -as [int]
            Write-Host "📌 从 .env 读取端口: $HealthCheckPort" -ForegroundColor Green
        } else {
            $HealthCheckPort = 8080
            Write-Host "⚠️  .env 中未找到 SISYS_PORT，使用默认值 8080" -ForegroundColor Yellow
        }
    } else {
        $HealthCheckPort = 8080
        Write-Host "⚠️  .env 文件不存在，使用默认端口 8080" -ForegroundColor Yellow
    }
}

# 启动服务
$started = Start-SISYSServices

if ($started) {
    # 等待服务启动
    Write-Host ""
    Write-Host "⏳ 等待服务启动..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10

    # 验证健康状态
    $healthy = Test-ServiceHealth

    if ($healthy) {
        # 显示服务状态
        Show-ServiceStatus

        Write-Host "🎉 SISYS 已成功启动！" -ForegroundColor Green
        Write-Host ""
        Write-Host "💡 下一步:" -ForegroundColor Cyan
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
        Write-Host "1. 打开浏览器访问: http://localhost:$HealthCheckPort/welcome"
        Write-Host "2. 查看快速入门指南: docs\quick-start-guide.md"
        Write-Host "3. 查看服务日志: docker compose logs -f"
        Write-Host ""

        exit 0
    } else {
        Write-Host "❌ 服务启动失败，请查看上面的故障排查建议" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "❌ 服务启动命令失败" -ForegroundColor Red
    exit 1
}
