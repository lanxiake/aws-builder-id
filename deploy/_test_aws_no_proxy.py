#!/usr/bin/env python3
"""测试不走代理、带代理扩展能否打开 AWS 页面。"""
import os, sys
from pathlib import Path
import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_SCRIPT = r"""#!/usr/bin/env python3
import os, time
os.environ.setdefault("DISPLAY", ":97")

import undetected_chromedriver as uc

# ====== Test 1: No proxy ======
print("=== Test 1: No proxy ===")
opts = uc.ChromeOptions()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
try:
    d = uc.Chrome(options=opts, version_main=148, driver_executable_path="/usr/local/bin/chromedriver")
    print("Driver OK")
    d.get("https://builder.aws.com/start")
    time.sleep(10)
    print("Title:", d.title)
    print("URL:", d.current_url)
    d.quit()
    print("Test 1 PASSED")
except Exception as e:
    print(f"Test 1 FAILED: {e}")

time.sleep(2)

# ====== Test 2: With --proxy-server (inline, no auth ext) ======
print()
print("=== Test 2: --proxy-server (full URL with auth) ===")
PROXY = "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443"
opts2 = uc.ChromeOptions()
opts2.add_argument("--no-sandbox")
opts2.add_argument("--disable-dev-shm-usage")
opts2.add_argument("--disable-gpu")
opts2.add_argument(f"--proxy-server={PROXY}")
try:
    d2 = uc.Chrome(options=opts2, version_main=148, driver_executable_path="/usr/local/bin/chromedriver")
    print("Driver OK")
    d2.get("https://httpbin.org/ip")
    time.sleep(5)
    print("Title:", d2.title)
    src = d2.page_source
    print("Body:", src[:300])
    d2.get("https://builder.aws.com/start")
    time.sleep(10)
    print("AWS Title:", d2.title)
    print("AWS URL:", d2.current_url)
    d2.quit()
    print("Test 2 PASSED")
except Exception as e:
    print(f"Test 2 FAILED: {e}")

# ====== Test 3: proxy-server without auth ======
print()
print("=== Test 3: --proxy-server (no auth, expect 407) ===")
opts3 = uc.ChromeOptions()
opts3.add_argument("--no-sandbox")
opts3.add_argument("--disable-dev-shm-usage")
opts3.add_argument("--disable-gpu")
opts3.add_argument("--proxy-server=http://70.39.242.6:443")
try:
    d3 = uc.Chrome(options=opts3, version_main=148, driver_executable_path="/usr/local/bin/chromedriver")
    print("Driver OK")
    d3.get("https://httpbin.org/ip")
    time.sleep(5)
    print("Title:", d3.title)
    print("Body:", d3.page_source[:300])
    d3.quit()
    print("Test 3 DONE")
except Exception as e:
    print(f"Test 3 FAILED: {e}")
"""

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY),
              timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_aws_test.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    run_sh = """#!/bin/bash
set -e
pkill -f 'Xvfb :97' 2>/dev/null || true
pkill -f chromedriver 2>/dev/null || true
pkill -f chrome 2>/dev/null || true
sleep 2
Xvfb :97 -screen 0 1280x720x24 &>/dev/null &
sleep 2
cd /opt/aws-builder-id
DISPLAY=:97 /opt/aws-builder-id/.venv/bin/python /tmp/_aws_test.py 2>&1
pkill -f 'Xvfb :97' 2>/dev/null || true
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_run_aws_test.sh", "w") as f:
        f.write(run_sh)
    sftp.close()

    _, stdout, stderr = c.exec_command("bash /tmp/_run_aws_test.sh", get_pty=True, timeout=300)
    out = stdout.read().decode(errors="replace")
    print(out)
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    c.close()

if __name__ == "__main__":
    main()
