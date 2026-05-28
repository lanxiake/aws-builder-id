#!/usr/bin/env python3
"""全面测试邮箱服务和注册工具链。"""
import os
import sys
import json
import time
import smtplib
import requests
from email.mime.text import MIMEText

HOST = "192.119.110.157"
DOMAIN_API = "https://mx1.metoolbot.top"
IP_API = f"http://{HOST}"
EMAIL_DOMAIN = "metoolbot.top"


def test_api(base_url, label):
    """测试邮箱 API 全部接口。"""
    print(f"\n{'='*50}")
    print(f"测试 API: {label} ({base_url})")
    print(f"{'='*50}")

    # 1. Health check
    print("\n[1] GET /api/health")
    try:
        r = requests.get(f"{base_url}/api/health", timeout=10, verify=False)
        print(f"  {r.status_code}: {r.text.strip()}")
        assert r.status_code == 200
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    # 2. Create address
    print("\n[2] POST /api/new_address")
    try:
        r = requests.post(f"{base_url}/api/new_address",
                          json={"name": "fulltest01"},
                          headers={"Content-Type": "application/json"},
                          timeout=10, verify=False)
        print(f"  {r.status_code}: {r.text.strip()[:150]}")
        data = r.json()
        jwt = data.get("jwt", "")
        addr = data.get("address", "")
        assert r.status_code == 200 and jwt and addr
        print(f"  Address: {addr}")
        print(f"  JWT: {jwt[:50]}...")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    # 3. Check messages (should be empty)
    print("\n[3] GET /api/mails (empty inbox)")
    try:
        r = requests.get(f"{base_url}/api/mails?jwt={jwt}", timeout=10, verify=False)
        print(f"  {r.status_code}: {r.text.strip()[:150]}")
        assert r.status_code == 200
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")

    return True, jwt, addr


def test_smtp_delivery():
    """测试 SMTP 收信（直连 VPS 25 端口发送邮件）。"""
    print(f"\n{'='*50}")
    print("测试 SMTP 收信（VPS 25 端口直连）")
    print(f"{'='*50}")

    # 先创建一个地址
    r = requests.post(f"{IP_API}/api/new_address",
                      json={"name": "smtptest"},
                      timeout=10)
    data = r.json()
    jwt = data["jwt"]
    addr = data["address"]
    print(f"  目标地址: {addr}")

    # 发送测试邮件到 VPS 的 25 端口
    print(f"\n  通过 SMTP 直连 {HOST}:25 发送测试邮件...")
    msg = MIMEText("This is a test verification code: 123456")
    msg["Subject"] = "Test Email Delivery"
    msg["From"] = "test@example.com"
    msg["To"] = addr

    try:
        with smtplib.SMTP(HOST, 25, timeout=30) as smtp:
            smtp.ehlo("test.local")
            smtp.sendmail("test@example.com", [addr], msg.as_string())
        print("  邮件发送成功")
    except Exception as e:
        print(f"  SMTP 发送失败: {e}")
        print("  可能 25 端口被防火墙阻止或 ISP 封禁")
        return False, jwt

    # 等待邮件处理
    print("  等待邮件处理...")
    for i in range(10):
        time.sleep(3)
        r = requests.get(f"{IP_API}/api/mails?jwt={jwt}", timeout=10)
        mails = r.json()
        if isinstance(mails, list) and len(mails) > 0:
            print(f"  收到 {len(mails)} 封邮件!")
            for m in mails:
                print(f"    From: {m.get('from', '?')}")
                print(f"    Subject: {m.get('subject', '?')}")
                print(f"    Body: {str(m.get('body', '?'))[:100]}")
            print("  PASS")
            return True, jwt
        print(f"    [{(i+1)*3}s] 无新邮件...")

    print("  FAIL: 30秒内未收到邮件")
    return False, jwt


def test_registration_chain():
    """测试注册工具的邮箱调用链（不启动浏览器）。"""
    print(f"\n{'='*50}")
    print("测试注册工具邮箱调用链")
    print(f"{'='*50}")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    try:
        from services.email_service import create_temp_email
        print("\n[1] create_temp_email()")
        addr, jwt = create_temp_email()
        print(f"  Address: {addr}")
        print(f"  JWT: {jwt[:50] if jwt else 'None'}...")
        assert addr and jwt
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()


def main():
    """运行全部测试。"""
    print("=" * 60)
    print("  全面邮箱服务测试")
    print("=" * 60)

    # 1. 通过 IP 测试 API
    ok1 = test_api(IP_API, "IP 直连")

    # 2. 通过域名测试 API
    ok2 = test_api(DOMAIN_API, "域名 HTTPS")

    # 3. SMTP 收信测试
    smtp_ok, _ = test_smtp_delivery()

    # 4. 注册工具调用链
    test_registration_chain()

    # 汇总
    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    print(f"  API (IP直连):   {'PASS' if ok1 else 'FAIL'}")
    print(f"  API (域名HTTPS): {'PASS' if ok2 else 'FAIL'}")
    print(f"  SMTP 收信:       {'PASS' if smtp_ok else 'FAIL'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
