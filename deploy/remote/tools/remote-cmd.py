#!/usr/bin/env python3
"""通过密钥 SSH 执行远程命令。用法: python deploy/remote/tools/remote-cmd.py \"command\" """
import os
import sys
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")


def main():
    """执行远程命令。"""
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo hi"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username="root", pkey=key, timeout=30,
                   allow_agent=False, look_for_keys=False)
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=300)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    sys.exit(code)


if __name__ == "__main__":
    main()
