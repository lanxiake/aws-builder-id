#!/usr/bin/env python3
"""
测试 cloudflare_temp_email Worker API 是否可用。
用法: python scripts/test_email_api.py
"""

import json
import sys
from pathlib import Path

import requests

# 将 src 加入路径以读取 config
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import EMAIL_WORKER_URL, EMAIL_DOMAIN  # noqa: E402


def test_new_address():
    """
    调用 /api/new_address 创建临时邮箱并打印结果。
    返回: 成功 True，失败 False
    """
    url = f"{EMAIL_WORKER_URL.rstrip('/')}/api/new_address"
    print(f"Worker URL: {EMAIL_WORKER_URL}")
    print(f"域名: {EMAIL_DOMAIN}")
    print(f"POST {url}")

    try:
        resp = requests.post(
            url,
            json={"name": "deploytest"},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"请求失败: {exc}")
        return False

    print(f"HTTP {resp.status_code}")
    try:
        body = resp.json()
        print(json.dumps(body, ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text[:500])
        return False

    if resp.status_code != 200:
        return False

    if body.get("jwt") and (body.get("address") or EMAIL_DOMAIN):
        print("邮箱 API 正常")
        return True

    print("响应缺少 jwt 或 address")
    return False


if __name__ == "__main__":
    ok = test_new_address()
    sys.exit(0 if ok else 1)
