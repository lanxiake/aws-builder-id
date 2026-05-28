#!/usr/bin/env python3
"""步骤2：通过SSH密钥上传文件并部署邮箱服务到VPS。"""
import os
import sys
import time
import paramiko
from scp import SCPClient

HOST = "192.119.110.157"
USER = "root"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
_DEPLOY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEPLOY_DIR = _DEPLOY_ROOT
_VPS_EMAIL = os.path.join(_DEPLOY_ROOT, "services", "vps-email")
_INSTALL_SH = os.path.join(_DEPLOY_ROOT, "vps", "install-email-server.sh")


def get_client():
    """通过密钥连接服务器。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username=USER, pkey=key, timeout=30,
                   allow_agent=False, look_for_keys=False)
    return client


def ssh_run(client, cmd, timeout=600):
    """执行远程命令，实时打印输出。"""
    print(f"\n>>> {cmd[:120]}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    output = []
    for line in iter(stdout.readline, ""):
        print(f"  {line}", end="")
        output.append(line)
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if err.strip():
        print(f"  [stderr] {err.strip()}")
    if code != 0:
        print(f"  [exit {code}]")
    return code, "".join(output)


def main():
    """上传并安装邮箱服务。"""
    print("=" * 50)
    print("步骤2: 部署邮箱服务 mx1.metoolbot.top")
    print("=" * 50)

    client = get_client()
    print(f"已通过密钥连接 {USER}@{HOST}")

    # 上传文件
    print("\n[1/5] 上传邮箱服务文件...")
    ssh_run(client, "mkdir -p /root/email-deploy/vps_email")
    with SCPClient(client.get_transport()) as scp:
        scp.put(_INSTALL_SH, "/root/email-deploy/install_email_server.sh")
        scp.put(os.path.join(_VPS_EMAIL, "app.py"), "/root/email-deploy/vps_email/app.py")
        scp.put(os.path.join(_VPS_EMAIL, "postfix_pipe.sh"), "/root/email-deploy/vps_email/postfix_pipe.sh")
        scp.put(os.path.join(_VPS_EMAIL, "requirements.txt"), "/root/email-deploy/vps_email/requirements.txt")
    print("  文件上传完成")

    # 修复换行符
    print("\n[2/5] 修复脚本换行符...")
    ssh_run(client, "sed -i 's/\\r$//' /root/email-deploy/install_email_server.sh /root/email-deploy/vps_email/postfix_pipe.sh")
    ssh_run(client, "chmod +x /root/email-deploy/install_email_server.sh /root/email-deploy/vps_email/postfix_pipe.sh")

    # 等待 apt 锁
    print("\n[3/5] 等待 apt 锁释放...")
    ssh_run(client, "while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do echo 'waiting for apt...'; sleep 3; done; echo 'apt ready'")

    # 执行安装
    print("\n[4/5] 执行安装脚本（可能需要几分钟）...")
    code, _ = ssh_run(client, "bash /root/email-deploy/install_email_server.sh", timeout=600)
    if code != 0:
        print(f"\n安装失败 (exit={code})")
        client.close()
        sys.exit(1)

    # 验证
    print("\n[5/5] 验证服务状态...")
    time.sleep(3)
    ssh_run(client, "systemctl is-active temp-email-api postfix nginx")
    ssh_run(client, 'curl -sf http://127.0.0.1:18787/api/health; echo')
    ssh_run(client, 'curl -sf http://127.0.0.1/api/health; echo')
    ssh_run(client, 'curl -sf -X POST http://127.0.0.1/api/new_address -H "Content-Type: application/json" -d \'{"name":"testdeploy"}\'; echo')

    client.close()
    print("\n" + "=" * 50)
    print("邮箱服务部署完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
