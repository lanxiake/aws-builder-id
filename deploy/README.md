# deploy 目录说明

部署相关脚本按职责分层，避免根目录堆满 `_*.py` 与混杂入口。

## 目录结构

```
deploy/
├── README.md                 # 本文件
├── DEPLOY.md                 # 完整部署文档
│
├── bin/windows/              # 本机 Windows 入口（推荐从这里执行）
│   ├── full-deploy.ps1       # 一键：SSH → 邮箱 → 注册工具
│   ├── remote-register.ps1   # 远程启动注册
│   ├── push-email-server.ps1 # 仅上传安装邮箱
│   ├── test-email-service.ps1
│   └── push-and-deploy.ps1   # 同步整个项目到 VPS
│
├── vps/                      # 在 VPS 上执行的 Shell
│   ├── bootstrap.sh          # 控制台一键（SSH + 全量安装）
│   ├── console-install.sh
│   ├── server-setup.sh       # Chrome + Python + 项目
│   ├── install-email-server.sh  # 仅邮箱（可打 tar 包）
│   ├── run-register.sh
│   └── ...
│
├── services/
│   └── vps-email/            # 自建临时邮箱（API + Postfix pipe）
│       ├── app.py
│       ├── postfix_pipe.sh
│       ├── install.sh        # 随完整项目安装邮箱
│       └── requirements.txt
│
├── remote/                   # 本机通过 SSH 自动化（paramiko）
│   ├── steps/                # 正式流水线（按序号）
│   │   ├── 01-setup-ssh.py
│   │   ├── 02-deploy-email.py
│   │   ├── 03-deploy-register.py
│   │   └── 04-run-register.py
│   ├── tools/                # 排障与单次工具
│   ├── legacy/               # 旧版步骤与历史修复脚本
│   └── lib/paths.py          # 路径常量
│
├── artifacts/                # 预打包产物（可选）
├── cloudflare/               # Cloudflare Worker 邮箱备选方案
└── third-party/              # 第三方参考代码（勿改）
```

## 常用命令

```powershell
# 一键部署（推荐）
$env:DEPLOY_PASS = 'root密码'   # 仅首次
.\deploy\Invoke-FullDeploy.ps1

# 等价新路径
.\deploy\bin\windows\full-deploy.ps1
```

```powershell
python deploy\remote\steps\02-deploy-email.py
```

## 兼容说明

`deploy/` 根目录下保留 **薄包装脚本**（如 `Invoke-FullDeploy.ps1`），转发到 `bin/windows/`，避免旧文档与 curl URL 失效。

独立邮箱安装包（tar）内仍使用 `vps_email/` 子目录名，与 VPS 上 `/opt/temp-email/deploy/vps_email` 路径一致。
