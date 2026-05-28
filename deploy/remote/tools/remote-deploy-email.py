#!/usr/bin/env python3
"""通过 SSH 密码上传并安装邮箱服务（勿提交含密码的版本）。"""

import os
import subprocess
import sys

import paramiko
from scp import SCPClient

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
USER = os.environ.get("DEPLOY_USER", "root")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAR = os.path.join(ROOT, "deploy", "email-deploy.tar.gz")
PUBKEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")


def main():
    """上传安装包并执行 install_email_server.sh。"""
    password = os.environ.get("DEPLOY_PASS")
    if not password and len(sys.argv) > 1:
        password = sys.argv[1]
    if not password:
        print("用法: DEPLOY_PASS=xxx python deploy/remote/tools/remote-deploy-email.py")
        sys.exit(1)

    if not os.path.isfile(TAR):
        print(f"缺少安装包: {TAR}")
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST, username=USER, password=password, timeout=30,
        allow_agent=False, look_for_keys=False,
    )

    try:
        pub = subprocess.check_output(
            ["ssh-keygen", "-y", "-f", PUBKEY], text=True, stderr=subprocess.DEVNULL
        ).strip()
        client.exec_command(
            f'mkdir -p /root/.ssh && chmod 700 /root/.ssh && '
            f'grep -qF "{pub[:50]}" /root/.ssh/authorized_keys 2>/dev/null || '
            f'echo "{pub}" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys'
        )
    except Exception:
        pass

    print("==> 上传 email-deploy.tar.gz ...")
    with SCPClient(client.get_transport()) as scp:
        scp.put(TAR, "/root/email-deploy.tar.gz")

    install_cmd = (
        "set -e\n"
        "mkdir -p /root/email-deploy\n"
        "tar -xzf /root/email-deploy.tar.gz -C /root/email-deploy\n"
        "chmod +x /root/email-deploy/install_email_server.sh "
        "/root/email-deploy/vps_email/postfix_pipe.sh\n"
        "bash /root/email-deploy/install_email_server.sh\n"
    )
    print("==> 执行安装（约 2–5 分钟）...")
    _, stdout, stderr = client.exec_command(install_cmd, get_pty=True, timeout=900)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print("STDERR:", err[-4000:])
    if code != 0:
        print("安装失败 exit=", code)
        client.close()
        sys.exit(code)

    print("==> 验证...")
    verify = (
        "curl -sf http://127.0.0.1:18787/api/health; echo; "
        "curl -sf http://127.0.0.1/api/health; echo; "
        "systemctl is-active temp-email-api postfix nginx; echo; "
        'curl -sf -X POST http://127.0.0.1/api/new_address '
        '-H "Content-Type: application/json" -d \'{"name":"deploychk"}\'; echo'
    )
    _, stdout, _ = client.exec_command(verify, timeout=60)
    print(stdout.read().decode())
    client.close()
    print("==> 完成")


if __name__ == "__main__":
    main()
