# 本地全面测试邮箱 API（DNS + HTTP + 可选 SMTP）
# 用法: .\deploy\bin\windows\test-email-service.ps1 [-SkipSmtp]
# 兼容: .\deploy\Test-EmailService.ps1

param(
    [string]$BaseUrl = "https://mx1.metoolbot.top",
    [string]$SmtpHost = "192.119.110.157",
    [switch]$SkipSmtp
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "请先创建虚拟环境: python -m venv .venv && pip install -r requirements.txt requests"
    exit 1
}

$args = @("scripts\test_email_service.py", "--base-url", $BaseUrl, "--smtp-host", $SmtpHost)
if ($SkipSmtp) { $args += "--skip-smtp" }

Push-Location $ProjectRoot
try {
    & $VenvPython @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
