#!/usr/bin/env python3
"""在 VPS 上后台启动独立注册脚本并等待日志。"""

import os
import sys
import time

import paramiko

HOST = "192.119.110.157"
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username="root",
        pkey=paramiko.RSAKey.from_private_key_file(KEY),
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = c.open_sftp()

    launcher = """#!/bin/bash
set -e
cd /opt/aws-builder-id
source .venv/bin/activate

rm -f /tmp/standalone.log /tmp/step_*.png /tmp/final.png /tmp/error.png /tmp/standalone_result.json

pkill -f _standalone_register 2>/dev/null || true
pkill -f pproxy 2>/dev/null || true
sleep 1

nohup pproxy -l http://127.0.0.1:18080 -r 'http://70.39.242.6:443#WMauHktAwcKX:YiLkHvDOJs' > /tmp/pproxy.log 2>&1 &
sleep 2
echo "pproxy started"

export DISPLAY=:99
export PROXY_URL=http://127.0.0.1:18080
export GMAIL_BASE_USER=toojia0510
export GMAIL_APP_PASSWORD='ties zgem pvky ilah'

echo "starting standalone register..."
python /tmp/_standalone_register.py > /tmp/standalone.log 2>&1
echo "EXIT_CODE=$?"
echo "=== LOG ==="
cat /tmp/standalone.log
"""
    with sftp.open("/tmp/_launch_standalone.sh", "w") as f:
        f.write(launcher)
    sftp.close()

    print("Launching standalone register ...")
    _, stdout, stderr = c.exec_command(
        "bash /tmp/_launch_standalone.sh",
        get_pty=True,
        timeout=600,
    )
    out = stdout.read().decode(errors="replace")
    print(out)
    err = stderr.read().decode(errors="replace")
    if err:
        print("STDERR:", err, file=sys.stderr)
    c.close()


if __name__ == "__main__":
    main()
