#!/usr/bin/env bash
# 在 VPS 网页控制台 / VNC 中粘贴执行（无需本机 SSH）
# 用法: curl -fsSL https://raw.githubusercontent.com/7836246/aws-builder-id/main/deploy/console_install.sh | bash
# 或: bash deploy/vps/console-install.sh
set -euo pipefail

APP_DIR="/opt/aws-builder-id"
REPO_URL="https://github.com/7836246/aws-builder-id.git"

echo "========== AWS Builder ID 控制台安装 =========="

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl wget gnupg ca-certificates \
  python3 python3-pip python3-venv \
  fonts-liberation libnss3 libgbm1 libgtk-3-0 libxss1 xdg-utils

if ! command -v google-chrome >/dev/null 2>&1; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list
  apt-get update -qq
  apt-get install -y -qq google-chrome-stable
fi

if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" pull --ff-only || true
else
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip -q
pip install -r requirements.txt -q

if [[ -f config/config.production.yaml ]]; then
  cp config/config.production.yaml config/config.yaml
fi

# 修复 SSH：写入常见部署公钥（toolan.pem）
AUTH_KEY='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDH73bOZ7OWvjyrb356hsMu15GqBpPOveMfUDYRmKsqmE+f9Jd6wie5uO3G4GoC2SEneQMyJ8O9LbNHEtCPv5wweo7Z00VYamTljTvCayoRJ0/owS0Ksogq/JKtyTj0oG0sd8DIN+YWi+ZsW58uPjrhRIq0Yku55NEbLUJnlFthFf5LXYfJD4geMbdUw9ldKsZmNeorYDVg0i6ak0jZ2zEtr2JTbrfhngct5VefBltLnBAEH2OGQlXes52X4kjUWZTJV5bN90TbxaDZgwdawONeEo7M6sto3gLR3n+YtCUURHZNLlTO4m+t7ld6mkuSPCopPu79Kjfszqx4CV8PcRtf'
mkdir -p /root/.ssh
chmod 700 /root/.ssh
grep -qF "${AUTH_KEY}" /root/.ssh/authorized_keys 2>/dev/null || echo "${AUTH_KEY}" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

chmod +x deploy/vps/server-setup.sh deploy/vps/run-register.sh 2>/dev/null || true
chmod +x deploy/server_setup.sh deploy/run_register.sh 2>/dev/null || true

echo ""
echo "安装完成: ${APP_DIR}"
echo "请编辑 config/config.yaml 填写 email.worker_url 与 email.domain"
echo "试跑: cd ${APP_DIR} && source .venv/bin/activate && python src/runners/main.py"
echo "本机可测试 SSH: ssh -i toolan.pem root@$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
