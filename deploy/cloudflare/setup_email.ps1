# 在本地部署 cloudflare_temp_email Worker（域名 metoolbot.top）
# 前置: 域名 NS 已指向 Cloudflare；已执行 npx wrangler login
param(
    [string]$Domain = "metoolbot.top",
    [string]$WorkerSubdomain = "temp-email-api",
    [string]$JwtSecret = "",
    [string]$AdminPassword = ""
)

$ErrorActionPreference = "Stop"
$DeployRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "_cf_email"
$WorkerDir = Join-Path $DeployRoot "worker"

if (-not (Test-Path $WorkerDir)) {
    Write-Host "克隆 cloudflare_temp_email..."
    git clone --depth 1 https://github.com/dreamhunter2333/cloudflare_temp_email.git $DeployRoot
}

if (-not $JwtSecret) {
    $JwtSecret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
}
if (-not $AdminPassword) {
    $AdminPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ })
}

Push-Location $WorkerDir
try {
    Write-Host "==> 检查 Wrangler 登录..."
    npx wrangler whoami
    if ($LASTEXITCODE -ne 0) {
        Write-Host "请先运行: npx wrangler login"
        exit 1
    }

    Write-Host "==> 创建 D1 数据库 (若已存在可忽略错误)..."
    $dbName = "temp_email_metoolbot"
    npx wrangler d1 create $dbName 2>$null
    $dbList = npx wrangler d1 list 2>&1 | Out-String
    if ($dbList -notmatch $dbName) {
        Write-Error "D1 数据库创建失败，请在 Cloudflare 控制台手动创建后重试"
    }
    $dbId = (npx wrangler d1 list --json | ConvertFrom-Json | Where-Object { $_.name -eq $dbName }).uuid

    $apiHost = "${WorkerSubdomain}.${Domain}"
    $template = Get-Content "wrangler.toml.template" -Raw
    $toml = $template `
        -replace 'name = "cloudflare_temp_email"', "name = `"temp-email-metoolbot`"" `
        -replace 'JWT_SECRET = "xxx"', "JWT_SECRET = `"$JwtSecret`"" `
        -replace 'DEFAULT_DOMAINS = \["xxx.xxx1" , "xxx.xxx2"\]', "DEFAULT_DOMAINS = [`"$Domain`"]" `
        -replace 'DOMAINS = \["xxx.xxx1" , "xxx.xxx2"\]', "DOMAINS = [`"$Domain`"]" `
        -replace 'database_name = "xxx"', "database_name = `"$dbName`"" `
        -replace 'database_id = "xxx"', "database_id = `"$dbId`""

    $toml += @"

routes = [
  { pattern = "${apiHost}/*", zone_name = "${Domain}" }
]
"@

    Set-Content -Path "wrangler.toml" -Value $toml -Encoding UTF8

    Write-Host "==> 安装依赖并部署 Worker..."
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        pnpm install
        pnpm run deploy
    } else {
        npm install
        npx wrangler deploy
    }

    Write-Host ""
    Write-Host "========== 部署信息 =========="
    Write-Host "Worker URL: https://${apiHost}"
    Write-Host "收信域名:   ${Domain}"
    Write-Host "JWT_SECRET: ${JwtSecret}"
    Write-Host "ADMIN 密码: ${AdminPassword}  (请写入 wrangler.toml ADMIN_PASSWORDS)"
    Write-Host ""
    Write-Host "请在 Cloudflare 控制台完成:"
    Write-Host "  1. Email Routing -> 启用 ${Domain}"
    Write-Host "  2. 添加 Catch-all -> Send to Worker (temp-email-metoolbot)"
    Write-Host "  3. DNS 自动添加 MX 记录"
    Write-Host ""
    Write-Host "然后更新 config/config.yaml:"
    Write-Host "  email.worker_url: https://${apiHost}"
    Write-Host "  email.domain: ${Domain}"
}
finally {
    Pop-Location
}
