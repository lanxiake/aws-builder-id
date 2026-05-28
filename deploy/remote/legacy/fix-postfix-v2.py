#!/usr/bin/env python3
"""修复 Postfix 虚拟邮箱映射并验证完整邮件收发链。"""
import os
import time
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

SMTP_TEST = '''
import smtplib, time, json, re, urllib.request
from email.mime.text import MIMEText

print("=== SMTP 完整收发测试 ===")
data = json.dumps({"name": "finalcheck"}).encode()
req = urllib.request.Request("http://127.0.0.1:18787/api/new_address",
                             data=data, headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req).read().decode())
jwt_tok, addr = resp["jwt"], resp["address"]
print(f"  创建地址: {addr}")

msg = MIMEText("Your verification code is: 473829")
msg["Subject"] = "Verify your email address"
msg["From"] = "noreply@signin.aws"
msg["To"] = addr
with smtplib.SMTP("127.0.0.1", 25, timeout=10) as s:
    s.sendmail("noreply@signin.aws", [addr], msg.as_string())
print("  SMTP 发送 OK")

for i in range(15):
    time.sleep(2)
    req2 = urllib.request.Request("http://127.0.0.1:18787/api/mails",
                                  headers={"Authorization": f"Bearer {jwt_tok}"})
    mails = json.loads(urllib.request.urlopen(req2).read().decode())
    if mails:
        print(f"  收到 {len(mails)} 封邮件!")
        for m in mails:
            print(f"    From: {m.get('from','')}")
            print(f"    Subject: {m.get('subject','')}")
            raw = m.get("raw", "")
            codes = re.findall(r"(\\d{6})", raw)
            if codes:
                print(f"    提取验证码: {codes[0]}")
        print("  PASS - 邮件收发链完整!")
        break
    print(f"    [{(i+1)*2}s] 等待中...")
else:
    print("  FAIL: 30秒未收到")
    import subprocess
    out = subprocess.check_output("tail -30 /var/log/mail.log 2>/dev/null || echo none", shell=True).decode()
    print(f"  mail.log:\\n{out[-2000:]}")
'''


def run(cmd, timeout=60):
    """执行远程命令。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    err = stderr.read().decode(errors="replace").strip()
    c.close()
    return code, out, err


def main():
    """修复并测试。"""
    # 1. 修改 virtual_mailbox_maps 为 regexp（内置无需额外包）
    print("[1] 修复 Postfix virtual_mailbox_maps...")
    # 用 regexp 类型替代 pcre，返回 OK 而非 transport
    code, out, _ = run(
        "echo '/.*@metoolbot\\.top$/  OK' > /etc/postfix/virtual_mailbox_regexp && "
        "postconf -e 'virtual_mailbox_maps = regexp:/etc/postfix/virtual_mailbox_regexp' && "
        "postfix reload && sleep 1 && "
        "postmap -q 'test@metoolbot.top' regexp:/etc/postfix/virtual_mailbox_regexp"
    )
    print(f"  lookup: '{out.strip()}'")

    if "OK" not in out:
        # 备用方案：使用 hash 表
        print("  regexp 仍然不行，改用 hash 方案...")
        code, out, _ = run(
            "echo '@metoolbot.top  OK' > /etc/postfix/virtual_mailbox && "
            "postmap /etc/postfix/virtual_mailbox && "
            "postconf -e 'virtual_mailbox_maps = hash:/etc/postfix/virtual_mailbox' && "
            "postfix reload && sleep 1 && "
            "postmap -q 'any@metoolbot.top' hash:/etc/postfix/virtual_mailbox"
        )
        print(f"  hash lookup: '{out.strip()}'")

    # 2. 确保 pipe 脚本和 DB 路径一致
    print("\n[2] 确保 postfix_pipe.sh 指向正确路径...")
    code, out, _ = run("cat /opt/temp-email/deploy/vps_email/postfix_pipe.sh")
    print(f"  {out.strip()}")

    # 确保 DB 路径一致
    code, out, _ = run("ls -la /opt/temp-email/data/")
    print(f"  data目录: {out.strip()}")

    # 3. 重启所有服务
    print("\n[3] 重启服务...")
    run("systemctl restart postfix temp-email-api")
    time.sleep(3)

    # 4. 运行测试
    print("\n[4] SMTP 收发测试...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_smtp_test2.py", "w") as f:
        f.write(SMTP_TEST)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        "source /opt/temp-email/.venv/bin/activate 2>/dev/null; "
        "python3 /tmp/_smtp_test2.py",
        timeout=60,
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-500:])
    c.close()


if __name__ == "__main__":
    main()
