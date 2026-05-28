"""deploy 目录路径常量，供 remote 下 Python 脚本引用。"""
from pathlib import Path

# deploy/
DEPLOY_ROOT = Path(__file__).resolve().parents[2]
# deploy/services/vps-email/
VPS_EMAIL_SRC = DEPLOY_ROOT / "services" / "vps-email"
# deploy/vps/
VPS_SCRIPTS = DEPLOY_ROOT / "vps"
INSTALL_EMAIL_SH = VPS_SCRIPTS / "install-email-server.sh"

# 上传到 VPS 独立邮箱栈时的暂存目录名（与 tar 包内布局一致）
REMOTE_EMAIL_STAGING = "vps_email"
