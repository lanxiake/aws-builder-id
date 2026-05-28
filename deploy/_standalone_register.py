#!/usr/bin/env python3
"""
独立注册脚本：完全绕过项目模块链，直接用标准 Selenium 完成 AWS Builder ID 注册。

不导入 undetected_chromedriver，不注入 CDP 指纹，不依赖项目 config/helpers。
用于排查 main.py 浏览器崩溃是否由 CDP 注入或模块导入引起。
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import paramiko
import yaml

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE = "/opt/aws-builder-id"
PROXY_URL = os.environ.get(
    "PROXY_URL",
    "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443",
)

# 内联的注册脚本，上传到 VPS /tmp/ 后直接运行
REGISTER_SCRIPT = r'''#!/usr/bin/env python3
"""独立 AWS Builder ID 注册脚本 — 纯 Selenium，零 CDP 注入。"""

import email as email_lib
import imaplib
import os
import random
import re
import string
import time
from email import policy
from email.header import decode_header

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# ──────────────────── Gmail 别名工具 ────────────────────

GMAIL_BASE_USER = os.environ.get("GMAIL_BASE_USER", "toojia0510")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "ties zgem pvky ilah")


def _add_random_dots(username):
    chars = list(username)
    result = [chars[0]]
    for c in chars[1:]:
        if random.random() < 0.45:
            result.append(".")
        result.append(c)
    return "".join(result)


def create_gmail_alias():
    """生成 Gmail 别名，返回 (alias_address, tag)。"""
    base = GMAIL_BASE_USER.replace("@gmail.com", "").replace(".", "").lower()
    dotted = _add_random_dots(base)
    tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    alias = f"{dotted}+{tag}@gmail.com"
    print(f"Gmail alias: {alias}")
    return alias, tag


def wait_for_verification_code(alias_address, timeout=180, poll_interval=5):
    """IMAP 轮询 Gmail 收件箱，提取 AWS 验证码。"""
    full_email = f"{GMAIL_BASE_USER.replace('@gmail.com','')}@gmail.com"
    print(f"IMAP polling {full_email} for mail to {alias_address}")
    start = time.time()
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(full_email, GMAIL_APP_PASSWORD)
    except Exception as e:
        print(f"IMAP login failed: {e}")
        return None

    try:
        while time.time() - start < timeout:
            try:
                mail.select("INBOX")
                _, msg_nums = mail.search(None, "(UNSEEN)")
                if not msg_nums or not msg_nums[0]:
                    print(f"  polling... ({int(time.time()-start)}s)", end="\r")
                    time.sleep(poll_interval)
                    continue
                for mid in reversed(msg_nums[0].split()[-10:]):
                    _, data = mail.fetch(mid, "(RFC822)")
                    if not data or not data[0] or not isinstance(data[0], tuple):
                        continue
                    msg = email_lib.message_from_bytes(data[0][1], policy=policy.default)
                    to_f = (msg.get("To") or "").lower()
                    from_f = (msg.get("From") or "").lower()
                    subj = str(msg.get("Subject") or "")
                    if alias_address.lower() not in to_f:
                        continue
                    if "amazon" not in from_f and "aws" not in from_f and "verify" not in subj.lower():
                        continue
                    print(f"\nGot verification email! Subject: {subj}")
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
                    for pat in [r'code[:\s]+(\d{6})', r'\b(\d{6})\b']:
                        m = re.search(pat, subj + " " + body, re.IGNORECASE)
                        if m:
                            print(f"  Verification code: {m.group(1)}")
                            return m.group(1)
            except Exception as e:
                print(f"  IMAP poll error: {e}")
            time.sleep(poll_interval)
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    print(f"Timeout waiting for verification ({timeout}s)")
    return None


# ──────────────────── 浏览器工具 ────────────────────

def human_delay(lo=0.5, hi=2.0):
    if random.random() < 0.15:
        time.sleep(random.uniform(2.5, 4.0))
    time.sleep(random.uniform(lo, hi))


def human_type(element, text):
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.04, 0.12))


def human_click(driver, element):
    try:
        ac = ActionChains(driver)
        ac.move_to_element_with_offset(element, random.randint(-3, 3), random.randint(-3, 3))
        ac.click()
        ac.perform()
    except Exception:
        try:
            element.click()
        except Exception:
            driver.execute_script("arguments[0].click();", element)


# ──────────────────── 注册流程 ────────────────────

def run():
    import tempfile, shutil
    from faker import Faker

    fake = Faker("en_US")
    first_name = fake.first_name()
    last_name = fake.last_name()
    full_name = f"{first_name} {last_name}"

    email_address, tag = create_gmail_alias()
    password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = (
        random.choice(string.ascii_uppercase)
        + random.choice(string.ascii_lowercase)
        + random.choice(string.digits)
        + random.choice("!@#$%^&*")
        + "".join(random.choices(password_chars, k=12))
    )

    print(f"Name: {full_name}")
    print(f"Email: {email_address}")
    print(f"Password: {password}")

    # Chrome options — 极简配置
    user_data_dir = tempfile.mkdtemp(prefix="aws_reg_")
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-hang-monitor")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--lang=en-US")

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    options.add_argument(f"--user-agent={ua}")

    proxy_url = os.environ.get("PROXY_URL", "http://127.0.0.1:18080")
    if proxy_url:
        options.add_argument(f"--proxy-server={proxy_url}")
        print(f"Proxy: {proxy_url}")

    driver_path = "/usr/local/bin/chromedriver" if os.path.exists("/usr/local/bin/chromedriver") else None
    service = Service(executable_path=driver_path) if driver_path else Service()

    print("Launching Chrome ...")
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # 不注入任何 CDP 指纹 — 直接打开页面
        print("Navigating to builder.aws.com/start ...")
        driver.get("https://builder.aws.com/start")
        print("Waiting for page render ...")
        try:
            WebDriverWait(driver, 90).until(lambda d: d.title and "builder" in d.title.lower())
        except Exception:
            pass
        human_delay(3, 5)
        print(f"Title: {driver.title}")
        print(f"URL: {driver.current_url}")

        # Cookie 弹窗
        print("Handling cookie popup ...")
        human_delay(3, 4)
        cookie_closed = False
        for sel in [
            "//button[@id='awsccc-cb-btn-accept']",
            "//button[contains(text(), 'Accept')]",
        ]:
            try:
                btn = driver.find_element(By.XPATH, sel)
                if btn.is_displayed():
                    human_click(driver, btn)
                    cookie_closed = True
                    human_delay(2, 3)
                    break
            except Exception:
                continue
        if not cookie_closed:
            try:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                human_delay(1, 2)
            except Exception as e:
                print(f"ESC failed: {e}")
        print(f"Cookie handled: {cookie_closed}")

        # Sign up with Builder ID
        print("Looking for Sign up button ...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Sign up with Builder')]"))
            )
        except Exception:
            print("  Timeout waiting for signup element")

        human_delay(4, 6)
        original_url = driver.current_url
        signup_clicked = False

        for text in ["Sign up with Builder ID", "Builder ID"]:
            if signup_clicked:
                break
            for el in driver.find_elements(By.XPATH, f"//span[contains(text(), '{text}')]"):
                try:
                    if not el.is_displayed():
                        continue
                    parent = el
                    for _ in range(5):
                        try:
                            parent = parent.find_element(By.XPATH, "./..")
                            if parent.tag_name in ("a", "button"):
                                break
                        except Exception:
                            break
                    human_click(driver, parent)
                    human_delay(2, 3)
                    if driver.current_url != original_url:
                        signup_clicked = True
                        break
                except Exception:
                    continue
            if not signup_clicked:
                for el in driver.find_elements(By.XPATH, f"//*[contains(., '{text}')]"):
                    try:
                        if el.is_displayed() and el.tag_name in ("a", "button", "span", "div"):
                            human_click(driver, el)
                            human_delay(2, 3)
                            if driver.current_url != original_url:
                                signup_clicked = True
                                break
                    except Exception:
                        continue

        print(f"Signup clicked: {signup_clicked}, URL: {driver.current_url}")
        driver.save_screenshot("/tmp/step_signup.png")

        # 填写邮箱
        print(f"Entering email: {email_address}")
        email_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[placeholder="username@example.com"]')
        ))
        email_input.click()
        human_delay(0.3, 0.8)
        email_input.clear()
        human_type(email_input, email_address)
        driver.save_screenshot("/tmp/step_email.png")

        # Continue
        human_delay(1, 2)
        btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="test-primary-button"]')
        ))
        btn.click()
        human_delay(3, 5)
        print(f"After email continue, URL: {driver.current_url}")

        # 填写姓名
        print(f"Entering name: {full_name}")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]')))
        inputs = [el for el in driver.find_elements(By.CSS_SELECTOR, 'input[type="text"]') if el.is_displayed()]
        if len(inputs) >= 2:
            for el, val in zip(inputs[:2], [first_name, last_name]):
                el.click()
                human_delay(0.2, 0.4)
                el.send_keys(Keys.CONTROL + "a")
                el.send_keys(Keys.DELETE)
                human_type(el, val)
                human_delay(0.3, 0.6)
        else:
            inputs[0].click()
            inputs[0].send_keys(Keys.CONTROL + "a")
            inputs[0].send_keys(Keys.DELETE)
            human_type(inputs[0], full_name)
        driver.save_screenshot("/tmp/step_name.png")

        # Continue (name page)
        human_delay(4, 7)
        for sel in [
            (By.XPATH, "//button[contains(., 'Continue')]"),
            (By.CSS_SELECTOR, '[data-testid="test-primary-button"]'),
            (By.XPATH, "//button[@type='submit']"),
        ]:
            try:
                btn = driver.find_element(*sel)
                if btn.is_displayed():
                    human_click(driver, btn)
                    break
            except Exception:
                continue
        human_delay(5, 8)
        print(f"After name continue, URL: {driver.current_url}")
        driver.save_screenshot("/tmp/step_name_continue.png")

        # 等待验证码
        print("Waiting for verification code ...")
        code = wait_for_verification_code(email_address, timeout=180, poll_interval=5)

        if code:
            print(f"Got code: {code}")
            human_delay(4, 6)
            code_input = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'input[type="text"]')
            ))
            code_input.click()
            human_delay(0.5, 1)
            human_type(code_input, code)
            human_delay(1, 2)

            for sel in [
                (By.XPATH, "//button[contains(., 'Verify')]"),
                (By.XPATH, "//button[contains(., 'Continue')]"),
                (By.XPATH, "//button[@type='submit']"),
            ]:
                try:
                    btn = driver.find_element(*sel)
                    if btn.is_displayed():
                        human_click(driver, btn)
                        break
                except Exception:
                    continue
            human_delay(8, 12)
            driver.save_screenshot("/tmp/step_verify.png")
            print(f"After verify, URL: {driver.current_url}")

            # 设置密码
            print("Setting password ...")
            human_delay(5, 8)
            pwd_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
            if pwd_inputs:
                pwd_inputs[0].click()
                human_type(pwd_inputs[0], password)
                if len(pwd_inputs) >= 2:
                    human_delay(0.5, 1)
                    pwd_inputs[1].click()
                    human_type(pwd_inputs[1], password)
                human_delay(1, 2)
                for sel in [
                    (By.XPATH, "//button[contains(., 'Create')]"),
                    (By.XPATH, "//button[contains(., 'Continue')]"),
                    (By.XPATH, "//button[@type='submit']"),
                ]:
                    try:
                        btn = driver.find_element(*sel)
                        if btn.is_displayed():
                            human_click(driver, btn)
                            break
                    except Exception:
                        continue
                human_delay(5, 8)
                driver.save_screenshot("/tmp/step_password.png")
            else:
                print("No password inputs found")
        else:
            print("No verification code received")

        print(f"Final URL: {driver.current_url}")
        print(f"Final Title: {driver.title}")
        driver.save_screenshot("/tmp/final.png")

        import json, datetime
        result = {
            "email": email_address,
            "password": password,
            "name": full_name,
            "final_url": driver.current_url,
            "final_title": driver.title,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open("/tmp/standalone_result.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("Result saved to /tmp/standalone_result.json")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            driver.save_screenshot("/tmp/error.png")
        except Exception:
            pass
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        try:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    run()
'''


def main():
    """上传独立脚本并运行。"""
    _p = urlparse(PROXY_URL)
    _pproxy_remote = (
        f"{_p.hostname}:{_p.port}#{_p.username}:{_p.password}"
        if _p.username
        else f"{_p.hostname}:{_p.port}"
    )

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username="root",
        pkey=paramiko.RSAKey.from_private_key_file(KEY),
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = c.open_sftp()

    # 上传独立脚本
    with sftp.open("/tmp/_standalone_register.py", "w") as f:
        f.write(REGISTER_SCRIPT.replace("\r\n", "\n"))
    print("Uploaded /tmp/_standalone_register.py")

    # 上传 gmail_alias_service.py（独立脚本内联了，但以防万一）
    sftp.close()

    run_sh = f"""#!/bin/bash
set -e
cd /opt/aws-builder-id
source .venv/bin/activate
pip install -q pproxy faker 2>&1 | tail -3

pkill -f '_standalone_register' 2>/dev/null || true
pkill -f pproxy 2>/dev/null || true
pkill -f Xvfb 2>/dev/null || true
sleep 2

# 启动 pproxy
nohup pproxy -l http://127.0.0.1:18080 -r http://{_pproxy_remote} > /tmp/pproxy.log 2>&1 &
sleep 2
echo "pproxy PID=$!"

# 启动 Xvfb
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
sleep 1

echo "===== Running standalone register ====="
export PROXY_URL=http://127.0.0.1:18080
export GMAIL_BASE_USER=toojia0510
export GMAIL_APP_PASSWORD="ties zgem pvky ilah"

# 前台运行以捕获完整输出
timeout 300 python /tmp/_standalone_register.py 2>&1 || true
echo "===== Done ====="
"""

    sftp = c.open_sftp()
    with sftp.open("/tmp/_standalone_run.sh", "w") as f:
        f.write(run_sh.replace("\r\n", "\n"))
    sftp.close()

    print("\nRunning standalone register on VPS ...")
    _, stdout, stderr = c.exec_command(
        "bash /tmp/_standalone_run.sh",
        get_pty=True,
        timeout=600,
    )
    output = stdout.read().decode(errors="replace")
    print(output)
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
