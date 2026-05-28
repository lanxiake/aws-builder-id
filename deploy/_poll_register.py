#!/usr/bin/env python3
"""轮询 VPS 注册日志。"""
import os
import sys
import time
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")


def get_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    return c


def main():
    """轮询并打印日志尾部。"""
    for i in range(120):
        time.sleep(10)
        c = get_client()
        _, stdout, _ = c.exec_command(
            "wc -c < /tmp/register_run.log 2>/dev/null; echo '---'; "
            "tail -20 /tmp/register_run.log 2>/dev/null; echo '---'; "
            "pgrep -af main.py 2>/dev/null || echo DEAD",
            timeout=30,
        )
        block = stdout.read().decode(errors="replace")
        c.close()
        parts = block.split("---")
        size_s = parts[0].strip().split()[0] if parts[0].strip() else "0"
        tail = parts[1] if len(parts) > 1 else ""
        print(f"[{(i+1)*10}s] {size_s} bytes")
        for line in tail.strip().split("\n")[-8:]:
            if line.strip():
                print(f"  {line[:130]}")
        if "DEAD" in block and int(size_s or 0) > 800:
            break
        if "获取到验证码" in tail:
            break

    c = get_client()
    _, stdout, _ = c.exec_command("tail -90 /tmp/register_run.log", timeout=30)
    print("\n" + "=" * 60 + "\n" + stdout.read().decode(errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
