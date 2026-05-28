#!/usr/bin/env python3
"""验证邮箱收信后启动注册并跟踪日志。"""
import os
import sys
import time
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE_DIR = "/opt/aws-builder-id"

EMAIL_TEST = r'''
import smtplib, json, time, re, urllib.request, sys
from email.mime.text import MIMEText

print("=== 邮箱收信验证 ===")
data = json.dumps({"name": "reg_precheck"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:18787/api/new_address",
    data=data, headers={"Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=10).read())
addr, jwt = r["address"], r["jwt"]
print(f"创建地址: {addr}")

msg = MIMEText("Your Amazon Web Services verification code is 847291.")
msg["Subject"] = "Verify your email address"
msg["From"] = "noreply@signin.aws"
msg["To"] = addr
with smtplib.SMTP("127.0.0.1", 25, timeout=15) as s:
    s.sendmail("noreply@signin.aws", [addr], msg.as_string())
print("SMTP 本机投递 OK")

ok = False
for i in range(15):
    time.sleep(2)
    req2 = urllib.request.Request(
        "http://127.0.0.1:18787/api/mails",
        headers={"Authorization": f"Bearer {jwt}"})
    mails = json.loads(urllib.request.urlopen(req2, timeout=10).read())
    if mails:
        raw = mails[0].get("raw", "")
        codes = re.findall(r"\b(\d{6})\b", raw)
        print(f"收到邮件: subject={mails[0].get('subject','')}")
        print(f"验证码提取: {codes[0] if codes else 'N/A'}")
        ok = True
        break
    print(f"  等待 {(i+1)*2}s ...")

if not ok:
    print("FAIL: 未收到邮件")
    sys.exit(1)
print("EMAIL_TEST_PASS")
'''


def get_client():
    """SSH 密钥连接。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    return c


def run_remote_script(script: str, timeout=120) -> tuple[int, str]:
    """上传并执行远程 Python 脚本。"""
    c = get_client()
    sftp = c.open_sftp()
    path = "/tmp/_remote_task.py"
    with sftp.open(path, "w") as f:
        f.write(script)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        f"/opt/temp-email/.venv/bin/python3 {path} 2>&1",
        timeout=timeout,
    )
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    err = stderr.read().decode(errors="replace").strip()
    c.close()
    if err:
        out += f"\n[stderr] {err}"
    return code, out


def start_register():
    """后台启动注册并轮询日志。"""
    c = get_client()
    cmd = (
        f"cd {REMOTE_DIR} && source .venv/bin/activate && "
        "rm -f /tmp/register_run.log && "
        "nohup python src/runners/main.py > /tmp/register_run.log 2>&1 & "
        "echo $! > /tmp/register_run.pid && cat /tmp/register_run.pid"
    )
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    pid = stdout.read().decode().strip().split()[-1]
    c.close()
    print(f"\n注册进程已启动 PID={pid}")
    print("跟踪日志...\n")

    last_size = 0
    for i in range(150):
        time.sleep(6)
        c = get_client()
        _, stdout, _ = c.exec_command(
            "wc -c < /tmp/register_run.log 2>/dev/null; echo '---'; "
            "tail -25 /tmp/register_run.log 2>/dev/null; echo '---'; "
            "kill -0 $(cat /tmp/register_run.pid 2>/dev/null) 2>/dev/null && echo ALIVE || echo DEAD",
            timeout=30,
        )
        block = stdout.read().decode(errors="replace")
        c.close()

        parts = block.split("---")
        try:
            size = int(parts[0].strip().split()[0])
        except (ValueError, IndexError):
            size = 0
        tail = parts[1].strip() if len(parts) > 1 else ""
        status = parts[2].strip() if len(parts) > 2 else ""

        if size != last_size:
            last_size = size
            print(f"[{(i+1)*6}s] ---")
            for line in tail.split("\n")[-12:]:
                if line.strip():
                    print(f"  {line}")

        if "账号流程结束" in tail or "账号已保存" in tail and "DEAD" in status:
            pass
        if "DEAD" in status:
            print("\n进程已结束，完整日志尾部:")
            c = get_client()
            _, stdout, _ = c.exec_command("tail -60 /tmp/register_run.log", timeout=30)
            print(stdout.read().decode(errors="replace"))
            c.close()
            if "获取到验证码" in tail or "final_success" in tail.lower():
                return 0
            if "未能获取到验证码" in tail or "error processing" in tail.lower():
                return 1
            return 0

    print("\n轮询超时（15分钟）")
    return 2


def main():
    """主流程。"""
    print("=" * 55)
    print("步骤 1/2: 验证邮箱收信")
    print("=" * 55)
    code, out = run_remote_script(EMAIL_TEST, timeout=90)
    print(out)
    if code != 0 or "EMAIL_TEST_PASS" not in out:
        print("\n邮箱验证未通过，中止注册。")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("步骤 2/2: 启动 AWS Builder ID 注册")
    print("=" * 55)
    rc = start_register()
    sys.exit(rc)


if __name__ == "__main__":
    main()
