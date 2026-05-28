# metoolbot.top 邮箱 DNS 配置（DNSPod）

邮箱 Web 收件箱：`https://mx1.metoolbot.top/`（浏览器打开即可创建地址、查看邮件）

邮箱 API 地址：`https://mx1.metoolbot.top`（Let's Encrypt 证书，HTTP 自动跳转 HTTPS）  
收信域名：`metoolbot.top`（注册时生成如 `abc123xyz@metoolbot.top`）

## 必填记录

| 类型 | 主机记录 | 记录值 | 说明 |
|------|----------|--------|------|
| A | `mx1` | `192.119.110.157` | 邮箱 API + 邮件服务器；**收信建议仅 DNS（灰云），不要橙云代理** |
| MX | `@` | `mx1.metoolbot.top` | 优先级 `10` |

> **注意**：若 MX 指向 Cloudflare 的 `_dc-mx.xxx.metoolbot.top`，AWS 验证邮件会进 CF 邮件路由，**不会**进入 VPS Postfix，注册脚本将永远收不到验证码。务必改为 `mx1.metoolbot.top`。

可选（仅 HTTP 测试阶段）：

| 类型 | 主机记录 | 记录值 |
|------|----------|--------|
| A | `@` | `192.119.110.157` |

## 验证

```bash
nslookup mx1.metoolbot.top
nslookup -type=mx metoolbot.top

curl -s https://mx1.metoolbot.top/api/health
curl -s -X POST https://mx1.metoolbot.top/api/new_address \
  -H "Content-Type: application/json" \
  -d '{"name":"test01"}'
```

返回含 `jwt` 与 `address` 即表示 API 正常。

## 服务器安装（仅邮箱）

SSH 不可用时，在 **VPS 控制台 VNC** 操作：

1. 用 SFTP/文件管理将本仓库 `deploy/artifacts/email-deploy.tar.gz` 上传到 `/root/`（或由 `Push-EmailServer.ps1` 自动生成）
2. 执行：

```bash
mkdir -p /root/email-deploy
tar -xzf /root/email-deploy.tar.gz -C /root/email-deploy
bash /root/email-deploy/install_email_server.sh
```

安装成功后本机验证：

```bash
curl -s http://127.0.0.1/api/health
curl -s -X POST http://127.0.0.1/api/new_address -H 'Content-Type: application/json' -d '{"name":"test"}'
```

Windows 本机（SSH 恢复后）可执行：`.\deploy\Push-EmailServer.ps1`
