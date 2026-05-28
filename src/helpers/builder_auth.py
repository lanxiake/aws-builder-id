"""
AWS Builder ID 通用页面操作：Cookie、登录/注册入口、邮箱、验证码、密码。
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def human_delay(min_sec=0.5, max_sec=2.0):
    """随机等待（由调用方传入或在此模块内简单实现）。"""
    import random
    time.sleep(random.uniform(min_sec, max_sec))


def dismiss_cookie_banner(driver) -> bool:
    """尝试关闭 Cookie 弹窗。"""
    human_delay(2, 3)
    for selector in [
        "//button[@id='awsccc-cb-btn-accept']",
        "//button[contains(text(), 'Accept')]",
        "//button[contains(@class, 'awsccc')]",
    ]:
        try:
            btn = driver.find_element(By.XPATH, selector)
            if btn.is_displayed():
                btn.click()
                human_delay(1, 2)
                return True
        except Exception:
            continue
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        human_delay(0.5, 1)
    except Exception:
        pass
    return False


def click_builder_entry(driver, wait: WebDriverWait, action: str = "signup") -> bool:
    """
    点击 Builder ID 入口。

    action: signup | signin
    """
    if action == "signin":
        key_texts = [
            "Sign in with Builder ID",
            "Sign in with your Builder ID",
            "Mit Builder-ID anmelden",
            "Builder ID でサインイン",
            "Sign in",
        ]
    else:
        key_texts = [
            "Sign up with Builder ID",
            "Mit Builder-ID anmelden",
            "Builder ID",
            "Builder-ID",
        ]

    human_delay(3, 5)
    original_url = driver.current_url
    for text in key_texts:
        for xpath in (
            f"//span[contains(text(), '{text}')]",
            f"//*[contains(., '{text}')]",
        ):
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if not el.is_displayed():
                        continue
                    target = el
                    if el.tag_name not in ("a", "button"):
                        parent = el
                        for _ in range(5):
                            try:
                                parent = parent.find_element(By.XPATH, "./..")
                                if parent.tag_name in ("a", "button"):
                                    target = parent
                                    break
                            except Exception:
                                break
                    target.click()
                    human_delay(2, 4)
                    if driver.current_url != original_url:
                        return True
                except Exception:
                    continue
    return driver.current_url != original_url


def fill_email_and_continue(driver, wait: WebDriverWait, email: str, human_type, human_click) -> bool:
    """填写邮箱并点击继续。"""
    try:
        email_input = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[type="email"], input[placeholder*="example.com"], input[name="email"]')
            )
        )
        email_input.click()
        human_delay(0.3, 0.6)
        email_input.clear()
        human_type(email_input, email)
        human_delay(0.8, 1.5)
        for sel in [
            (By.CSS_SELECTOR, '[data-testid="test-primary-button"]'),
            (By.XPATH, "//button[contains(., 'Continue')]"),
            (By.XPATH, "//button[@type='submit']"),
        ]:
            try:
                btn = driver.find_element(*sel)
                if btn.is_displayed():
                    human_click(driver, btn)
                    human_delay(3, 5)
                    return True
            except Exception:
                continue
    except Exception as e:
        print(f"   填写邮箱失败: {e}")
    return False


def fill_password_and_continue(
    driver,
    wait: WebDriverWait,
    password: str,
    human_type,
    human_click,
    *,
    submit_labels: Optional[list] = None,
) -> bool:
    """填写密码（含确认框）并提交。"""
    submit_labels = submit_labels or ["Continue", "Sign in", "Create AWS Builder ID", "Verify"]
    try:
        pwd_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
        visible = [el for el in pwd_inputs if el.is_displayed()]
        if not visible:
            return False
        visible[0].click()
        human_type(visible[0], password)
        if len(visible) >= 2:
            human_delay(0.4, 0.8)
            visible[1].click()
            human_type(visible[1], password)
        human_delay(0.8, 1.5)
        for label in submit_labels:
            try:
                btn = driver.find_element(By.XPATH, f"//button[contains(., '{label}')]")
                if btn.is_displayed():
                    human_click(driver, btn)
                    human_delay(4, 7)
                    return True
            except Exception:
                continue
        visible[0].send_keys(Keys.ENTER)
        human_delay(4, 7)
        return True
    except Exception as e:
        print(f"   填写密码失败: {e}")
    return False


def fill_otp_if_present(
    driver,
    wait: WebDriverWait,
    code: str,
    human_type,
    human_click,
) -> bool:
    """若页面有验证码输入框则填写并提交。"""
    try:
        code_input = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    'input[placeholder*="digit"], input[autocomplete="one-time-code"], input[type="text"]',
                )
            )
        )
        if not code_input.is_displayed():
            return False
        code_input.click()
        human_delay(0.3, 0.6)
        human_type(code_input, code)
        human_delay(0.8, 1.2)
        for xpath in [
            "//button[contains(., 'Verify')]",
            "//button[contains(., 'Continue')]",
            "//button[@type='submit']",
        ]:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    human_click(driver, btn)
                    human_delay(5, 8)
                    return True
            except Exception:
                continue
        code_input.send_keys(Keys.ENTER)
        human_delay(5, 8)
        return True
    except Exception:
        return False


def fetch_verification_code(
    email_address: str,
    email_provider: str,
    jwt_token: str = "",
    *,
    purpose: str = "any",
) -> Optional[str]:
    """按 Provider 拉取验证码（注册/登录通用）。"""
    if email_provider == "gmail_alias":
        from services.gmail_alias_service import wait_for_verification_from_gmail
        return wait_for_verification_from_gmail(
            alias_address=email_address,
            timeout=int(os.environ.get("EMAIL_WAIT_TIMEOUT", "180")),
            poll_interval=int(os.environ.get("EMAIL_POLL_INTERVAL", "5")),
            purpose=purpose,
        )
    if email_provider == "outlook" or jwt_token == "OUTLOOK_API":
        return None
    from services.email_service import wait_for_verification_email
    return wait_for_verification_email(jwt_token)


def try_complete_otp_step(
    driver,
    wait: WebDriverWait,
    email_address: str,
    email_provider: str,
    jwt_token: str,
    human_type,
    human_click,
    *,
    purpose: str = "any",
) -> bool:
    """检测 OTP 页并自动收信填码。"""
    human_delay(2, 4)
    url = driver.current_url.lower()
    title = (driver.title or "").lower()
    needs_otp = (
        "verify" in url
        or "otp" in url
        or "code" in url
        or "verify" in title
        or "digit" in driver.page_source.lower()[:8000]
    )
    if not needs_otp:
        return False

    print(f"📨 检测到验证码步骤 (purpose={purpose})，等待邮件...")
    code = fetch_verification_code(
        email_address, email_provider, jwt_token, purpose=purpose
    )
    if not code:
        print("❌ 未收到验证码")
        return False
    print(f"✅ 验证码: {code}")
    return fill_otp_if_present(driver, wait, code, human_type, human_click)


def is_logged_in_to_builder(driver) -> bool:
    """根据 URL/页面粗判是否已进入 Builder 已登录态。"""
    url = (driver.current_url or "").lower()
    title = (driver.title or "").lower()
    if "builder.aws.com" in url and "signin" not in url and "login" not in url:
        if "start" in url or "builder center" in title or "aws builder" in title:
            return True
    page = driver.page_source.lower()[:12000]
    if "sign out" in page or "sign-out" in page or "log out" in page:
        return True
    if "my profile" in page and "sign in with builder" not in page:
        return True
    return False


def sign_out_if_possible(driver) -> None:
    """尝试退出登录，便于后续登录验证。"""
    for text in ("Sign out", "Log out", "Abmelden", "サインアウト"):
        try:
            el = driver.find_element(By.XPATH, f"//*[contains(., '{text}')]")
            if el.is_displayed():
                el.click()
                human_delay(3, 5)
                return
        except Exception:
            continue


def verify_account_login(
    driver,
    wait: WebDriverWait,
    email: str,
    password: str,
    email_provider: str,
    jwt_token: str,
    human_delay_fn: Callable,
    human_type,
    human_click,
) -> bool:
    """
    注册完成后执行登录验证：退出 → 重新 Sign in → 邮箱/密码/OTP → 确认可进入 Builder。
    """
    print("\n" + "=" * 50)
    print("🔐 开始登录验证（确认账号可用）")
    print("=" * 50)

    sign_out_if_possible(driver)
    human_delay_fn(2, 3)

    driver.get("https://builder.aws.com/start")
    human_delay_fn(3, 5)
    try:
        WebDriverWait(driver, 60).until(
            lambda d: d.title and "builder" in d.title.lower()
        )
    except Exception:
        pass

    dismiss_cookie_banner(driver)

    if not click_builder_entry(driver, wait, action="signin"):
        print("⚠️ 未找到 Sign in 入口，尝试 Sign up 同页入口...")
        click_builder_entry(driver, wait, action="signup")

    human_delay_fn(2, 4)
    if not fill_email_and_continue(driver, wait, email, human_type, human_click):
        print("❌ 登录验证：填写邮箱失败")
        driver.save_screenshot("login_verify_email_fail.png")
        return False

    human_delay_fn(3, 5)
    try_complete_otp_step(
        driver, wait, email, email_provider, jwt_token,
        human_type, human_click, purpose="login",
    )

    human_delay_fn(2, 4)
    if driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]'):
        fill_password_and_continue(
            driver, wait, password, human_type, human_click,
            submit_labels=["Sign in", "Continue", "Verify"],
        )
    else:
        try_complete_otp_step(
            driver, wait, email, email_provider, jwt_token,
            human_type, human_click, purpose="login",
        )

    human_delay_fn(5, 8)
    driver.save_screenshot("login_verify_result.png")
    ok = is_logged_in_to_builder(driver)
    print(f"{'✅' if ok else '❌'} 登录验证结果: logged_in={ok}")
    print(f"   URL: {driver.current_url}")
    print(f"   Title: {driver.title}")
    return ok
