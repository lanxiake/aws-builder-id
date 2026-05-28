# 兼容入口 → deploy/bin/windows/push-and-deploy.ps1
& "$PSScriptRoot\bin\windows\push-and-deploy.ps1" @args
if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE }
