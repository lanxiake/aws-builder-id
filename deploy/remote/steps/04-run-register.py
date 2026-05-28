#!/usr/bin/env python3
"""步骤4：在VPS上运行注册工具并监控日志。"""
import os
import sys
import time
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE_DIR = "/opt/aws-builder-id"


def get_client():
    """获取新的SSH连接。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    return c


def run(cmd, timeout=60):
    """新建连接执行命令。"""
    c = get_client()
    _, stdout, _ = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    return code, out


def main():
    """启动注册并轮询日志。"""
    print("=" * 50)
    print("步骤4: 运行 AWS Builder ID 注册")
    print("=" * 50)

    # 清理旧日志、启动
    run("rm -f /tmp/register_run.log")
    run(
        f"cd {REMOTE_DIR} && source .venv/bin/activate && "
        "nohup python src/runners/main.py "
        "> /tmp/register_run.log 2>&1 & echo $! > /tmp/register_run.pid"
    )
    time.sleep(2)

    _, pid_str = run("cat /tmp/register_run.pid 2>/dev/null")
    pid = pid_str.strip()
    print(f"  后台进程 PID={pid}")

    # 轮询日志
    last_size = 0
    for i in range(120):
        time.sleep(5)
        _, log = run(f"wc -c < /tmp/register_run.log 2>/dev/null; echo '---'; tail -20 /tmp/register_run.log 2>/dev/null")
        parts = log.split("---", 1)
        size = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
        tail = parts[1].strip() if len(parts) > 1 else ""

        if size != last_size:
            last_size = size
            print(f"\n[{(i+1)*5}s] log size={size}")
            for line in tail.split("\n")[-10:]:
                print(f"  {line}")

        # 检查进程是否还在运行
        _, alive = run(f"kill -0 {pid} 2>/dev/null && echo ALIVE || echo DEAD")
        if "DEAD" in alive:
            print(f"\n进程已结束")
            _, full_log = run("cat /tmp/register_run.log")
            print("\n=== 完整日志（尾部） ===")
            print(full_log[-5000:])
            break
    else:
        print("\n轮询超时（10分钟），请手动检查 /tmp/register_run.log")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
