#!/usr/bin/env python3
"""
验证 metoolbot.top 临时邮箱收发：
1) VPS 本机 SMTP 收信 + API 读取
2) QQ 邮箱 SMTP 外发 → @metoolbot.top（测公网入站）
3) VPS Postfix 外发到 QQ（测出站，可能未配置 relay）
"""
import json
import os
import re
import smtplib
import ssl
import time
import urllib.parse
import urllib.request

import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
API_BASE = "http://127.0.0.1:18787"

QQ_USER = os.environ.get("QQ_USER", "188294604@qq.com")
QQ_AUTH = os.environ.get("QQ_AUTH", "")


def ssh_run(py_script: str, timeout=120) -> str:
    """在 VPS 上执行 Python 脚本。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    path = "/tmp/_mail_roundtrip.py"
    with sftp.open(path, "w") as f:
        f.write(py_script)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        f"/opt/temp-email/.venv/bin/python3 {path} 2>&1",
        timeout=timeout,
    )
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace").strip()
    c.close()
    if err:
        out += f"\n[stderr] {err}"
    return out


def test_vps_receive() -> tuple[bool, str, str]:
    """VPS 本机创建地址并 SMTP 投递，API 收信。"""
    script = f'''
import smtplib, json, time, re, urllib.request
from email.mime.text import MIMEText

data = json.dumps({{"name": "rcvtest"}}).encode()
req = urllib.request.Request("{API_BASE}/api/new_address",
    data=data, headers={{"Content-Type": "application/json"}})
r = json.loads(urllib.request.urlopen(req, timeout=15).read())
addr, jwt = r["address"], r["jwt"]
print("ADDR", addr)

msg = MIMEText("Inbound test code 556677 from localhost SMTP.")
msg["Subject"] = "VPS local receive test 556677"
msg["From"] = "test@metoolbot.top"
msg["To"] = addr
with smtplib.SMTP("127.0.0.1", 25, timeout=15) as s:
    s.sendmail("test@metoolbot.top", [addr], msg.as_string())
print("LOCAL_SMTP_OK")

for i in range(12):
    time.sleep(2)
    req2 = urllib.request.Request("{API_BASE}/api/mails",
        headers={{"Authorization": f"Bearer {{jwt}}"}})
    mails = json.loads(urllib.request.urlopen(req2, timeout=15).read())
    if mails:
        raw = mails[0].get("raw", "")
        codes = re.findall(r"\\b(\\d{{6}})\\b", raw)
        print("RECEIVE_OK", mails[0].get("subject", ""), codes[0] if codes else "")
        break
else:
    print("RECEIVE_FAIL")
'''
    out = ssh_run(script)
    ok = "RECEIVE_OK" in out
    addr = ""
    for line in out.splitlines():
        if line.startswith("ADDR "):
            addr = line[5:].strip()
    return ok, addr, out


def test_qq_to_vps(target_addr: str) -> tuple[bool, str]:
    """QQ SMTP 发送邮件到临时地址。"""
    if not QQ_AUTH:
        return False, "未设置 QQ_AUTH 环境变量"

    body = (
        "This is an external inbound test from QQ mailbox. "
        "Verification code: 889900."
    )
    msg = (
        f"From: {QQ_USER}\r\n"
        f"To: {target_addr}\r\n"
        f"Subject: QQ to metoolbot inbound test 889900\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}\r\n"
    )

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30, context=ctx) as s:
            s.login(QQ_USER, QQ_AUTH)
            s.sendmail(QQ_USER, [target_addr], msg.encode("utf-8"))
        return True, "QQ_SMTP_SEND_OK"
    except Exception as e:
        return False, f"QQ_SMTP_FAIL: {e}"


def wait_api_mail(jwt: str, keyword: str, timeout_sec=120) -> tuple[bool, str]:
    """轮询 API 是否收到含关键字的邮件。"""
    script = f'''
import json, time, urllib.request
jwt = {jwt!r}
kw = {keyword!r}
for i in range({timeout_sec // 5}):
    time.sleep(5)
    req = urllib.request.Request("{API_BASE}/api/mails",
        headers={{"Authorization": f"Bearer {{jwt}}"}})
    mails = json.loads(urllib.request.urlopen(req, timeout=15).read())
    for m in mails:
        subj = (m.get("subject") or "").lower()
        raw = (m.get("raw") or "").lower()
        sender = (m.get("from") or "").lower()
        if kw in subj or kw in raw or "qq.com" in sender:
            print("FOUND", m.get("subject"), m.get("from"))
            break
    else:
        continue
    break
else:
    print("NOT_FOUND")
'''
    out = ssh_run(script, timeout=timeout_sec + 30)
    return "FOUND" in out, out


def test_vps_send_to_qq() -> tuple[bool, str]:
    """尝试从 VPS Postfix 发到 QQ（依赖出站 relay 配置）。"""
    script = f'''
import smtplib
from email.mime.text import MIMEText
msg = MIMEText("Outbound test from VPS Postfix to QQ.")
msg["Subject"] = "VPS outbound test to QQ"
msg["From"] = "noreply@metoolbot.top"
msg["To"] = "{QQ_USER}"
try:
    with smtplib.SMTP("127.0.0.1", 25, timeout=20) as s:
        s.sendmail("noreply@metoolbot.top", ["{QQ_USER}"], msg.as_string())
    print("OUTBOUND_QUEUE_OK")
except Exception as e:
    print("OUTBOUND_FAIL", e)
'''
    return "OUTBOUND_QUEUE_OK" in ssh_run(script), ssh_run(script)


def get_jwt_for_addr(addr: str) -> str:
    """为已有地址创建 JWT（通过 new_address 同名或查库）— 用 API 新建带固定前缀。"""
    # 外网测试用新地址更可靠
    return ""


def main():
    """执行全部测试。"""
    print("=" * 60)
    print("metoolbot.top 邮箱收发验证")
    print("=" * 60)

    print("\n[1] VPS 本机收信 (SMTP→Postfix→API)")
    ok1, addr1, out1 = test_vps_receive()
    print(out1)
    print("结果:", "PASS" if ok1 else "FAIL")

    # 为 QQ 入站测试创建新地址
    print("\n[2] 创建用于 QQ 入站测试的地址")
    create_script = f'''
import json, urllib.request
data = json.dumps({{"name": "qqinbound"}}).encode()
req = urllib.request.Request("{API_BASE}/api/new_address",
    data=data, headers={{"Content-Type": "application/json"}})
r = json.loads(urllib.request.urlopen(req).read())
print("ADDR", r["address"])
print("JWT", r["jwt"])
'''
    out2 = ssh_run(create_script)
    print(out2)
    addr2, jwt2 = "", ""
    for line in out2.splitlines():
        if line.startswith("ADDR "):
            addr2 = line[5:].strip()
        if line.startswith("JWT "):
            jwt2 = line[4:].strip()

    print(f"\n[3] QQ ({QQ_USER}) → {addr2}")
    ok3, msg3 = test_qq_to_vps(addr2)
    print(msg3)
    if ok3 and jwt2:
        print("等待 VPS 收信 (最多 120s)...")
        ok3b, out3b = wait_api_mail(jwt2, "889900", 120)
        print(out3b)
        print("公网入站:", "PASS" if ok3b else "FAIL")
    else:
        ok3b = False
        print("公网入站: SKIP/FAIL")

    print(f"\n[4] VPS → QQ ({QQ_USER}) 出站")
    ok4, out4 = test_vps_send_to_qq()
    print(out4)
    print("出站:", "PASS(已入队)" if ok4 else "FAIL", "(入队≠必达，需配置 SPF/中继)")

    print("\n" + "=" * 60)
    print("汇总")
    print(f"  本机收信:     {'PASS' if ok1 else 'FAIL'}")
    print(f"  QQ→临时邮箱:  {'PASS' if ok3 and ok3b else 'FAIL'}")
    print(f"  临时邮箱→QQ:  {'PASS(入队)' if ok4 else 'FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
