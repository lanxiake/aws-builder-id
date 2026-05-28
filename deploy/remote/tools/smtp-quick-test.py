#!/usr/bin/env python3
"""快速 SMTP 测试。"""
import os
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_SCRIPT = """
import smtplib, time, json, re, urllib.request, traceback
from email.mime.text import MIMEText

try:
    print("1. 创建地址...")
    data = json.dumps({"name": "quicktest"}).encode()
    req = urllib.request.Request("http://127.0.0.1:18787/api/new_address",
                                 data=data, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read().decode())
    jwt_tok, addr = resp["jwt"], resp["address"]
    print(f"   {addr}")

    print("2. SMTP 发送...")
    msg = MIMEText("Your verification code is: 473829")
    msg["Subject"] = "Verify your email address"
    msg["From"] = "noreply@signin.aws"
    msg["To"] = addr
    with smtplib.SMTP("127.0.0.1", 25, timeout=10) as s:
        s.ehlo()
        result = s.sendmail("noreply@signin.aws", [addr], msg.as_string())
        print(f"   发送结果: {result}")
    print("   OK")

    print("3. 等待收信...")
    for i in range(15):
        time.sleep(2)
        req2 = urllib.request.Request("http://127.0.0.1:18787/api/mails",
                                      headers={"Authorization": f"Bearer {jwt_tok}"})
        mails = json.loads(urllib.request.urlopen(req2).read().decode())
        if mails:
            print(f"   收到 {len(mails)} 封!")
            for m in mails:
                print(f"   Subject: {m.get('subject','')}")
                raw = m.get("raw", "")
                codes = re.findall(r"(\\d{6})", raw)
                if codes:
                    print(f"   验证码: {codes[0]}")
            print("   PASS!")
            break
        if (i+1) % 3 == 0:
            print(f"   [{(i+1)*2}s] 等待中...")
    else:
        print("   30秒未收到邮件")
        import subprocess
        log = subprocess.check_output("tail -15 /var/log/mail.log", shell=True).decode()
        print(f"   mail.log:\\n{log}")

except Exception as e:
    traceback.print_exc()
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
c.connect(HOST, username="root", pkey=key, timeout=30, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
with sftp.open("/tmp/_quick_smtp.py", "w") as f:
    f.write(REMOTE_SCRIPT)
sftp.close()
_, stdout, stderr = c.exec_command(
    "source /opt/temp-email/.venv/bin/activate 2>/dev/null; python3 /tmp/_quick_smtp.py",
    timeout=60,
)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace").strip()
print(out)
if err:
    print("STDERR:", err[-800:])
c.close()
