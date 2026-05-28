#!/usr/bin/env python3
"""上传最新 cloak_driver.py + main.py 到 VPS，然后用真实邮箱做 A/B 测试（只测 Continue）。"""

import os
import paramiko
from pathlib import Path


def main() -> int:
    """执行一次远程 A/B 测试。"""
    repo = Path(__file__).resolve().parents[1]
    local_cloak_driver = repo / "src" / "helpers" / "cloak_driver.py"
    local_main = repo / "src" / "runners" / "main.py"
    if not local_cloak_driver.is_file() or not local_main.is_file():
        print("缺少需要上传的文件")
        return 1

    key_path = os.path.expanduser("~/.ssh/toolan_deploy.pem")
    if not os.path.isfile(key_path):
        print(f"缺少 SSH 私钥: {key_path}")
        return 1

    host = "192.119.110.157"
    test_email = os.environ.get("TEST_EMAIL", "").strip()
    if not test_email:
        test_email = "singledog.lxk@foxmail.com"

    remote_cloak_driver = "/opt/aws-builder-id/src/helpers/cloak_driver.py"
    remote_main = "/opt/aws-builder-id/src/runners/main.py"

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

    sftp = c.open_sftp()
    sftp.put(str(local_cloak_driver), remote_cloak_driver)
    sftp.put(str(local_main), remote_main)
    sftp.close()

    cmd = (
        "cd /opt/aws-builder-id && "
        "source .venv/bin/activate && "
        f"TEST_EMAIL={test_email} STOP_AFTER_CONTINUE=1 BROWSER_ENGINE=uc_plain "
        "python src/runners/main.py"
    )
    _, stdout, stderr = c.exec_command(cmd, get_pty=True, timeout=900)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    c.close()

    print(out)
    if err.strip():
        print("\n--- STDERR ---")
        print(err)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

