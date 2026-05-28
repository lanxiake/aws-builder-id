# AWS Builder ID + VPS 临时邮箱 — 使用手册

本文档说明如何在德国 VPS（`192.119.110.157`）上部署 **临时邮箱服务** 与 **自动注册工具**，并完成联调。

## 一、架构概览

```
┌─────────────┐     HTTPS      ┌──────────────────────────────────┐
│ 本机/脚本   │ ──────────────►│ mx1.metoolbot.top (Nginx → API)   │
│ PowerShell  │                │ 127.0.0.1:18787  temp-email-api  │
└─────────────┘                └──────────────┬─────────────────────┘
                                              │ SQLite
┌─────────────┐     SMTP :25                  │
│ AWS / 外网  │ ─────────────────────────────►│ Postfix → pipe → DB │
└─────────────┘                               └────────────────────┘
```

| 组件 | 路径/端口 | 说明 |
|------|-----------|------|
| 邮箱 Web | `https://mx1.metoolbot.top/` | 浏览器收件箱（创建地址、刷新邮件） |
| 邮箱 API | `https://mx1.metoolbot.top` | 与 cloudflare_temp_email 兼容 |
| API 进程 | `127.0.0.1:18787` | systemd: `temp-email-api` |
| Postfix | `:25` | 收 `@metoolbot.top` 邮件 |
| 注册工具 | `/opt/aws-builder-id` | headless Chrome + Selenium |

## 二、服务器信息

见 `docs/服务器信息.md`：

- IP：`192.119.110.157`
- SSH：`root@192.119.110.157`，端口 22
- 邮箱 API 域名：`mx1.metoolbot.top`
- 收信域名：`metoolbot.top`

## 三、DNS 配置（重要）

### 3.1 必须项（API 访问）

| 类型 | 主机记录 | 记录值 | 说明 |
|------|----------|--------|------|
| A | `mx1` | `192.119.110.157` | 若走 Cloudflare，HTTP/HTTPS 可代理；**收信用建议仅 DNS（灰云）** |

### 3.2 收 AWS 验证邮件（关键）

当前若 MX 指向 Cloudflare 的 `_dc-mx.xxx.metoolbot.top`，**AWS 发来的邮件会进 Cloudflare 邮件路由，不会进 VPS Postfix**，注册时永远收不到验证码。

**推荐配置（DNSPod / Cloudflare DNS）：**

| 类型 | 主机记录 | 记录值 | 优先级 |
|------|----------|--------|--------|
| MX | `@` | `mx1.metoolbot.top` | 10 |
| A | `mx1` | `192.119.110.157` | — |

验证命令（本机 PowerShell）：

```powershell
nslookup -type=mx metoolbot.top 8.8.8.8
nslookup mx1.metoolbot.top 8.8.8.8
```

期望：MX 指向 `mx1.metoolbot.top`，且 `mx1` 解析到 `192.119.110.157`。

### 3.3 HTTPS 正式证书（DNS 生效后）

SSH 登录服务器执行：

```bash
certbot --nginx -d mx1.metoolbot.top --non-interactive --agree-tos -m admin@metoolbot.top
```

## 四、首次部署（本机 Windows）

### 4.1 环境准备

```powershell
cd d:\my-project\aws-builder-id
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt paramiko scp requests PyJWT
```

将 SSH 私钥放到：`%USERPROFILE%\.ssh\toolan_deploy.pem`（由 `docs/toolan.pem` 复制并限制权限）。

### 4.2 一键部署

```powershell
# 仅首次需要 root 密码，用于写入公钥
$env:DEPLOY_PASS = '你的root密码'
.\deploy\Invoke-FullDeploy.ps1
```

分步等价命令：

| 步骤 | 脚本 |
|------|------|
| 1. SSH 公钥免密 | `python deploy\remote\steps\01-setup-ssh.py` |
| 2. 邮箱服务 | `python deploy\remote\steps\02-deploy-email.py` |
| 3. 注册工具 | `python deploy\remote\steps\03-deploy-register.py` |

仅部署邮箱：`.\deploy\Invoke-FullDeploy.ps1 -EmailOnly`  
仅部署注册工具：`.\deploy\Invoke-FullDeploy.ps1 -RegisterOnly`

## 五、测试邮箱服务

### 5.1 本机测试

```powershell
.\deploy\Test-EmailService.ps1
# 跳过外网 SMTP（本机 25 端口常被封锁）：
.\deploy\Test-EmailService.ps1 -SkipSmtp
```

或：

```powershell
.\.venv\Scripts\python scripts\test_email_service.py
```

### 5.2 在 VPS 上测试 SMTP 全链路

```bash
ssh -i ~/.ssh/toolan_deploy.pem root@192.119.110.157
/opt/temp-email/.venv/bin/python -c "
import smtplib, json, time, re, urllib.request
from email.mime.text import MIMEText
data = json.dumps({'name':'vps_test'}).encode()
req = urllib.request.Request('http://127.0.0.1:18787/api/new_address', data=data,
    headers={'Content-Type':'application/json'})
r = json.loads(urllib.request.urlopen(req).read())
addr, jwt = r['address'], r['jwt']
msg = MIMEText('code 123456'); msg['Subject']='Verify'; msg['From']='noreply@signin.aws'; msg['To']=addr
smtplib.SMTP('127.0.0.1',25).sendmail('noreply@signin.aws',[addr],msg.as_string())
time.sleep(3)
m = json.loads(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18787/api/mails',
    headers={'Authorization':'Bearer '+jwt})).read())
print('mails:', len(m), m[0]['subject'] if m else 'none')
"
```

### 5.3 API 快速检查

```bash
curl -s https://mx1.metoolbot.top/api/health
curl -s -X POST https://mx1.metoolbot.top/api/new_address \
  -H "Content-Type: application/json" -d '{"name":"demo"}'
```

## 六、运行自动注册

### 6.1 VPS 配置

服务器上 `/opt/aws-builder-id/config/config.yaml` 建议：

```yaml
email:
  worker_url: http://127.0.0.1:18787   # 同机调用，不走公网
  domain: metoolbot.top
browser:
  headless: true
region:
  current: usa          # 或 germany / japan
  use_proxy: false    # 若 AWS 报 Request error，建议开启住宅代理
```

### 6.2 本机触发注册并看日志

```powershell
.\deploy\Invoke-RemoteRegister.ps1
```

### 6.3 直接在服务器运行

```bash
ssh root@192.119.110.157
cd /opt/aws-builder-id
source .venv/bin/activate
python src/runners/main.py
```

账号输出：`/opt/aws-builder-id/accounts.jsonl`（每行一个 JSON）。

### 6.4 注册失败常见原因

| 现象 | 原因 | 处理 |
|------|------|------|
| 姓名页 `error processing your request` | 数据中心 IP / 风控 | 配置 `region.use_proxy: true` 与住宅代理 |
| 一直等不到验证码 | MX 未指向 VPS | 按第三节改 DNS |
| ChromeDriver 版本不匹配 | Chrome 自动升级 | 服务器已安装 `/usr/local/bin/chromedriver`，`main.py` 使用 `version_main=148` |
| `ModuleNotFoundError: distutils` | Python 3.12 | `pip install setuptools` |

## 七、服务管理（SSH）

```bash
# 邮箱 API
systemctl status temp-email-api
systemctl restart temp-email-api
journalctl -u temp-email-api -f

# Postfix
systemctl status postfix
postqueue -p
postfix reload

# Nginx
nginx -t && systemctl reload nginx
```

日志位置：

- 注册：`/tmp/register_run.log`
- 邮件：`journalctl | grep postfix`

## 八、文件与脚本索引

| 文件 | 用途 |
|------|------|
| `deploy/Invoke-FullDeploy.ps1` | 一键部署（兼容入口） |
| `deploy/bin/windows/full-deploy.ps1` | 一键部署（推荐路径） |
| `deploy/bin/windows/test-email-service.ps1` | 本机邮箱测试 |
| `deploy/bin/windows/remote-register.ps1` | 远程启动注册 |
| `deploy/vps/install-email-server.sh` | 仅邮箱（在 VPS 执行） |
| `deploy/README.md` | 目录结构说明 |
| `scripts/test_email_service.py` | Python 测试入口 |
| `config/config.yaml` | 本机开发配置 |
| `docs/DNS邮箱配置.md` | DNS 说明 |

## 九、当前联调结论

- **邮箱 API**：`https://mx1.metoolbot.top/api/health` 正常；创建地址、Bearer 查询邮件接口可用。
- **VPS 本机 SMTP → Postfix → SQLite**：已验证通过（需 `virtual_mailbox_maps=regexp` 且 pipe 用户为 `nobody`）。
- **自动注册浏览器流程**：可打开 AWS 页面、创建邮箱、填表；**姓名提交步骤常被 AWS 拒绝**（与 IP/风控有关），需代理或更换出口 IP；**验证码依赖 MX 正确指向 VPS**。

完成 DNS（MX → `mx1.metoolbot.top`）并配置代理后，再执行：

```powershell
.\deploy\Invoke-RemoteRegister.ps1
```
