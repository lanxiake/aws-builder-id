#!/usr/bin/env python3
"""
测试 Gmail IMAP 连接 + 别名生成。
验证 App Password 能否正常登录并读取邮件。
"""
import os, sys
from pathlib import Path
import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_SCRIPT = r"""#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/aws-builder-id/src')

# 测试1：别名生成
print("=== 测试1：Gmail 别名生成 ===")
from services.gmail_alias_service import generate_alias, create_gmail_alias_email

for i in range(5):
    alias = generate_alias(use_plus=True)
    print(f"  +tag 别名 {i+1}: {alias}")

for i in range(3):
    alias = generate_alias(use_plus=False)
    print(f"  纯点别名 {i+1}: {alias}")

email, tag = create_gmail_alias_email()
print(f"  生成邮箱: {email}")
print(f"  别名 tag: {tag}")

# 测试2：IMAP 连接
print()
print("=== 测试2：Gmail IMAP 登录 ===")
from services.gmail_alias_service import _get_gmail_config
import imaplib

cfg = _get_gmail_config()
full_email = f"{cfg['base_user']}@gmail.com"
print(f"  主账号: {full_email}")
print(f"  App密码: {'*' * len(cfg['app_password'])}")

try:
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    status, caps = mail.login(full_email, cfg['app_password'])
    print(f"  登录状态: {status}")
    
    # 选择收件箱
    status, data = mail.select("INBOX")
    print(f"  收件箱状态: {status}, 邮件数: {data[0].decode()}")
    
    # 搜索最近10封邮件
    status, msg_nums = mail.search(None, "ALL")
    if msg_nums and msg_nums[0]:
        ids = msg_nums[0].split()
        print(f"  总邮件数: {len(ids)}")
        
        # 读最近3封邮件的主题
        for mid in ids[-3:]:
            status, data = mail.fetch(mid, "(BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            if data and data[0]:
                raw = data[0][1] if isinstance(data[0], tuple) else data[0]
                if isinstance(raw, bytes):
                    print(f"  ---")
                    print(f"  {raw.decode(errors='replace').strip()}")
    else:
        print("  收件箱为空")
    
    mail.logout()
    print()
    print("✅ Gmail IMAP 测试通过!")
except Exception as e:
    print(f"❌ IMAP 测试失败: {e}")
    import traceback
    traceback.print_exc()
"""

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY),
              timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_gmail_test.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    _, stdout, stderr = c.exec_command(
        "cd /opt/aws-builder-id && /opt/aws-builder-id/.venv/bin/python /tmp/_gmail_test.py 2>&1",
        get_pty=True, timeout=60,
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    c.close()

if __name__ == "__main__":
    main()
