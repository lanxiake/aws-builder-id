#!/usr/bin/env python3
"""用 screen 在 VPS 后台启动独立注册，然后轮询日志。"""

import os
import sys
import time

import paramiko

HOST = "192.119.110.157"
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

BG_SCRIPT = """#!/bin/bash
set -e
cd /opt/aws-builder-id
source .venv/bin/activate

rm -f /tmp/standalone.log /tmp/step_*.png /tmp/final.png /tmp/error.png /tmp/standalone_result.json
pkill -9 -f _standalone_register 2>/dev/null || true
pkill -9 -f chrome 2>/dev/null || true
pkill -9 -f chromedriver 2>/dev/null || true
pkill -f pproxy 2>/dev/null || true
sleep 3

pkill -f Xvfb 2>/dev/null || true
sleep 1
Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
sleep 1

nohup pproxy -l http://127.0.0.1:18080 -r 'http://70.39.242.6:443#WMauHktAwcKX:YiLkHvDOJs' > /tmp/pproxy.log 2>&1 &
sleep 2

export DISPLAY=:99
export PROXY_URL=http://127.0.0.1:18080
export GMAIL_BASE_USER=toojia0510
export GMAIL_APP_PASSWORD='ties zgem pvky ilah'

echo "$(date) Starting standalone register" > /tmp/standalone.log
python /tmp/_standalone_register.py >> /tmp/standalone.log 2>&1
echo "$(date) EXIT=$?" >> /tmp/standalone.log
"""


def connect():
    """建立 SSH 连接。"""
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
    return c


def run_cmd(c, cmd, timeout=15):
    """执行命令并返回 stdout。"""
    _, stdout, _ = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="replace")


def main():
    c = connect()
    sftp = c.open_sftp()

    # 写入 shell 脚本（确保 Unix 换行符）
    with sftp.open("/tmp/_bg_register.sh", "w") as f:
        f.write(BG_SCRIPT.replace("\r\n", "\n"))
    print("Uploaded _bg_register.sh (Unix LF)")
    sftp.close()

    # 用 screen 启动
    run_cmd(c, "screen -X -S reg quit 2>/dev/null || true")
    time.sleep(1)
    run_cmd(c, "screen -dmS reg bash /tmp/_bg_register.sh")
    time.sleep(3)
    sessions = run_cmd(c, "screen -ls 2>/dev/null || true")
    print(f"Screen sessions: {sessions.strip()}")
    c.close()

    # 轮询日志
    print("\n=== Polling log (every 10s, up to 6 min) ===")
    last_size = 0
    for i in range(36):
        time.sleep(10)
        try:
            c2 = connect()
            log = run_cmd(c2, "cat /tmp/standalone.log 2>/dev/null")
            c2.close()
        except Exception as e:
            print(f"  (connection error: {e})")
            continue

        if len(log) > last_size:
            new_part = log[last_size:]
            print(new_part, end="")
            last_size = len(log)

        if "EXIT=" in log or "Script finished" in log or "Final URL:" in log:
            print("\n\n--- Done ---")
            break
    else:
        print("\n\n--- Timeout (6 min) ---")

    # 最终结果
    try:
        c3 = connect()
        result = run_cmd(c3, "cat /tmp/standalone_result.json 2>/dev/null")
        if result.strip():
            print("\n=== RESULT ===")
            print(result)
        files = run_cmd(c3, "ls -la /tmp/step_*.png /tmp/final.png /tmp/error.png 2>/dev/null")
        if files.strip():
            print("\n=== SCREENSHOTS ===")
            print(files)
        c3.close()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
