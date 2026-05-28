"""
Gmail 别名临时邮箱 Provider。

利用 Gmail +tag 规则：主账号本地名 + 纯字母数字 tag，邮件进入主收件箱，经 IMAP 拉取验证码。
本地名仅含字母与数字（tag 亦同）；+ 为 Gmail 别名分隔符，投递所必需。
"""

import email as email_lib
import imaplib
import os
import random
import re
import string
import time
from email import policy
from email.header import decode_header
from email.utils import parsedate_to_datetime


def _get_gmail_config() -> dict:
    """从 config 或环境变量读取 Gmail 配置。"""
    base_user = os.environ.get("GMAIL_BASE_USER", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    tag_length = int(os.environ.get("GMAIL_TAG_LENGTH", "0") or 0)

    if not base_user or not app_password:
        try:
            from config import _config
            gmail_cfg = _config.get("email", {}).get("gmail", {})
            base_user = base_user or gmail_cfg.get("base_user", "")
            app_password = app_password or gmail_cfg.get("app_password", "")
            if not tag_length:
                tag_length = int(gmail_cfg.get("tag_length", 12) or 12)
        except Exception:
            pass

    if not tag_length:
        tag_length = 12

    if not base_user:
        raise ValueError(
            "Gmail base_user 未配置（config.yaml email.gmail.base_user 或 GMAIL_BASE_USER）"
        )
    if not app_password:
        raise ValueError(
            "Gmail app_password 未配置（config.yaml email.gmail.app_password 或 GMAIL_APP_PASSWORD）"
        )

    base_user = re.sub(r"[^a-z0-9]", "", base_user.replace("@gmail.com", "").lower())
    if not base_user:
        raise ValueError("Gmail base_user 须包含字母或数字")

    return {
        "base_user": base_user,
        "app_password": app_password,
        "tag_length": max(8, min(tag_length, 20)),
    }


def _random_alphanumeric(length: int) -> str:
    """生成仅含小写字母与数字的随机串。"""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def normalize_gmail_local(email: str) -> str:
    """
    规范化 Gmail 本地名用于匹配（去点、小写、保留 +tag）。
    """
    addr = (email or "").strip().lower()
    if "@" in addr:
        local, domain = addr.split("@", 1)
    else:
        local, domain = addr, "gmail.com"
    local = local.replace(".", "")
    return f"{local}@{domain}"


def generate_alias(base_user: str = "", tag_length: int = 0) -> str:
    """
    生成 Gmail 别名：baseuser+{纯字母数字tag}@gmail.com。

    显示/填写用的本地名仅含字母与数字；+ 为 Gmail 路由所需分隔符。
    """
    cfg = _get_gmail_config() if not base_user else None
    if not base_user:
        base_user = cfg["base_user"]
        tag_length = tag_length or cfg["tag_length"]
    else:
        base_user = re.sub(r"[^a-z0-9]", "", base_user.replace("@gmail.com", "").lower())
        tag_length = tag_length or 12

    tag = _random_alphanumeric(tag_length)
    return f"{base_user}+{tag}@gmail.com"


def create_gmail_alias_email() -> tuple[str, str]:
    """
    生成别名并返回 (email_address, alias_tag)。
    alias_tag 用于 IMAP 筛选与日志。
    """
    cfg = _get_gmail_config()
    alias = generate_alias(cfg["base_user"], cfg["tag_length"])
    tag = alias.split("+")[1].split("@")[0] if "+" in alias else ""
    print(f"📧 Gmail 别名: {alias}")
    return alias, tag


def _extract_code_from_text(text: str) -> str | None:
    """从文本中提取 6 位数字验证码。"""
    if not text:
        return None
    patterns = [
        r'code[:\s]+(\d{6})',
        r'verification[:\s]+(\d{6})',
        r'验证码[：:\s]+(\d{6})',
        r'\b(\d{6})\b',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _decode_header_value(raw) -> str:
    """解码邮件头字段。"""
    parts = decode_header(raw or "")
    result = []
    for data, charset in parts:
        if isinstance(data, bytes):
            result.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(data))
    return " ".join(result)


def _is_aws_mail(from_field: str, subject: str, purpose: str) -> bool:
    """判断是否为 AWS/Amazon 验证类邮件。"""
    from_l = (from_field or "").lower()
    subj_l = (subject or "").lower()
    if "amazon" not in from_l and "aws" not in from_l and "signin.aws" not in from_l:
        if "verify" not in subj_l and "verification" not in subj_l and "code" not in subj_l:
            return False

    if purpose == "login":
        login_hints = ("sign in", "sign-in", "login", "log in", "one-time", "otp", "security code")
        if any(h in subj_l for h in login_hints):
            return True
        return "verify" in subj_l or "code" in subj_l

    if purpose == "registration":
        reg_hints = ("builder", "verify your", "verification", "confirm")
        if any(h in subj_l for h in reg_hints):
            return True
        return True

    return True


def _mail_matches_alias(to_field: str, alias_address: str) -> bool:
    """收件人是否匹配目标别名（忽略点号差异）。"""
    target = normalize_gmail_local(alias_address)
    for part in re.split(r"[,;]", to_field or ""):
        part = part.strip().lower()
        if "<" in part and ">" in part:
            part = part.split("<", 1)[1].split(">", 1)[0].strip()
        if normalize_gmail_local(part) == target:
            return True
        if target.split("@")[0] in normalize_gmail_local(part):
            return True
    return False


def _parse_message_code(mail, mid: bytes, alias_address: str, purpose: str, since_ts: float) -> str | None:
    """解析单封邮件，匹配则返回验证码。"""
    _, data = mail.fetch(mid, "(RFC822)")
    if not data or not data[0] or not isinstance(data[0], tuple):
        return None
    raw = data[0][1]
    msg = email_lib.message_from_bytes(raw, policy=policy.default)

    try:
        date_hdr = msg.get("Date")
        if date_hdr:
            msg_dt = parsedate_to_datetime(date_hdr)
            if msg_dt.timestamp() < since_ts - 30:
                return None
    except Exception:
        pass

    to_field = msg.get("To") or ""
    from_field = msg.get("From") or ""
    subject = _decode_header_value(msg.get("Subject"))

    if not _mail_matches_alias(to_field, alias_address):
        return None
    if not _is_aws_mail(from_field, subject, purpose):
        return None

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    code = _extract_code_from_text(subject) or _extract_code_from_text(body)
    if code:
        print(f"\n✅ 收到验证邮件 ({purpose})")
        print(f"   主题: {subject}")
        print(f"   发件人: {from_field}")
        print(f"   验证码: {code}")
        return code
    return None


def wait_for_verification_from_gmail(
    alias_address: str,
    timeout: int = 180,
    poll_interval: int = 5,
    purpose: str = "any",
) -> str | None:
    """
    通过 IMAP 轮询主 Gmail，筛选发往 alias_address 的 AWS 验证码邮件。

    purpose: any | registration | login（登录时主题/发件人筛选更宽）
    同时搜索未读与最近邮件，避免「已读」导致漏信。
    """
    cfg = _get_gmail_config()
    full_email = f"{cfg['base_user']}@gmail.com"
    app_password = cfg["app_password"]
    purpose = (purpose or "any").lower()

    print(f"📨 IMAP 监听验证码 (主账号: {full_email}, purpose={purpose})")
    print(f"   目标别名: {alias_address}")

    start = time.time()
    since_ts = start - 60
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(full_email, app_password)
        mail.select("INBOX")
    except Exception as e:
        print(f"❌ IMAP 连接/登录失败: {e}")
        return None

    try:
        while time.time() - start < timeout:
            try:
                mail.select("INBOX")
                seen_ids: set[bytes] = set()
                for criteria in ("UNSEEN", "ALL"):
                    _, msg_nums = mail.search(None, f"({criteria})")
                    if not msg_nums or not msg_nums[0]:
                        continue
                    ids = msg_nums[0].split()
                    for mid in reversed(ids[-25:]):
                        if mid in seen_ids:
                            continue
                        seen_ids.add(mid)
                        code = _parse_message_code(
                            mail, mid, alias_address, purpose, since_ts
                        )
                        if code:
                            return code
            except Exception as e:
                print(f"  IMAP 轮询异常: {e}")

            elapsed = int(time.time() - start)
            print(f"  轮询中... ({elapsed}s)", end="\r")
            time.sleep(poll_interval)
    finally:
        try:
            if mail:
                mail.logout()
        except Exception:
            pass

    print(f"\n❌ 等待 Gmail 验证码超时 ({timeout}s)")
    return None
