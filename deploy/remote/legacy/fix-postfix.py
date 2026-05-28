#!/usr/bin/env python3
"""安装 postfix-pcre 并测试完整邮件收发链。"""
import os
import time
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

SMTP_TEST = '''
import smtplib, time, json, sqlite3, urllib.request, re
from email.mime.text import MIMEText

print("=== SMTP 完整测试 ===")

# 创建新地址
data = json.dumps({"name": "pipetest"}).encode()
req = urllib.request.Request("http://127.0.0.1:18787/api/new_address",
                             data=data,
                             headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req).read().decode())
jwt_tok = resp["jwt"]
addr = resp["address"]
print(f"  目标: {addr}")

# 发送模拟 AWS 验证邮件
msg = MIMEText("Your verification code is: 473829\\n\\nPlease enter this code.")
msg["Subject"] = "Verify your email address"
msg["From"] = "noreply@signin.aws"
msg["To"] = addr

with smtplib.SMTP("127.0.0.1", 25, timeout=10) as s:
    s.sendmail("noreply@signin.aws", [addr], msg.as_string())
print("  SMTP 发送成功")

# 等待 Postfix 处理
for i in range(10):
    time.sleep(2)
    req2 = urllib.request.Request("http://127.0.0.1:18787/api/mails",
                                  headers={"Authorization": f"Bearer {jwt_tok}"})
    resp2 = json.loads(urllib.request.urlopen(req2).read().decode())
    if resp2:
        print(f"  收到 {len(resp2)} 封邮件!")
        for m in resp2:
            print(f"    From: {m.get('from','?')}")
            print(f"    Subject: {m.get('subject','?')}")
            raw = m.get("raw", "")
            codes = re.findall(r"\\b(\\d{6})\\b", raw)
            if codes:
                print(f"    验证码: {codes[0]}")
        print("  PASS!")
        break
    print(f"    [{(i+1)*2}s] 等待中...")
else:
    print("  FAIL: 20秒未收到")

# 检查 mail.log
import subprocess
out = subprocess.check_output(
    "tail -20 /var/log/mail.log 2>/dev/null || echo 'no mail.log'",
    shell=True).decode()
print(f"\\n=== mail.log ===\\n{out[-1500:]}")
'''


def run(cmd, timeout=120):
    """执行远程命令。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    return code, out


def main():
    """修复 Postfix 并测试。"""
    # 安装 postfix-pcre
    print("[1] 安装 postfix-pcre...")
    code, out = run("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postfix-pcre 2>&1")
    print(out[-500:])

    print("[2] 重启 Postfix...")
    run("systemctl restart postfix")
    time.sleep(2)

    print("[3] 验证 pcre lookup...")
    code, out = run("postmap -q 'test@metoolbot.top' pcre:/etc/postfix/virtual_mailbox_regexp")
    print(f"  lookup result: '{out.strip()}'")

    # 上传并运行测试
    print("\n[4] SMTP 自发自收测试...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_smtp_full_test.py", "w") as f:
        f.write(SMTP_TEST)
    sftp.close()

    _, stdout, stderr = c.exec_command(
        "source /opt/temp-email/.venv/bin/activate 2>/dev/null; "
        "source /opt/aws-builder-id/.venv/bin/activate 2>/dev/null; "
        "python3 /tmp/_smtp_full_test.py",
        timeout=60,
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-500:])
    c.close()


if __name__ == "__main__":
    main()
