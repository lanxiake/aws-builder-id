import os
import yaml
from pathlib import Path

# 读取配置文件
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path, "r", encoding="utf-8") as f:
    _config = yaml.safe_load(f)

# 邮箱 Provider（vps / gmail_alias）
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "").strip() or _config["email"].get("provider", "vps")

# 邮箱配置（VPS 模式）
EMAIL_WORKER_URL = _config["email"]["worker_url"]
EMAIL_DOMAIN = _config["email"]["domain"]
EMAIL_PREFIX_LENGTH = _config["email"]["prefix_length"]
EMAIL_WAIT_TIMEOUT = _config["email"]["wait_timeout"]
EMAIL_POLL_INTERVAL = _config["email"]["poll_interval"]
EMAIL_ADMIN_PASSWORD = _config["email"].get("admin_password", "")

# Gmail 别名配置
_gmail_cfg = _config["email"].get("gmail", {})
GMAIL_BASE_USER = os.environ.get("GMAIL_BASE_USER", "").strip() or _gmail_cfg.get("base_user", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip() or _gmail_cfg.get("app_password", "")
GMAIL_TAG_LENGTH = int(os.environ.get("GMAIL_TAG_LENGTH", "0") or 0) or int(_gmail_cfg.get("tag_length", 12) or 12)

# 注册完成后是否自动登录验证
_verify_env = os.environ.get("VERIFY_LOGIN_AFTER_REGISTER", "").strip().lower()
if _verify_env in ("1", "true", "yes", "y"):
    VERIFY_LOGIN_AFTER_REGISTER = True
elif _verify_env in ("0", "false", "no", "n"):
    VERIFY_LOGIN_AFTER_REGISTER = False
else:
    VERIFY_LOGIN_AFTER_REGISTER = bool(_config.get("registration", {}).get("verify_login_after_register", True))

# 浏览器配置
HEADLESS = _config["browser"]["headless"]
SLOW_MO = _config["browser"]["slow_mo"]
BROWSER_ENGINE = _config["browser"].get("engine", "uc")

# 地区配置
REGION_CURRENT = _config["region"]["current"]
DEVICE_TYPE = _config["region"].get("device_type", "desktop")
REGION_USE_PROXY = _config["region"].get("use_proxy", False)
REGION_PROXY_MODE = _config["region"].get("proxy_mode", "static")
REGION_PROXY_URL = _config["region"].get("proxy_url", "")
REGION_PROXY_API = _config["region"].get("proxy_api", {})
REGION_PROFILES = _config["region"]["profiles"]



# HTTP 配置
HTTP_TIMEOUT = _config["http"]["timeout"]
