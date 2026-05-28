# 在 VPS 上启动 AWS Builder ID 注册并跟踪日志
# 用法: .\deploy\bin\windows\remote-register.ps1
# 兼容: .\deploy\Invoke-RemoteRegister.ps1
# 需要: ~/.ssh/toolan_deploy.pem 已配置免密登录

$ErrorActionPreference = "Stop"
$Host_ip = "192.119.110.157"
$KeyPath = Join-Path $env:USERPROFILE ".ssh\toolan_deploy.pem"
$RemoteDir = "/opt/aws-builder-id"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $KeyPath)) {
    Write-Host "未找到密钥: $KeyPath"
    exit 1
}

# 上传最新 main.py
Write-Host "[1/3] 上传 main.py ..."
scp -i $KeyPath -o StrictHostKeyChecking=no `
    "$ProjectRoot\src\runners\main.py" `
    "root@${Host_ip}:${RemoteDir}/src/runners/main.py"

Write-Host "[2/3] 在 VPS 后台启动注册 ..."
$StartCmd = @"
cd $RemoteDir && source .venv/bin/activate && \
rm -f /tmp/register_run.log && \
nohup python src/runners/main.py > /tmp/register_run.log 2>&1 & \
echo `$! > /tmp/register_run.pid && cat /tmp/register_run.pid
"@
$pid = ssh -i $KeyPath -o StrictHostKeyChecking=no root@$Host_ip $StartCmd
Write-Host "  PID: $pid"

Write-Host "[3/3] 跟踪日志 (Ctrl+C 停止查看，进程仍在服务器运行) ..."
ssh -i $KeyPath -o StrictHostKeyChecking=no root@$Host_ip "tail -f /tmp/register_run.log"
