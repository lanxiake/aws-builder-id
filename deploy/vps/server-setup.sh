#!/usr/bin/env bash
# 在德国 VPS 上安装 AWS Builder ID 注册工具运行环境（Ubuntu 22.04/24.04）
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aws-builder-id}"
REPO_URL="${REPO_URL:-https://github.com/7836246/aws-builder-id.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "==> 更新系统包..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  git curl wget gnupg ca-certificates \
  python3 python3-pip python3-venv \
  fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
  libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 \
  libgbm1 libgcc1 libglib2.0-0 libgtk-3-0 libnspr4 libnss3 \
  libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 \
  libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 \
  libxi6 libxrandr2 libxrender1 libxss1 libxtst6 xdg-utils

echo "==> 安装 Google Chrome..."
if ! command -v google-chrome >/dev/null 2>&1; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list
  apt-get update -qq
  apt-get install -y -qq google-chrome-stable
fi

echo "==> 克隆/更新项目到 ${APP_DIR}..."
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" pull --ff-only
else
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"

echo "==> 创建 Python 虚拟环境..."
${PYTHON_BIN} -m venv .venv
source .venv/bin/activate
pip install -U pip wheel
pip install -r requirements.txt

echo "==> 应用生产配置（若存在）..."
if [[ -f config/config.production.yaml ]]; then
  cp config/config.production.yaml config/config.yaml
  echo "已使用 config/config.production.yaml"
else
  echo "警告: 未找到 config/config.production.yaml，请手动编辑 config/config.yaml"
fi

echo "==> 切换到德国地区、关闭代理（VPS 在德国可直接用本机 IP）..."
${PYTHON_BIN} scripts/switch_region.py germany || true
${PYTHON_BIN} scripts/disable_proxy.py || true

mkdir -p logs data
chmod +x deploy/vps/run-register.sh deploy/services/vps-email/*.sh 2>/dev/null || true

if [[ "${INSTALL_VPS_EMAIL:-1}" == "1" ]] && [[ -f deploy/services/vps-email/install.sh ]]; then
  echo "==> 安装 VPS 临时邮箱 (mx1.metoolbot.top)..."
  bash deploy/services/vps-email/install.sh
fi

echo ""
echo "安装完成。下一步:"
echo "  1. DNSPod: A 记录 mx1 -> 本机公网 IP; MX @ -> mx1.metoolbot.top (10)"
echo "  2. 测试邮箱: curl -s https://mx1.metoolbot.top/api/health"
echo "  3. 试跑: cd ${APP_DIR} && source .venv/bin/activate && python src/runners/main.py"
