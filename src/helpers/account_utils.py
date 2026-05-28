"""账号保存与密码生成（避免 runners.main 与 CloakBrowser 冲突）。"""

import json
import os
import random
import string
from datetime import datetime


def generate_strong_password() -> str:
    """生成高强度密码。"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(random.choices(chars, k=16))
    password = (
        random.choice(string.ascii_uppercase)
        + random.choice(string.ascii_lowercase)
        + random.choice(string.digits)
        + random.choice("!@#$%^&*")
        + password[4:]
    )
    return password


def save_account(
    email: str,
    password: str,
    name: str,
    jwt_token: str = "",
    *,
    login_verified: bool | None = None,
    status: str = "registered",
) -> None:
    """追加保存账号到 accounts.jsonl。"""
    account_info = {
        "email": email,
        "password": password,
        "name": name,
        "jwt_token": jwt_token,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
    }
    if login_verified is not None:
        account_info["login_verified"] = login_verified
    file_path = "accounts.jsonl"
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(account_info, ensure_ascii=False) + "\n")
        print(f"✅ 账号已保存: {email}")
    except Exception as e:
        print(f"❌ 保存账号失败: {e}")
