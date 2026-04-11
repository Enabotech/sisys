# ============================================================================
# 生成随机密码脚本
# 功能：为 .env 文件生成随机强密码
# 修复 C4: 避免硬编码明文密码
# ============================================================================

param(
    [string]$EnvTemplatePath = ".env.template",
    [string]$EnvOutputPath = ".env"
)

function New-RandomPassword {
    <#
    .SYNOPSIS
        生成随机强密码
    
    .PARAMETER Length
        密码长度（默认 16）
    
    .OUTPUTS
        string - 随机密码
    #>
    param([int]$Length = 16)
    
    $Chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+'
    $Password = -join ((1..$Length) | ForEach-Object { Get-Random -Input $Chars.ToCharArray() })
    
    return $Password
}

# ============================================================================
# 主逻辑
# ============================================================================

Write-Host "🔐 生成随机密码..." -ForegroundColor Cyan

# 生成密码
$postgresPassword = New-RandomPassword -Length 20
$minioPassword = New-RandomPassword -Length 20

Write-Host "✅ PostgreSQL 密码已生成 (${postgresPassword.Length} 字符)" -ForegroundColor Green
Write-Host "✅ MinIO 密码已生成 (${minioPassword.Length} 字符)" -ForegroundColor Green

# 替换模板中的占位符
if (Test-Path $EnvTemplatePath) {
    $content = Get-Content $EnvTemplatePath -Raw
    $content = $content -replace '__POSTGRES_PASSWORD_PLACEHOLDER__', $postgresPassword
    $content = $content -replace '__MINIO_PASSWORD_PLACEHOLDER__', $minioPassword
    
    # 替换数据路径占位符
    $sisysDataPath = "$env:USERPROFILE\SISYS\data"
    $sisysLogsPath = "$env:USERPROFILE\SISYS\logs"
    $content = $content -replace '__SISYS_DATA_PATH__', $sisysDataPath
    $content = $content -replace '__SISYS_LOGS_PATH__', $sisysLogsPath
    
    # 写入输出文件
    $content | Set-Content $EnvOutputPath -NoNewline
    
    Write-Host "✅ 配置文件已生成: $EnvOutputPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  重要: 请妥善保管以下密码:" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "PostgreSQL: $postgresPassword"
    Write-Host "MinIO: $minioPassword"
    Write-Host ""
    Write-Host "这些密码已写入 $EnvOutputPath，请限制访问权限。" -ForegroundColor Gray
} else {
    Write-Host "❌ 模板文件不存在: $EnvTemplatePath" -ForegroundColor Red
    exit 1
}
