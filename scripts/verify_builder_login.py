#!/usr/bin/env python3
"""
对已注册账号执行 Builder ID 登录验证（含邮箱 OTP）。

用法:
  python scripts/verify_builder_login.py --email xxx@gmail.com --password 'xxx'
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from selenium.webdriver.support.ui import WebDriverWait

from config import EMAIL_PROVIDER, HEADLESS, REGION_CURRENT
from helpers.builder_auth import dismiss_cookie_banner, verify_account_login
from helpers.cloak_driver import (
    build_chrome_options,
    create_standard_driver,
    get_driver_mode,
    prepare_user_data_dir,
    resolve_headless,
)
from helpers.utils import (
    get_accept_language_for_region,
    get_locale_for_region,
    get_user_agent_for_region,
    is_mobile,
)
from managers.proxy_manager import proxy_manager


def _human_delay(lo=0.5, hi=2.0):
    import random
    import time
    time.sleep(random.uniform(lo, hi))


def _human_type(el, text):
    import random
    import time
    for ch in text:
        el.send_keys(ch)
        time.sleep(random.uniform(0.04, 0.12))


def _human_click(driver, el):
    from helpers.builder_auth import human_click as _hc
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        import random
        ac = ActionChains(driver)
        ac.move_to_element_with_offset(el, random.randint(-3, 3), random.randint(-3, 3))
        ac.click()
        ac.perform()
    except Exception:
        try:
            el.click()
        except Exception:
            driver.execute_script("arguments[0].click();", el)


def main() -> int:
    """启动浏览器并执行登录验证。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    proxy_url = proxy_manager.get_proxy() if proxy_manager.use_proxy else None
    user_data_dir = prepare_user_data_dir()
    options, _ = build_chrome_options(
        headless=resolve_headless(HEADLESS),
        is_mobile=is_mobile(),
        locale=get_locale_for_region(REGION_CURRENT),
        accept_language=get_accept_language_for_region(REGION_CURRENT),
        user_agent=get_user_agent_for_region(REGION_CURRENT),
        proxy_url=proxy_url,
        user_data_dir=user_data_dir,
        use_cloak=False,
        driver_mode=get_driver_mode(),
    )
    driver = create_standard_driver(options, user_data_dir)
    wait = WebDriverWait(driver, 30)
    try:
        ok = verify_account_login(
            driver,
            wait,
            args.email,
            args.password,
            EMAIL_PROVIDER,
            "",
            _human_delay,
            _human_type,
            _human_click,
        )
        return 0 if ok else 1
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
