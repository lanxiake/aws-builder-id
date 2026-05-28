#!/usr/bin/env python3
"""对 AWS Builder 注册做真实邮箱 A/B 测试（姓名页 Continue 后直接退出）。"""

import os
import paramiko


def main() -> int:
    """执行一次 VPS 上的注册流程测试。"""
    key_path = os.path.expanduser("~/.ssh/toolan_deploy.pem")
    if not os.path.isfile(key_path):
        print(f"缺少 SSH 私钥: {key_path}")
        return 1

    host = "192.119.110.157"
    email = "singledog.lxk@foxmail.com"

    cmd = (
        "cd /opt/aws-builder-id && "
        "source .venv/bin/activate && "
        f"TEST_EMAIL={email} STOP_AFTER_CONTINUE=1 "
        "python src/runners/main.py"
    )

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        host,
        username="root",
        pkey=paramiko.RSAKey.from_private_key_file(key_path),
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    _, stdout, stderr = c.exec_command(cmd, get_pty=True, timeout=900)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    c.close()

    print(out)
    if err.strip():
        print("\n--- STDERR ---")
        print(err)
    return 0 if not err.strip() else 2


if __name__ == "__main__":
    raise SystemExit(main())

