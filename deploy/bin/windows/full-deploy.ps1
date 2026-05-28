# 一键部署：SSH 密钥 -> 邮箱服务 -> 注册工具
# 用法:
#   $env:DEPLOY_PASS='你的root密码'   # 仅首次配置密钥时需要
#   .\deploy\bin\windows\full-deploy.ps1
# 兼容: .\deploy\Invoke-FullDeploy.ps1

param(
    [switch]$SkipEmail,
    [switch]$SkipRegister,
    [switch]$EmailOnly,
    [switch]$RegisterOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "创建虚拟环境并安装依赖..."
    python -m venv (Join-Path $ProjectRoot ".venv")
    & $VenvPython -m pip install -q -r (Join-Path $ProjectRoot "requirements.txt") paramiko scp PyJWT requests pyyaml
}

Push-Location $ProjectRoot
try {
    if (-not $RegisterOnly) {
        if (-not $env:DEPLOY_PASS -and -not (Test-Path (Join-Path $env:USERPROFILE ".ssh\toolan_deploy.pem"))) {
            Write-Host "首次部署请设置: `$env:DEPLOY_PASS='root密码'"
            exit 1
        }
        if ($env:DEPLOY_PASS) {
            Write-Host "=== 步骤1: 配置 SSH 公钥 ==="
            & $VenvPython deploy\remote\steps\01-setup-ssh.py
        }
    }

    if (-not $SkipEmail -and -not $RegisterOnly) {
        Write-Host "`n=== 步骤2: 部署邮箱服务 ==="
        & $VenvPython deploy\remote\steps\02-deploy-email.py
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not $SkipRegister -and -not $EmailOnly) {
        Write-Host "`n=== 步骤3: 打包并部署注册工具 ==="
        $tar = Join-Path $env:TEMP "aws-builder-id.tar.gz"
        tar -czf $tar --exclude=".venv" --exclude=".git" --exclude="__pycache__" `
            --exclude="data" --exclude="logs" --exclude="screenshots" `
            src config scripts requirements.txt
        & $VenvPython deploy\remote\steps\03-deploy-register.py
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "`n=== 步骤4: 邮箱服务测试 ==="
        & $VenvPython scripts\test_email_service.py --skip-smtp
    }

    Write-Host "`n部署完成。运行注册: .\deploy\Invoke-RemoteRegister.ps1"
}
finally {
    Pop-Location
}
