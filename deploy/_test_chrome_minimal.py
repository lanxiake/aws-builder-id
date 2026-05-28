#!/usr/bin/env python3
"""最小化 Chrome 启动测试（诊断 VPS 上浏览器崩溃）。"""

import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

TEST_SCRIPT = r"""#!/usr/bin/env python3
import undetected_chromedriver as uc
import time, os

os.environ.setdefault("DISPLAY", ":98")

opts = uc.ChromeOptions()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--disable-extensions")
print("Creating UC driver (v148)...")
try:
    d = uc.Chrome(options=opts, version_main=148, driver_executable_path="/usr/local/bin/chromedriver")
    print("Driver created OK")
    d.get("https://httpbin.org/ip")
    time.sleep(3)
    print("Title:", d.title)
    print("Body:", d.page_source[:300])
    d.quit()
    print("SUCCESS with UC")
except Exception as e:
    print(f"UC FAILED: {e}")

print()
print("--- Testing with plain Selenium ---")
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
opts2 = ChromeOptions()
opts2.add_argument("--no-sandbox")
opts2.add_argument("--disable-dev-shm-usage")
opts2.add_argument("--disable-gpu")
opts2.add_argument("--disable-extensions")
try:
    svc = Service(executable_path="/usr/local/bin/chromedriver")
    d2 = Chrome(service=svc, options=opts2)
    print("Selenium driver created OK")
    d2.get("https://httpbin.org/ip")
    time.sleep(3)
    print("Title:", d2.title)
    print("Body:", d2.page_source[:300])
    d2.quit()
    print("SUCCESS with Selenium")
except Exception as e:
    print(f"Selenium FAILED: {e}")
"""

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY), timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_chrome_test.py", "w") as f:
        f.write(TEST_SCRIPT)
    sftp.close()

    cmd = """
pkill -f 'Xvfb :98' 2>/dev/null; sleep 1
Xvfb :98 -screen 0 1280x720x24 &>/dev/null &
sleep 1
cd /opt/aws-builder-id && source .venv/bin/activate
DISPLAY=:98 python /tmp/_chrome_test.py
pkill -f 'Xvfb :98' 2>/dev/null
"""
    _, stdout, stderr = c.exec_command(cmd, get_pty=True, timeout=120)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    c.close()

if __name__ == "__main__":
    main()
