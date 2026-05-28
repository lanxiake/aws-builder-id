#!/usr/bin/env python3
"""测试 CDP 指纹注入是否导致 Chrome 崩溃。"""
import os, sys
import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_SCRIPT = '''#!/usr/bin/env python3
import os, time, random
os.environ.setdefault("DISPLAY", ":97")

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--disable-software-rasterizer")
opts.add_argument("--window-size=1280,720")
opts.add_argument("--proxy-server=http://127.0.0.1:18080")
opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

svc = Service(executable_path="/usr/local/bin/chromedriver")

# ====== Test A: Without CDP scripts ======
print("=== Test A: No CDP injection ===")
d = Chrome(service=svc, options=opts)
try:
    d.get("https://builder.aws.com/start")
    time.sleep(10)
    print(f"  Title: {d.title}")
    print(f"  URL: {d.current_url}")
    body = d.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.ESCAPE)
    time.sleep(2)
    print(f"  After ESC - Title: {d.title}")
    time.sleep(5)
    body = d.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.ESCAPE)
    time.sleep(2)
    print(f"  Still alive after 2nd ESC")
    d.quit()
    print("  Test A PASSED")
except Exception as e:
    print(f"  Test A FAILED: {e}")
    try: d.quit()
    except: pass

time.sleep(3)

# ====== Test B: With CDP fingerprint injection ======
print()
print("=== Test B: With CDP fingerprint injection ===")
d2 = Chrome(service=svc, options=opts)
try:
    cores = random.choice([4, 8, 12, 16])
    memory = random.choice([4, 8, 16, 32])
    js_code = (
        "Object.defineProperty(navigator, \'hardwareConcurrency\', {"
        "  get: () => " + str(cores) +
        "});"
        "Object.defineProperty(navigator, \'deviceMemory\', {"
        "  get: () => " + str(memory) +
        "});"
        "const getParameter = WebGLRenderingContext.prototype.getParameter;"
        "WebGLRenderingContext.prototype.getParameter = function(parameter) {"
        "  if (parameter === 37445) { return \'Intel Inc.\'; }"
        "  if (parameter === 37446) { return \'Intel Iris OpenGL Engine\'; }"
        "  return getParameter(parameter);"
        "};"
    )
    d2.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js_code})
    d2.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "America/New_York"})
    d2.execute_cdp_cmd("Emulation.setGeolocationOverride", {
        "latitude": 40.7128, "longitude": -74.0060, "accuracy": 100
    })
    print("  CDP injected")

    d2.get("https://builder.aws.com/start")
    time.sleep(10)
    print(f"  Title: {d2.title}")
    print(f"  URL: {d2.current_url}")
    body = d2.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.ESCAPE)
    time.sleep(2)
    print(f"  After ESC - Title: {d2.title}")
    time.sleep(5)
    body = d2.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.ESCAPE)
    time.sleep(2)
    print(f"  Still alive after 2nd ESC")
    d2.quit()
    print("  Test B PASSED")
except Exception as e:
    print(f"  Test B FAILED: {e}")
    try: d2.quit()
    except: pass
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY),
              timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_cdp_test.py", "w") as f:
        f.write(REMOTE_SCRIPT)

    run_sh = """#!/bin/bash
pkill -f 'Xvfb :97' 2>/dev/null || true
sleep 1
Xvfb :97 -screen 0 1280x720x24 >/dev/null 2>&1 &
sleep 2
cd /opt/aws-builder-id
DISPLAY=:97 /opt/aws-builder-id/.venv/bin/python /tmp/_cdp_test.py > /tmp/cdp_out.log 2>&1
echo EXIT=$?
cat /tmp/cdp_out.log
pkill -f 'Xvfb :97' 2>/dev/null || true
"""
    with sftp.open("/tmp/_run_cdp.sh", "w") as f:
        f.write(run_sh)
    sftp.close()

    _, stdout, stderr = c.exec_command("bash /tmp/_run_cdp.sh", timeout=300)
    out = stdout.read().decode(errors="replace")
    print(out if out else "(empty)")
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    c.close()

if __name__ == "__main__":
    main()
