#!/usr/bin/env bash
# 仅部署临时邮箱服务（mx1.metoolbot.top + metoolbot.top 收信）
# 在 VPS 上以 root 执行: bash install-email-server.sh
# tar 包内仍为 install_email_server.sh（兼容）
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/temp-email}"
EMAIL_DOMAIN="${EMAIL_DOMAIN:-metoolbot.top}"
API_HOSTNAME="${API_HOSTNAME:-mx1.metoolbot.top}"
API_PORT="${EMAIL_API_PORT:-18787}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> 安装系统依赖..."
export DEBIAN_FRONTEND=noninteractive
echo "postfix postfix/mailname string ${API_HOSTNAME}" | debconf-set-selections
echo "postfix postfix/main_mailer_type string 'Internet Site'" | debconf-set-selections
apt-get update -qq
apt-get install -y -qq postfix postfix-pcre nginx certbot python3-certbot-nginx \
  python3 python3-pip python3-venv openssl ufw

mkdir -p "${APP_DIR}/deploy/vps_email" "${APP_DIR}/data"
SRC_DIR=""
if [[ -f "${SCRIPT_DIR}/vps_email/app.py" ]]; then
  SRC_DIR="${SCRIPT_DIR}/vps_email"
elif [[ -f "${SCRIPT_DIR}/../services/vps-email/app.py" ]]; then
  SRC_DIR="$(cd "${SCRIPT_DIR}/../services/vps-email" && pwd)"
else
  echo "错误: 未找到邮箱源码（vps_email/ 或 services/vps-email/）"
  exit 1
fi
cp -f "${SRC_DIR}/app.py" "${APP_DIR}/deploy/vps_email/app.py"
cp -f "${SRC_DIR}/postfix_pipe.sh" "${APP_DIR}/deploy/vps_email/postfix_pipe.sh"
cp -f "${SRC_DIR}/requirements.txt" "${APP_DIR}/deploy/vps_email/requirements.txt"
if [[ -d "${SRC_DIR}/static" ]]; then
  mkdir -p "${APP_DIR}/deploy/vps_email/static"
  cp -rf "${SRC_DIR}/static/"* "${APP_DIR}/deploy/vps_email/static/"
fi

echo "==> Python 虚拟环境..."
python3 -m venv "${APP_DIR}/.venv"
# shellcheck source=/dev/null
source "${APP_DIR}/.venv/bin/activate"
pip install -q -U pip
pip install -q -r "${APP_DIR}/deploy/vps_email/requirements.txt"
chmod +x "${APP_DIR}/deploy/vps_email/postfix_pipe.sh"

echo "==> Postfix 虚拟域 ${EMAIL_DOMAIN}..."
postconf -e "myhostname = ${API_HOSTNAME}"
postconf -e "mydestination ="
postconf -e "inet_interfaces = all"
postconf -e "virtual_mailbox_domains = ${EMAIL_DOMAIN}"
postconf -e "virtual_mailbox_maps = regexp:/etc/postfix/virtual_mailbox_regexp"
postconf -e "virtual_transport = tempmail:"
DOMAIN_ESC="${EMAIL_DOMAIN//./\\.}"
echo "/.*@${DOMAIN_ESC}\$/  OK" > /etc/postfix/virtual_mailbox_regexp
PIPE_SCRIPT="${APP_DIR}/deploy/vps_email/postfix_pipe.sh"
if ! grep -q "^tempmail" /etc/postfix/master 2>/dev/null; then
  cat >> /etc/postfix/master <<EOF

tempmail   unix  -       n       n       -       -       pipe
  flags=FR user=nobody argv=${PIPE_SCRIPT} \${recipient}
EOF
fi
chmod 777 "${APP_DIR}/data"
chmod +x "${APP_DIR}/deploy/vps_email/postfix_pipe.sh"
systemctl enable postfix
systemctl restart postfix

echo "==> systemd temp-email-api..."
cat > /etc/systemd/system/temp-email-api.service <<EOF
[Unit]
Description=Temp Email API
After=network.target

[Service]
Type=simple
Environment=APP_DIR=${APP_DIR}
Environment=EMAIL_DOMAIN=${EMAIL_DOMAIN}
Environment=EMAIL_API_HOST=127.0.0.1
Environment=EMAIL_API_PORT=${API_PORT}
Environment=EMAIL_DB_PATH=${APP_DIR}/data/email.db
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/deploy/vps_email/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable temp-email-api
systemctl restart temp-email-api

echo "==> Nginx..."
cat > "/etc/nginx/sites-available/temp-email" <<NGINX
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${API_HOSTNAME} _;
    location / {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/temp-email /etc/nginx/sites-enabled/temp-email
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> 自签名 HTTPS（DNS 生效后可 certbot 替换）..."
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/temp-email.key \
  -out /etc/nginx/ssl/temp-email.crt \
  -subj "/CN=${API_HOSTNAME}" 2>/dev/null
cat > "/etc/nginx/sites-available/temp-email-ssl" <<NGINX
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name ${API_HOSTNAME} _;
    ssl_certificate /etc/nginx/ssl/temp-email.crt;
    ssl_certificate_key /etc/nginx/ssl/temp-email.key;
    location / {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/temp-email-ssl /etc/nginx/sites-enabled/temp-email-ssl
nginx -t && systemctl reload nginx

ufw allow 22/tcp 2>/dev/null || true
ufw allow 25/tcp 2>/dev/null || true
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
ufw --force enable 2>/dev/null || true

sleep 2
echo "==> 本机自检..."
curl -sf "http://127.0.0.1:${API_PORT}/api/health" && echo ""
curl -sf "http://127.0.0.1/api/health" && echo ""

PUBLIC_IP=$(curl -4 -s --max-time 5 ifconfig.me || hostname -I | awk '{print $1}')
echo ""
echo "=========================================="
echo "邮箱服务已安装"
echo "  API:  http://${PUBLIC_IP}/api/health"
echo "  API:  https://${API_HOSTNAME}/api/health (需 DNS A 记录 mx1 -> ${PUBLIC_IP})"
echo "  域名: ${EMAIL_DOMAIN}"
echo ""
echo "DNSPod 请添加:"
echo "  A   mx1  ->  ${PUBLIC_IP}"
echo "  MX  @    ->  mx1.${EMAIL_DOMAIN}  优先级 10"
echo ""
echo "DNS 生效后申请正式证书:"
echo "  bash ${SCRIPT_DIR}/setup-https.sh"
echo "=========================================="

if command -v certbot >/dev/null 2>&1 && getent hosts "${API_HOSTNAME}" >/dev/null 2>&1; then
  RESOLVED=$(getent ahostsv4 "${API_HOSTNAME}" | awk '{print $1; exit}')
  if [[ -n "${RESOLVED}" ]] && [[ "${RESOLVED}" == "${PUBLIC_IP}" ]]; then
    echo "==> DNS 已指向本机，尝试申请 Let's Encrypt 证书..."
    if [[ -x "${SCRIPT_DIR}/setup-https.sh" ]]; then
      bash "${SCRIPT_DIR}/setup-https.sh" || echo "certbot 未成功，可稍后手动运行 setup-https.sh"
    fi
  fi
fi
