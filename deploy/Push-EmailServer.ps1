# 兼容入口 → deploy/bin/windows/push-email-server.ps1
& "$PSScriptRoot\bin\windows\push-email-server.ps1" @args
if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE }
