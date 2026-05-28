# 上传并远程安装邮箱服务（需 SSH 可用）
# 用法: .\deploy\bin\windows\push-email-server.ps1
# 兼容: .\deploy\Push-EmailServer.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$DeployRoot = Join-Path $ProjectRoot "deploy"
$Server = "192.119.110.157"
$User = "root"
$Key = "$env:USERPROFILE\.ssh\toolan_deploy.pem"
$RemoteDir = "/root/email-deploy"

if (-not (Test-Path $Key)) {
    Copy-Item "$ProjectRoot\docs\toolan.pem" $Key -Force
    icacls $Key /inheritance:r | Out-Null
    icacls $Key /grant:r "${env:USERNAME}:(F)" | Out-Null
}

$staging = Join-Path $env:TEMP "email-deploy"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path "$staging\vps_email" | Out-Null
Copy-Item "$DeployRoot\services\vps-email\*" "$staging\vps_email\"
Copy-Item "$DeployRoot\vps\install-email-server.sh" "$staging\install_email_server.sh"
$tar = Join-Path $env:TEMP "email-deploy.tar.gz"
if (Test-Path $tar) { Remove-Item $tar -Force }
& tar -czf $tar -C $staging .

Write-Host "==> 测试 SSH..."
ssh -i $Key -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 "${User}@${Server}" "echo SSH_OK"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "SSH 不可用。请在 VPS 控制台 (VNC) 执行以下步骤:" -ForegroundColor Yellow
    Write-Host "  1. 将本机目录打包上传: $tar"
    Write-Host "  2. 在服务器: mkdir -p /root/email-deploy && tar -xzf /root/email-deploy.tar.gz -C /root/email-deploy"
    Write-Host "  3. bash /root/email-deploy/install_email_server.sh"
    Write-Host ""
    Write-Host "或一键（需先 git push 到 GitHub）:"
    Write-Host "  curl -fsSL https://raw.githubusercontent.com/7836246/aws-builder-id/main/deploy/install_email_server.sh | bash"
    exit 1
}

Write-Host "==> 上传..."
ssh -i $Key -o StrictHostKeyChecking=no "${User}@${Server}" "mkdir -p $RemoteDir"
scp -i $Key -o StrictHostKeyChecking=no $tar "${User}@${Server}:/root/email-deploy.tar.gz"
ssh -i $Key -o StrictHostKeyChecking=no "${User}@${Server}" @"
set -e
mkdir -p $RemoteDir
tar -xzf /root/email-deploy.tar.gz -C $RemoteDir
bash $RemoteDir/install_email_server.sh
"@

Write-Host "==> 验证..."
ssh -i $Key -o StrictHostKeyChecking=no "${User}@${Server}" "curl -sf http://127.0.0.1/api/health; systemctl is-active temp-email-api postfix nginx"
Write-Host "完成"
