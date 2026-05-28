#!/usr/bin/env python3
"""
全面测试 VPS 临时邮箱服务：DNS、API、SMTP 收信。
用法: python scripts/test_email_service.py [--base-url URL]
"""
import argparse
import re
import smtplib
import subprocess
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DEFAULT_API = "https://mx1.metoolbot.top"
DEFAULT_SMTP_HOST = "192.119.110.157"
EMAIL_DOMAIN = "metoolbot.top"


def check_dns():
    """检查 MX / A 记录（Windows 使用 nslookup）。"""
    print("\n=== DNS 检查 ===")
    checks = [
        ("A mx1", f"nslookup mx1.{EMAIL_DOMAIN} 8.8.8.8"),
        ("MX @", f"nslookup -type=mx {EMAIL_DOMAIN} 8.8.8.8"),
    ]
    for label, cmd in checks:
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=15)
            text = out.decode(errors="replace")
            print(f"  [{label}]")
            for line in text.strip().splitlines()[-6:]:
                print(f"    {line}")
            if label == "MX @" and "mx1" not in text.lower() and "_dc-mx" in text.lower():
                print("    ⚠ MX 指向 Cloudflare 邮件路由，外部邮件可能进不了 VPS Postfix")
                print("    建议: MX @ -> mx1.metoolbot.top (10)，且 mx1 仅 DNS 解析到 VPS IP")
        except Exception as e:
            print(f"  [{label}] 查询失败: {e}")


def test_api(base_url: str) -> tuple[bool, str, str]:
    """测试 health / new_address / mails。"""
    print(f"\n=== API 测试 ({base_url}) ===")
    ok = True

    r = requests.get(f"{base_url}/api/health", timeout=15, verify=False)
    print(f"  GET /api/health -> {r.status_code} {r.text.strip()}")
    ok = ok and r.status_code == 200

    r = requests.post(
        f"{base_url}/api/new_address",
        json={"name": "autotest"},
        headers={"Content-Type": "application/json"},
        timeout=15,
        verify=False,
    )
    print(f"  POST /api/new_address -> {r.status_code}")
    if r.status_code != 200:
        return False, "", ""
    data = r.json()
    jwt, addr = data.get("jwt", ""), data.get("address", "")
    print(f"    address: {addr}")

    r = requests.get(
        f"{base_url}/api/mails?limit=5",
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=15,
        verify=False,
    )
    print(f"  GET /api/mails -> {r.status_code} (空收件箱应为 200 + [])")
    ok = ok and r.status_code == 200
    return ok, jwt, addr


def test_smtp_receive(smtp_host: str, addr: str, jwt: str, api_base: str) -> bool:
    """向 VPS 25 端口发送测试信并轮询 API。"""
    print(f"\n=== SMTP 收信测试 ({smtp_host}:25 -> {addr}) ===")
    msg = MIMEText("Your Amazon Web Services verification code is 847291.")
    msg["Subject"] = "Verify your email address"
    msg["From"] = "noreply@signin.aws"
    msg["To"] = addr
    try:
        with smtplib.SMTP(smtp_host, 25, timeout=30) as smtp:
            smtp.sendmail("noreply@signin.aws", [addr], msg.as_string())
        print("  SMTP 发送成功")
    except Exception as e:
        print(f"  SMTP 发送失败（本机可能封 25 端口）: {e}")
        print("  可在 VPS 上执行: python3 /opt/temp-email/deploy/vps_email/.. 或 deploy 内 smtp 测试")
        return False

    for i in range(15):
        time.sleep(2)
        r = requests.get(
            f"{api_base}/api/mails",
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=10,
            verify=False,
        )
        if r.status_code == 200 and r.json():
            raw = r.json()[0].get("raw", "")
            codes = re.findall(r"\b(\d{6})\b", raw)
            print(f"  收到邮件，验证码提取: {codes[0] if codes else '未匹配'}")
            return True
        if (i + 1) % 3 == 0:
            print(f"    等待中... {(i+1)*2}s")
    print("  超时未收到邮件")
    return False


def test_client_module(base_url: str) -> bool:
    """测试项目内 email_service 模块。"""
    print("\n=== 注册工具邮箱模块 ===")
    import os
    os.environ.setdefault("EMAIL_WORKER_URL_OVERRIDE", base_url)
    try:
        from config import EMAIL_WORKER_URL
        from services.email_service import create_temp_email

        print(f"  worker_url: {EMAIL_WORKER_URL}")
        addr, jwt = create_temp_email()
        if addr and jwt:
            print(f"  create_temp_email: {addr} OK")
            return True
        print("  create_temp_email 失败")
        return False
    except Exception as e:
        print(f"  跳过（需在本机配置 config.yaml）: {e}")
        return False


def main():
    """运行全部测试。"""
    parser = argparse.ArgumentParser(description="临时邮箱服务全面测试")
    parser.add_argument("--base-url", default=DEFAULT_API, help="API 根地址")
    parser.add_argument("--smtp-host", default=DEFAULT_SMTP_HOST, help="SMTP 主机")
    parser.add_argument("--skip-smtp", action="store_true", help="跳过 SMTP 外网测试")
    args = parser.parse_args()

    print("=" * 60)
    print("  临时邮箱服务 - 全面测试")
    print("=" * 60)

    check_dns()
    api_ok, jwt, addr = test_api(args.base_url)
    smtp_ok = False
    if api_ok and jwt and not args.skip_smtp:
        smtp_ok = test_smtp_receive(args.smtp_host, addr, jwt, args.base_url)
    client_ok = test_client_module(args.base_url)

    print("\n" + "=" * 60)
    print("汇总")
    print(f"  API:           {'PASS' if api_ok else 'FAIL'}")
    print(f"  SMTP 外网收信: {'PASS' if smtp_ok else 'SKIP/FAIL'}")
    print(f"  客户端模块:    {'PASS' if client_ok else 'SKIP/FAIL'}")
    print("=" * 60)
    sys.exit(0 if api_ok else 1)


if __name__ == "__main__":
    main()
