# 兼容入口 → deploy/bin/windows/test-email-service.ps1
& "$PSScriptRoot\bin\windows\test-email-service.ps1" @args
if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE }
