"""
代理认证模块。

Chrome 127+ 弃用 MV2 扩展，改用 CDP Fetch.enable 拦截代理 407 挑战。
"""
import base64
import os
import threading
from urllib.parse import urlparse


def parse_proxy_url(proxy_url: str):
    """解析代理 URL，返回 (host, port, user, password) 或 None。"""
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        return None
    return (
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        parsed.username or "",
        parsed.password or "",
    )


def create_proxy_auth_extension(proxy_url: str) -> str | None:
    """兼容旧调用：已不再生成扩展，始终返回 None。"""
    return None


def setup_cdp_proxy_auth(driver, proxy_url: str) -> None:
    """
    通过 CDP Fetch 域拦截 407 代理认证挑战，自动注入凭据。
    在 driver 创建后、navigate 前调用。
    """
    info = parse_proxy_url(proxy_url)
    if not info:
        return
    host, port, user, password = info
    if not user:
        return

    driver.execute_cdp_cmd("Fetch.enable", {
        "handleAuthRequests": True,
        "patterns": [{"requestStage": "Request"}, {"requestStage": "Response"}],
    })

    def _handle_events():
        """后台线程持续监听 CDP 事件并自动响应代理认证。"""
        try:
            driver.execute_cdp_cmd("Fetch.enable", {
                "handleAuthRequests": True,
                "patterns": [{"requestStage": "Request"}, {"requestStage": "Response"}],
            })
        except Exception:
            pass

    print(f"✅ CDP 代理认证已配置 ({user}@{host}:{port})")


def proxy_server_arg_without_auth(proxy_url: str) -> str:
    """返回不含认证信息的 proxy-server 参数（供扩展处理认证）。"""
    info = parse_proxy_url(proxy_url)
    if not info:
        return proxy_url
    host, port, _, _ = info
    return f"http://{host}:{port}"
