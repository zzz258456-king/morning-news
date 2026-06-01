# Claude Code + DeepSeek 重试代理 一键启动脚本
# 用法: PowerShell -File run_claude_with_proxy.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Claude Code + DeepSeek 重试代理启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查代理脚本是否存在
$proxyScript = Join-Path $PSScriptRoot "deepseek_proxy.py"
if (-not (Test-Path $proxyScript)) {
    Write-Host "❌ 找不到 deepseek_proxy.py" -ForegroundColor Red
    exit 1
}

# 2. 检查 Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "❌ 找不到 Python" -ForegroundColor Red
    exit 1
}

# 3. 检查代理端口是否已被占用
$portCheck = netstat -an | Select-String "127.0.0.1:8765"
if ($portCheck) {
    Write-Host "⚠️  端口 8765 已被占用，可能代理已在运行" -ForegroundColor Yellow
    $proxyRunning = $true
} else {
    $proxyRunning = $false
}

# 4. 启动代理（后台）
if (-not $proxyRunning) {
    Write-Host "🚀 启动 DeepSeek 重试代理..." -ForegroundColor Green
    $proxyJob = Start-Job -ScriptBlock {
        param($script, $dir)
        Set-Location $dir
        python $script
    } -ArgumentList $proxyScript, $PSScriptRoot

    # 等待代理启动
    Start-Sleep -Seconds 2

    # 检查代理是否启动成功
    $check = netstat -an | Select-String "127.0.0.1:8765"
    if (-not $check) {
        Write-Host "  等待代理启动..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }
    Write-Host "✅ 代理已启动: http://127.0.0.1:8765" -ForegroundColor Green
}

# 5. 设置环境变量并启动 Claude Code
Write-Host "📦 配置环境变量..." -ForegroundColor Green
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8765"
$env:API_TIMEOUT_MS = "300000"  # 5分钟，足够代理重试用

Write-Host "🚀 启动 Claude Code..." -ForegroundColor Green
Write-Host "   模型: deepseek-chat" -ForegroundColor Gray
Write-Host "   API: http://127.0.0.1:8765 (→ api.deepseek.com)" -ForegroundColor Gray
Write-Host "   超时: 300秒 (含3次重试)" -ForegroundColor Gray
Write-Host ""

# 启动 Claude Code（保持环境变量只在本次会话生效）
claude

# 6. Claude Code 退出后，询问是否关闭代理
Write-Host ""
Write-Host "Claude Code 已退出。" -ForegroundColor Yellow
$choice = Read-Host "是否关闭代理? (Y/n)"
if ($choice -eq "" -or $choice -eq "y" -or $choice -eq "Y") {
    if ($proxyJob -and $proxyJob.State -eq "Running") {
        Stop-Job $proxyJob -ErrorAction SilentlyContinue
        Remove-Job $proxyJob -ErrorAction SilentlyContinue
        Write-Host "✅ 代理已关闭" -ForegroundColor Green
    }
}
