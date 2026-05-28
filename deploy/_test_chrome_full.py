#!/usr/bin/env python3
"""模拟 main.py 的完整 Chrome 配置，定位崩溃原因。"""
import os, sys
import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_SCRIPT = '''#!/usr/bin/env python3
import os, time, random, tempfile, shutil
os.environ.setdefault("DISPLAY", ":97")

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

svc = Service(executable_path="/usr/local/bin/chromedriver")

# 模拟 main.py 的完整参数
user_data_dir = tempfile.mkdtemp(prefix="aws_test_")
print(f"user_data_dir: {user_data_dir}")

opts = Options()
opts.add_argument("--disable-blink-features=AutomationControlled")
resolutions = ["1920,1080", "1366,768", "1536,864", "1440,900", "1280,720"]
opts.add_argument(f"--window-size={random.choice(resolutions)}")
opts.add_argument("--start-maximized")
opts.add_argument("--lang=en-US")
opts.add_argument("--accept-lang=en-US,en;q=0.9")
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
opts.add_argument(f"--user-agent={ua}")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--disable-software-rasterizer")
opts.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
opts.add_argument(f"--user-data-dir={user_data_dir}")
opts.add_argument("--proxy-server=http://127.0.0.1:18080")

print("Creating driver with full main.py options...")
try:
    d = Chrome(service=svc, options=opts)
    print("Driver created OK")
except Exception as e:
    print(f"Driver creation FAILED: {e}")
    shutil.rmtree(user_data_dir, ignore_errors=True)
    exit(1)

# CDP injections (same as main.py)
try:
    cores = random.choice([4, 8, 12, 16])
    memory = random.choice([4, 8, 16, 32])
    js = (
        "Object.defineProperty(navigator, 'hardwareConcurrency', {"
        "  get: () => " + str(cores) + "});"
        "Object.defineProperty(navigator, 'deviceMemory', {"
        "  get: () => " + str(memory) + "});"
        "const gp = WebGLRenderingContext.prototype.getParameter;"
        "WebGLRenderingContext.prototype.getParameter = function(p) {"
        "  if (p === 37445) return 'Intel Inc.';"
        "  if (p === 37446) return 'Intel Iris OpenGL Engine';"
        "  return gp(p);"
        "};"
    )
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})
    d.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "America/New_York"})
    d.execute_cdp_cmd("Emulation.setGeolocationOverride", {
        "latitude": 40.7128, "longitude": -74.0060, "accuracy": 100
    })
    print("CDP injections done")
except Exception as e:
    print(f"CDP injection error: {e}")

# Navigate to AWS
try:
    print("Navigating to AWS...")
    d.get("https://builder.aws.com/start")
    print("Waiting for SPA render...")
    try:
        WebDriverWait(d, 60).until(lambda x: x.title and "builder" in x.title.lower())
    except:
        pass
    time.sleep(4)
    print(f"Title: {d.title}")
    print(f"URL: {d.current_url}")

    # Cookie handling (same as main.py)
    print("Cookie check...")
    time.sleep(3)
    body = d.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.ESCAPE)
    time.sleep(2)
    print(f"After ESC: {d.title}")

    # Sign up button wait
    print("Looking for Sign up button...")
    try:
        WebDriverWait(d, 30).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//*[contains(., 'Sign up with Builder') or contains(., 'Builder ID')]",
            ))
        )
        print("Button found!")
    except:
        print("Button not found within timeout")
    
    time.sleep(3)
    print(f"Still alive. Title: {d.title}")

    # Try to find and click it
    print("Scanning elements...")
    elements = d.find_elements(By.XPATH, "//span[contains(text(), 'Sign up with Builder')]")
    print(f"Found {len(elements)} elements")
    for el in elements:
        if el.is_displayed():
            print(f"  Visible element: {el.text}")

    print("TEST PASSED - Chrome survived full main.py flow!")

except Exception as e:
    print(f"TEST FAILED: {e}")

try:
    d.quit()
except:
    pass
shutil.rmtree(user_data_dir, ignore_errors=True)
'''

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY),
              timeout=30, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_full_test.py", "w") as f:
        f.write(REMOTE_SCRIPT)
    run_sh = """#!/bin/bash
pkill -f 'Xvfb :97' 2>/dev/null || true
pkill -f chromedriver 2>/dev/null || true
pkill -f 'chrome --' 2>/dev/null || true
sleep 2
Xvfb :97 -screen 0 1920x1080x24 >/dev/null 2>&1 &
sleep 2
cd /opt/aws-builder-id
DISPLAY=:97 /opt/aws-builder-id/.venv/bin/python /tmp/_full_test.py 2>&1
pkill -f 'Xvfb :97' 2>/dev/null || true
"""
    with sftp.open("/tmp/_run_full.sh", "w") as f:
        f.write(run_sh)
    sftp.close()
    
    # 后台运行
    c.exec_command("nohup bash /tmp/_run_full.sh > /tmp/full_test.log 2>&1 &", timeout=10)
    print("Test started in background. Waiting 120s...")
    import time
    time.sleep(120)

    # 读取结果
    _, stdout, _ = c.exec_command("cat /tmp/full_test.log", timeout=15)
    print(stdout.read().decode(errors="replace"))
    c.close()

if __name__ == "__main__":
    main()
