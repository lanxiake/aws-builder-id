#!/usr/bin/env python3
"""步骤2：分步部署邮箱服务，逐步排查问题。"""
import os
import sys
import time
from pathlib import Path

import paramiko
from scp import SCPClient

# 加载 deploy/remote/lib/paths.py
_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))
from paths import INSTALL_EMAIL_SH, REMOTE_EMAIL_STAGING, VPS_EMAIL_SRC  # noqa: E402

HOST = "192.119.110.157"
USER = "root"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")


def get_client():
    """通过密钥连接服务器。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username=USER, pkey=key, timeout=30,
                   allow_agent=False, look_for_keys=False)
    return client


def run(client, cmd, timeout=300):
    """执行命令并打印输出。"""
    print(f"\n$ {cmd[:150]}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-3000:] if len(out) > 3000 else out)
    if code != 0:
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(f"STDERR: {err[-1000:]}")
        print(f"[exit {code}]")
    return code, out


def main():
    """分步部署邮箱服务。"""
    client = get_client()
    print(f"已连接 {USER}@{HOST}")

    # 上传文件
    print("\n=== 上传文件 ===")
    staging_sub = REMOTE_EMAIL_STAGING
    run(client, f"mkdir -p /root/email-deploy/{staging_sub} /opt/temp-email/deploy/{staging_sub} /opt/temp-email/data")
    with SCPClient(client.get_transport()) as scp:
        scp.put(str(INSTALL_EMAIL_SH), "/root/email-deploy/install_email_server.sh")
        for f in ["app.py", "postfix_pipe.sh", "requirements.txt"]:
            scp.put(str(VPS_EMAIL_SRC / f), f"/root/email-deploy/{staging_sub}/{f}")
    run(client, "sed -i 's/\\r$//' /root/email-deploy/install_email_server.sh /root/email-deploy/vps_email/*.sh")
    run(client, "chmod +x /root/email-deploy/install_email_server.sh /root/email-deploy/vps_email/postfix_pipe.sh")
    print("上传完成")

    # 分步安装
    steps = [
        ("安装 apt 依赖", (
            "export DEBIAN_FRONTEND=noninteractive; "
            "echo 'postfix postfix/mailname string mx1.metoolbot.top' | debconf-set-selections; "
            "echo 'postfix postfix/main_mailer_type string Internet Site' | debconf-set-selections; "
            "apt-get update -qq && "
            "apt-get install -y -qq postfix nginx certbot python3-certbot-nginx "
            "python3 python3-pip python3-venv openssl"
        ), 300),
        ("复制代码到 /opt/temp-email", (
            "cp -f /root/email-deploy/vps_email/app.py /opt/temp-email/deploy/vps_email/app.py && "
            "cp -f /root/email-deploy/vps_email/postfix_pipe.sh /opt/temp-email/deploy/vps_email/postfix_pipe.sh && "
            "cp -f /root/email-deploy/vps_email/requirements.txt /opt/temp-email/deploy/vps_email/requirements.txt && "
            "chmod +x /opt/temp-email/deploy/vps_email/postfix_pipe.sh"
        ), 30),
        ("Python venv + PyJWT", (
            "python3 -m venv /opt/temp-email/.venv && "
            "source /opt/temp-email/.venv/bin/activate && "
            "pip install -q -U pip && "
            "pip install -q PyJWT>=2.8.0"
        ), 120),
        ("配置 Postfix", (
            "postconf -e 'myhostname = mx1.metoolbot.top' && "
            "postconf -e 'mydestination =' && "
            "postconf -e 'inet_interfaces = all' && "
            "postconf -e 'virtual_mailbox_domains = metoolbot.top' && "
            "postconf -e 'virtual_mailbox_maps = pcre:/etc/postfix/virtual_mailbox_regexp' && "
            "postconf -e 'virtual_transport = tempmail:' && "
            r"echo '/^.+@metoolbot\\.top$/  tempmail:' > /etc/postfix/virtual_mailbox_regexp && "
            "grep -q '^tempmail' /etc/postfix/master.cf || echo -e '\\ntempmail   unix  -       n       n       -       -       pipe\\n"
            "  flags=FR user=root argv=/opt/temp-email/deploy/vps_email/postfix_pipe.sh ${recipient}' >> /etc/postfix/master.cf && "
            "systemctl enable postfix && systemctl restart postfix"
        ), 30),
        ("配置 temp-email-api 服务", (
            "cat > /etc/systemd/system/temp-email-api.service << 'UNIT'\n"
            "[Unit]\n"
            "Description=Temp Email API\n"
            "After=network.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            "Environment=EMAIL_DOMAIN=metoolbot.top\n"
            "Environment=EMAIL_API_HOST=127.0.0.1\n"
            "Environment=EMAIL_API_PORT=18787\n"
            "Environment=EMAIL_DB_PATH=/opt/temp-email/data/email.db\n"
            "WorkingDirectory=/opt/temp-email\n"
            "ExecStart=/opt/temp-email/.venv/bin/python /opt/temp-email/deploy/vps_email/app.py\n"
            "Restart=always\n"
            "RestartSec=3\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "UNIT\n"
            "systemctl daemon-reload && systemctl enable temp-email-api && systemctl restart temp-email-api"
        ), 30),
        ("配置 Nginx HTTP 反代", (
            "cat > /etc/nginx/sites-available/temp-email << 'NGX'\n"
            "server {\n"
            "    listen 80 default_server;\n"
            "    server_name mx1.metoolbot.top _;\n"
            "    location / {\n"
            "        proxy_pass http://127.0.0.1:18787;\n"
            "        proxy_http_version 1.1;\n"
            "        proxy_set_header Host $host;\n"
            "        proxy_set_header X-Real-IP $remote_addr;\n"
            "    }\n"
            "}\n"
            "NGX\n"
            "ln -sf /etc/nginx/sites-available/temp-email /etc/nginx/sites-enabled/temp-email && "
            "rm -f /etc/nginx/sites-enabled/default && "
            "nginx -t && systemctl reload nginx"
        ), 30),
        ("配置 Nginx HTTPS (自签名)", (
            "mkdir -p /etc/nginx/ssl && "
            "openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
            "-keyout /etc/nginx/ssl/temp-email.key -out /etc/nginx/ssl/temp-email.crt "
            "-subj '/CN=mx1.metoolbot.top' 2>/dev/null && "
            "cat > /etc/nginx/sites-available/temp-email-ssl << 'NGX'\n"
            "server {\n"
            "    listen 443 ssl default_server;\n"
            "    server_name mx1.metoolbot.top _;\n"
            "    ssl_certificate /etc/nginx/ssl/temp-email.crt;\n"
            "    ssl_certificate_key /etc/nginx/ssl/temp-email.key;\n"
            "    location / {\n"
            "        proxy_pass http://127.0.0.1:18787;\n"
            "        proxy_http_version 1.1;\n"
            "        proxy_set_header Host $host;\n"
            "        proxy_set_header X-Real-IP $remote_addr;\n"
            "    }\n"
            "}\n"
            "NGX\n"
            "ln -sf /etc/nginx/sites-available/temp-email-ssl /etc/nginx/sites-enabled/temp-email-ssl && "
            "nginx -t && systemctl reload nginx"
        ), 30),
    ]

    for name, cmd, timeout in steps:
        print(f"\n{'='*40}")
        print(f"=== {name} ===")
        code, _ = run(client, cmd, timeout=timeout)
        if code != 0 and code != -1:
            print(f"\n!!! {name} 失败，停止安装")
            client.close()
            sys.exit(1)

    # 验证
    print(f"\n{'='*40}")
    print("=== 验证 ===")
    time.sleep(3)
    run(client, "systemctl status temp-email-api --no-pager -l | head -15")
    run(client, "curl -sf http://127.0.0.1:18787/api/health; echo")
    run(client, "curl -sf http://127.0.0.1/api/health; echo")
    run(client, 'curl -sf -X POST http://127.0.0.1/api/new_address -H "Content-Type: application/json" -d \'{"name":"finaltest"}\'; echo')

    client.close()
    print("\n" + "=" * 50)
    print("邮箱服务部署完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
