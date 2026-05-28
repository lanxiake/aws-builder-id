# remote/steps

从 Windows 本机执行的正式部署流水线（需 paramiko、scp）。

| 脚本 | 作用 |
|------|------|
| `01-setup-ssh.py` | 用 root 密码写入 SSH 公钥 |
| `02-deploy-email.py` | 部署 mx1 临时邮箱 |
| `03-deploy-register.py` | 上传并安装注册工具 |
| `04-run-register.py` | 在 VPS 上启动注册并看日志 |

由 `deploy/bin/windows/full-deploy.ps1` 按序调用。
