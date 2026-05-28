#!/usr/bin/env python3
"""后台执行安装并轮询日志。"""

import os
import sys
import time

import paramiko
from scp import SCPClient

HOST = "192.119.110.157"
TAR = os.path.join(os.path.dirname(__file__), "email-deploy.tar.gz")


def main():
    password = os.environ.get("DEPLOY_PASS")
    if not password:
        print("需要 DEPLOY_PASS")
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST, username="root", password=password, timeout=30,
        allow_agent=False, look_for_keys=False,
    )

    with SCPClient(client.get_transport()) as scp:
        scp.put(TAR, "/root/email-deploy.tar.gz")

    prep = (
        "mkdir -p /root/email-deploy && "
        "tar -xzf /root/email-deploy.tar.gz -C /root/email-deploy && "
        "chmod +x /root/email-deploy/install_email_server.sh /root/email-deploy/vps_email/postfix_pipe.sh && "
        "pkill -f install_email_server.sh 2>/dev/null; "
        "nohup bash /root/email-deploy/install_email_server.sh > /root/email-install.log 2>&1 &"
        "echo started"
    )
    client.exec_command(prep)

    for i in range(120):
        time.sleep(5)
        _, stdout, _ = client.exec_command(
            "tail -5 /root/email-install.log 2>/dev/null; "
            "pgrep -f install_email_server.sh >/dev/null && echo RUNNING || echo DONE",
            timeout=15,
        )
        tail = stdout.read().decode(errors="replace")
        print(f"[{i*5}s]", tail.strip().replace("\n", " | "))
        if "DONE" in tail and "RUNNING" not in tail.split("|")[-1]:
            break

    _, stdout, _ = client.exec_command("cat /root/email-install.log", timeout=60)
    log = stdout.read().decode(errors="replace")
    print("\n=== LOG (last 4000) ===\n", log[-4000:])

    _, stdout, _ = client.exec_command(
        "curl -sf http://127.0.0.1:18787/api/health; echo; "
        "systemctl is-active temp-email-api 2>/dev/null; echo",
        timeout=30,
    )
    print("=== VERIFY ===\n", stdout.read().decode())
    client.close()


if __name__ == "__main__":
    main()
