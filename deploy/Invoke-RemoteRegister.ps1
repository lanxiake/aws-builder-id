# 兼容入口 → deploy/bin/windows/remote-register.ps1
& "$PSScriptRoot\bin\windows\remote-register.ps1" @args
if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE }
