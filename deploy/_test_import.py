#!/usr/bin/env python3
"""检查 main.py 导入是否正常。"""
import os, sys
import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_SCRIPT = '''#!/usr/bin/env python3
import sys, os
sys.path.insert(0, "/opt/aws-builder-id/src")
os.environ["DISPLAY"] = ":99"
os.environ["BROWSER_ENGINE"] = "uc_plain"
os.environ["EMAIL_PROVIDER"] = "gmail_alias"

print("Step 1: Testing imports...")
try:
    from config import HEADLESS, SLOW_MO, EMAIL_PROVIDER
    print(f"  config OK: EMAIL_PROVIDER={EMAIL_PROVIDER}")
except Exception as e:
    print(f"  config FAILED: {e}")

try:
    from services.gmail_alias_service import create_gmail_alias_email
    print("  gmail_alias_service OK")
except Exception as e:
    print(f"  gmail_alias_service FAILED: {e}")

try:
    from helpers.cloak_driver import build_chrome_options, create_standard_driver, get_driver_mode
    dm = get_driver_mode()
    print(f"  cloak_driver OK: driver_mode={dm}")
except Exception as e:
    print(f"  cloak_driver FAILED: {e}")

print("Step 2: Testing main.py import...")
try:
    from runners import main as main_mod
    print(f"  main module OK, has run={hasattr(main_mod, 'run')}")
except Exception as e:
    print(f"  main import FAILED: {e}")
    import traceback
    traceback.print_exc()

print("Step 3: Testing Chrome launch...")
try:
    from helpers.cloak_driver import build_chrome_options, create_standard_driver, prepare_user_data_dir
    user_data_dir = prepare_user_data_dir()
    options, ext = build_chrome_options(
        headless=False,
        is_mobile=False,
        locale="en-US",
        accept_language="en-US,en;q=0.9",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        proxy_url="http://127.0.0.1:18080",
        user_data_dir=user_data_dir,
        use_cloak=False,
        driver_mode="uc_plain",
    )
    print(f"  Options type: {type(options).__name__}")
    print(f"  Options args: {options.arguments}")
    
    d = create_standard_driver(options, user_data_dir)
    print("  Driver created OK")
    d.get("https://builder.aws.com/start")
    import time
    time.sleep(10)
    print(f"  Title: {d.title}")
    body = d.find_element_by_tag_name("body") if hasattr(d, "find_element_by_tag_name") else None
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    body = d.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.ESCAPE)
    time.sleep(3)
    print(f"  After ESC - Title: {d.title}")
    time.sleep(5)
    print(f"  After 5s - Title: {d.title}")
    d.quit()
    print("  TEST PASSED")
except Exception as e:
    print(f"  Chrome test FAILED: {e}")
    import traceback
    traceback.print_exc()
    try: d.quit()
    except: pass
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY),
              timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_import_test.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    run_sh = """#!/bin/bash
Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 &
sleep 2
cd /opt/aws-builder-id
DISPLAY=:99 /opt/aws-builder-id/.venv/bin/python /tmp/_import_test.py 2>&1
"""
    with sftp.open("/tmp/_run_import.sh", "w") as f:
        f.write(run_sh)
    sftp.close()

    c.exec_command("nohup bash /tmp/_run_import.sh > /tmp/import_test.log 2>&1 &", timeout=10)
    print("Started. Waiting 90s...")
    import time
    time.sleep(90)

    c2 = paramiko.SSHClient()
    c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c2.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY),
               timeout=30, allow_agent=False, look_for_keys=False)
    _, stdout, _ = c2.exec_command("cat /tmp/import_test.log", timeout=15)
    print(stdout.read().decode(errors="replace"))
    c2.close()

if __name__ == "__main__":
    main()
