"""
CloakBrowser + undetected-chromedriver 启动器。

使用 CloakBrowser 修补过的 Chromium 二进制，配合 UC 隐藏 WebDriver 特征，
用于通过 AWS Builder 等强风控站点的自动化检测。
"""

from __future__ import annotations

import os
import random
import tempfile
from typing import Optional, Tuple


def get_driver_mode() -> str:
    """
    返回驱动模式:
    - 'cloak_uc' : CloakBrowser + undetected-chromedriver
    - 'uc'       : undetected-chromedriver
    - 'uc_plain' : 系统 chromedriver（Selenium 原生），用于规避 undetected 驱动缓存/占用问题
    """
    env = os.environ.get("BROWSER_ENGINE", "").strip().lower()
    if env in ("uc_plain", "standard", "selenium", "chrome_standard"):
        return "uc_plain"
    if env in ("cloak", "cloakbrowser", "1", "true", "yes"):
        return "cloak_uc"
    try:
        from config import BROWSER_ENGINE
        cfg = str(BROWSER_ENGINE).strip().lower()
        if cfg in ("uc_plain", "standard", "selenium", "chrome_standard"):
            return "uc_plain"
        if cfg in ("cloak", "cloakbrowser"):
            return "cloak_uc"
    except ImportError:
        pass
    return "uc"


def is_cloak_enabled() -> bool:
    """是否启用 CloakBrowser 引擎（环境变量 BROWSER_ENGINE=cloak 或 config）。"""
    return get_driver_mode() == "cloak_uc"


def _chromium_version_main() -> int:
    """返回 CloakBrowser 内置 Chromium 主版本号，供 UC 匹配 ChromeDriver。"""
    from cloakbrowser.config import get_chromium_version
    return int(get_chromium_version().split(".")[0])


def build_chrome_options(
    *,
    headless: bool,
    is_mobile: bool,
    locale: str,
    accept_language: str,
    user_agent: str,
    proxy_url: Optional[str] = None,
    user_data_dir: Optional[str] = None,
    use_cloak: bool = True,
    driver_mode: str = "uc",
) -> Tuple:
    """
    构建 Chrome 选项。

    driver_mode='uc_plain' 时使用标准 Selenium Options（避免 uc.ChromeOptions 的隐式行为）。
    返回 (options, proxy_ext_dir)，proxy_ext_dir 需在退出时清理。
    """
    if driver_mode == "uc_plain":
        from selenium.webdriver.chrome.options import Options
        options = Options()
    else:
        import undetected_chromedriver as uc
        options = uc.ChromeOptions()
    proxy_ext_dir = None

    if use_cloak:
        from cloakbrowser.config import get_default_stealth_args
        from cloakbrowser.download import ensure_binary

        options.binary_location = ensure_binary()
        for arg in get_default_stealth_args():
            options.add_argument(arg)
    else:
        options.add_argument("--disable-blink-features=AutomationControlled")

    if headless:
        options.add_argument("--headless=new")

    if is_mobile:
        options.add_argument("--window-size=375,812")
        options.add_argument("--touch-events=enabled")
    else:
        resolutions = ["1366,768", "1280,720"]
        options.add_argument(f"--window-size={random.choice(resolutions)}")

    options.add_argument(f"--lang={locale}")
    options.add_argument(f"--accept-lang={accept_language}")
    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-hang-monitor")
    options.add_argument(
        "--force-webrtc-ip-handling-policy=default_public_interface_only"
    )

    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")

    if proxy_url:
        from helpers.proxy_auth_extension import create_proxy_auth_extension

        if use_cloak:
            # CloakBrowser 二进制与 MV3 代理扩展易冲突，改用内联认证代理
            options.add_argument(f"--proxy-server={proxy_url}")
        else:
            proxy_ext_dir = create_proxy_auth_extension(proxy_url)
            if proxy_ext_dir:
                options.add_argument(f"--load-extension={proxy_ext_dir}")
            else:
                options.add_argument(f"--proxy-server={proxy_url}")

    return options, proxy_ext_dir


def create_uc_driver(
    options,
    user_data_dir: str,
    use_cloak: bool = True,
):
    """
    启动 undetected_chromedriver 实例。

    use_cloak 为 True 时 version_main 与 CloakBrowser Chromium 对齐，且不强制系统 chromedriver。
    """
    import undetected_chromedriver as uc

    version_main = _chromium_version_main() if use_cloak else 148
    driver_path = None
    if not use_cloak and os.path.exists("/usr/local/bin/chromedriver"):
        driver_path = "/usr/local/bin/chromedriver"
    return uc.Chrome(
        options=options,
        user_data_dir=user_data_dir,
        version_main=version_main,
        driver_executable_path=driver_path,
    )


def create_standard_driver(
    options,
    user_data_dir: str,
):
    """
    使用系统 chromedriver（Selenium WebDriver）启动。
    目的：绕开 undetected_chromedriver 的下载/缓存/占用问题。
    """
    from selenium.webdriver import Chrome
    from selenium.webdriver.chrome.service import Service

    driver_path = (
        "/usr/local/bin/chromedriver"
        if os.path.exists("/usr/local/bin/chromedriver")
        else None
    )
    service = Service(executable_path=driver_path) if driver_path else Service()
    # user_data_dir 已在 options 里通过 --user-data-dir 注入
    return Chrome(service=service, options=options)


def resolve_headless(config_headless: bool) -> bool:
    """无 DISPLAY 时强制 headless，避免 CloakBrowser 无法启动。"""
    if config_headless:
        return True
    display = os.environ.get("DISPLAY", "").strip()
    if not display:
        print("⚠️  未检测到 DISPLAY，自动切换 headless 模式")
        return True
    return False


def prepare_user_data_dir() -> str:
    """创建独立临时用户目录，避免 Cookie/缓存污染。"""
    return tempfile.mkdtemp(prefix=f"aws_reg_{random.randint(1000, 9999)}_")
