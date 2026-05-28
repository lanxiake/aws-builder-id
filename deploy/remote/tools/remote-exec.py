#!/usr/bin/env python3
"""在远程服务器执行命令。用法: DEPLOY_PASS=xxx python deploy/remote/tools/remote-exec.py \"cmd\" """

import os
import sys

import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")


def main():
    password = os.environ.get("DEPLOY_PASS") or (sys.argv[1] if len(sys.argv) > 2 else None)
    cmd = sys.argv[-1] if len(sys.argv) >= 2 else "echo hi"
    if not password:
        print("需要 DEPLOY_PASS")
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST, username="root", password=password, timeout=30,
        allow_agent=False, look_for_keys=False,
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    sys.exit(stdout.channel.recv_exit_status())


if __name__ == "__main__":
    main()
