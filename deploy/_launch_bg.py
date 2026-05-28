#!/usr/bin/env python3
"""上传并后台启动注册脚本，然后轮询日志。"""

import os
import sys
import time
from pathlib import Path

import paramiko

HOST = "192.119.110.157"
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")


def connect():
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


def run_cmd(c, cmd, timeout=30):
    """执行命令，返回 stdout。"""
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    return out


def main():
    repo = Path(__file__).resolve().parents[1]

    c = connect()
    sftp = c.open_sftp()

    # 上传脚本
    sftp.put(str(repo / "deploy" / "_bg_register.sh"), "/tmp/_bg_register.sh")
    print("Uploaded _bg_register.sh")

    # 确认独立脚本还在
    try:
        sftp.stat("/tmp/_standalone_register.py")
        print("_standalone_register.py already on VPS")
    except OSError:
        print("Need to re-upload _standalone_register.py (not found)")
        sftp.close()
        c.close()
        return 1
    sftp.close()

    # 后台启动
    print("Launching in background ...")
    c.exec_command("nohup bash /tmp/_bg_register.sh &>/dev/null &", timeout=10)
    time.sleep(5)
    c.close()

    # 轮询日志
    print("\nPolling log ...")
    last_lines = 0
    for _ in range(120):
        try:
            c2 = connect()
            log = run_cmd(c2, "cat /tmp/standalone.log 2>/dev/null", timeout=10)
            c2.close()

            lines = log.strip().split("\n")
            if len(lines) > last_lines:
                for line in lines[last_lines:]:
                    print(line)
                last_lines = len(lines)

            if "Script finished" in log or "ERROR:" in log or "Final URL:" in log:
                print("\n--- Script completed ---")
                break
        except Exception as e:
            print(f"  (poll error: {e})")
        time.sleep(5)

    # 最终检查
    try:
        c3 = connect()
        result = run_cmd(c3, "cat /tmp/standalone_result.json 2>/dev/null", timeout=10)
        if result.strip():
            print("\n=== RESULT ===")
            print(result)
        files = run_cmd(c3, "ls -la /tmp/step_*.png /tmp/final.png /tmp/error.png 2>/dev/null", timeout=10)
        if files.strip():
            print("\n=== SCREENSHOTS ===")
            print(files)
        c3.close()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
