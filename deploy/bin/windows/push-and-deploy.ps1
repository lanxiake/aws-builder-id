# 从 Windows 将项目上传到德国 VPS 并执行 server_setup.sh
# 用法: .\deploy\bin\windows\push-and-deploy.ps1
# 兼容: .\deploy\push_and_deploy.ps1
param(
    [string]$ServerHost = "192.119.110.157",
    [string]$ServerUser = "root",
    [int]$SshPort = 22,
    [string]$KeyPath = "$env:USERPROFILE\.ssh\toolan_deploy.pem",
    [string]$RemoteDir = "/opt/aws-builder-id"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if (-not (Test-Path $KeyPath)) {
    $srcKey = Join-Path $ProjectRoot "docs\toolan.pem"
    Copy-Item $srcKey $KeyPath -Force
    icacls $KeyPath /inheritance:r | Out-Null
    icacls $KeyPath /grant:r "${env:USERNAME}:(F)" | Out-Null
}

$sshTarget = "${ServerUser}@${ServerHost}"
$sshArgs = @("-i", $KeyPath, "-p", $SshPort, "-o", "StrictHostKeyChecking=no")

Write-Host "==> 测试 SSH 连接..."
& ssh @sshArgs @("-o", "BatchMode=yes", "-o", "ConnectTimeout=20") $sshTarget "echo SSH_OK"
if ($LASTEXITCODE -ne 0) {
    Write-Error @"
SSH 连接失败。请在 VPS 控制台检查:
  - fail2ban / ufw 是否封禁当前 IP
  - /etc/ssh/sshd_config 是否允许 PubkeyAuthentication
  - 安全组是否放行 TCP ${SshPort}
  - root 的 ~/.ssh/authorized_keys 是否包含本机公钥
可本地执行: ssh-keygen -y -f `"$KeyPath`"
"@
}

Write-Host "==> 创建远程目录..."
& ssh @sshArgs $sshTarget "mkdir -p $RemoteDir"

Write-Host "==> 同步项目文件 (排除 .venv、third-party)..."
$tarExclude = @(".venv", "deploy/third-party", ".git", "__pycache__", "accounts.jsonl")
# 使用 scp 递归上传（简单可靠）
& scp @sshArgs -r "$ProjectRoot\config" "$ProjectRoot\src" "$ProjectRoot\scripts" "$ProjectRoot\deploy" "$ProjectRoot\requirements.txt" "${sshTarget}:${RemoteDir}/"

Write-Host "==> 执行 server_setup.sh..."
& ssh @sshArgs $sshTarget "chmod +x ${RemoteDir}/deploy/server_setup.sh ${RemoteDir}/deploy/run_register.sh; APP_DIR=${RemoteDir} bash ${RemoteDir}/deploy/server_setup.sh"

Write-Host "完成。请 SSH 登录后编辑 ${RemoteDir}/config/config.yaml 并运行注册。"
