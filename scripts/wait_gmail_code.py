#!/usr/bin/env python3
"""
等待指定 Gmail 别名地址的 AWS 验证码（注册/登录均可）。

用法:
  python scripts/wait_gmail_code.py --email "baseuser+abc123@gmail.com"
  python scripts/wait_gmail_code.py --email "..." --purpose login
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.gmail_alias_service import wait_for_verification_from_gmail


def main() -> int:
    """解析参数并轮询 IMAP。"""
    parser = argparse.ArgumentParser(description="等待 Gmail 别名验证码")
    parser.add_argument("--email", required=True, help="注册/登录时填写的完整别名邮箱")
    parser.add_argument(
        "--purpose",
        default="any",
        choices=("any", "registration", "login"),
        help="邮件类型筛选",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    code = wait_for_verification_from_gmail(
        alias_address=args.email,
        timeout=args.timeout,
        poll_interval=args.interval,
        purpose=args.purpose,
    )
    if code:
        print(f"\n验证码: {code}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
