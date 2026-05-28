# 兼容入口 → deploy/bin/windows/full-deploy.ps1
& "$PSScriptRoot\bin\windows\full-deploy.ps1" @args
if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE }
