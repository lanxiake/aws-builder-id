#!/usr/bin/env python3
"""在VPS上执行SMTP自发自收测试。"""
import os
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

TEST_SCRIPT = '''
import smtplib, time, json, sqlite3, urllib.request
from email.mime.text import MIMEText

print("=== SMTP 自发自收测试 ===")

# 创建地址
data = json.dumps({"name": "smtptest2"}).encode()
req = urllib.request.Request("http://127.0.0.1:18787/api/new_address",
                             data=data,
                             headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req).read().decode())
jwt_tok = resp["jwt"]
addr = resp["address"]
print(f"  地址: {addr}")
print(f"  JWT: {jwt_tok[:40]}...")

# SMTP 发送
msg = MIMEText("Your verification code is 654321. Test email.")
msg["Subject"] = "Verify your email - code 654321"
msg["From"] = "noreply@signin.aws"
msg["To"] = addr
try:
    with smtplib.SMTP("127.0.0.1", 25, timeout=10) as s:
        s.sendmail("noreply@signin.aws", [addr], msg.as_string())
    print("  SMTP 发送成功")
except Exception as e:
    print(f"  SMTP 失败: {e}")

# 等待并检查 DB
time.sleep(3)
db = sqlite3.connect("/opt/temp-email/data/email.db")
rows = db.execute("SELECT id, subject, sender FROM mails WHERE full_address=?",
                  (addr,)).fetchall()
print(f"  数据库: {len(rows)} 封邮件")
for r in rows:
    print(f"    id={r[0][:8]}  subject={r[1]}  from={r[2]}")
db.close()

# API 查询
req2 = urllib.request.Request("http://127.0.0.1:18787/api/mails",
                              headers={"Authorization": f"Bearer {jwt_tok}"})
resp2 = json.loads(urllib.request.urlopen(req2).read().decode())
print(f"  API: {len(resp2)} 封邮件")
for m in resp2:
    print(f"    subject={m.get('subject','?')}  from={m.get('from','?')}")

# 模拟验证码提取
import re
for m in resp2:
    raw = m.get("raw", "")
    codes = re.findall(r"\\b(\\d{6})\\b", raw)
    if codes:
        print(f"  提取到验证码: {codes[0]}")

print("\\n=== DNS MX 记录 ===")
import subprocess
try:
    out = subprocess.check_output(["dig", "MX", "metoolbot.top", "+short"],
                                  timeout=10).decode().strip()
    print(f"  {out}")
except Exception:
    try:
        out = subprocess.check_output(["nslookup", "-type=mx", "metoolbot.top", "8.8.8.8"],
                                      timeout=10).decode().strip()
        print(f"  {out[-300:]}")
    except Exception as e2:
        print(f"  查询失败: {e2}")

print("\\n=== 所有已注册地址 ===")
db = sqlite3.connect("/opt/temp-email/data/email.db")
rows = db.execute("SELECT full_address, created_at FROM addresses ORDER BY created_at DESC LIMIT 10").fetchall()
for r in rows:
    print(f"  {r[0]}")
total_mails = db.execute("SELECT COUNT(*) FROM mails").fetchone()[0]
print(f"  总邮件数: {total_mails}")
db.close()
'''


def main():
    """上传并执行测试脚本。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_smtp_test.py", "w") as f:
        f.write(TEST_SCRIPT)
    sftp.close()

    _, stdout, stderr = c.exec_command(
        "source /opt/temp-email/.venv/bin/activate 2>/dev/null; "
        "source /opt/aws-builder-id/.venv/bin/activate 2>/dev/null; "
        "python3 /tmp/_smtp_test.py",
        timeout=60
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-500:])
    c.close()


if __name__ == "__main__":
    main()
