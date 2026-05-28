#!/usr/bin/env python3
"""测试代理访问 AWS 页面。"""
import os
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
PROXY = os.environ.get(
    "PROXY_URL",
    "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443",
)

SCRIPT = f'''
import requests
p = {{"http": "{PROXY}", "https": "{PROXY}"}}
for url in ["https://builder.aws.com/start", "https://www.amazon.com"]:
    try:
        r = requests.get(url, proxies=p, timeout=45, allow_redirects=True,
                         headers={{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}})
        low = r.text.lower()
        print(url)
        print("  status:", r.status_code, "len:", len(r.text), "final:", r.url[:90])
        print("  has signup:", "sign up" in low or "builder id" in low)
    except Exception as e:
        print(url, "FAIL", e)
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
c.connect(HOST, username="root", pkey=key, timeout=30, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
with sftp.open("/tmp/_aws_proxy_test.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command(
    "source /opt/aws-builder-id/.venv/bin/activate && python3 /tmp/_aws_proxy_test.py",
    timeout=90,
)
print(stdout.read().decode(errors="replace"))
c.close()
