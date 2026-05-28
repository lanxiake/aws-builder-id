#!/usr/bin/env bash
# 在 VPS 上安装与 cloudflare_temp_email 兼容的临时邮箱 API（mx1.metoolbot.top）
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aws-builder-id}"
EMAIL_DOMAIN="${EMAIL_DOMAIN:-metoolbot.top}"
API_HOSTNAME="${API_HOSTNAME:-mx1.metoolbot.top}"
API_PORT="${EMAIL_API_PORT:-18787}"
VENV="${APP_DIR}/.venv"

echo "==> 安装 Postfix / Nginx / Certbot..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postfix nginx certbot python3-certbot-nginx

echo "==> 安装邮箱 API Python 依赖..."
if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"
pip install -q -r "${APP_DIR}/deploy/services/vps-email/requirements.txt"

echo "==> 配置 Postfix 虚拟域 ${EMAIL_DOMAIN}（任意前缀 @${EMAIL_DOMAIN} 均可收信）..."
postconf -e "myhostname = ${API_HOSTNAME}"
postconf -e "mydestination ="
postconf -e "inet_interfaces = all"
postconf -e "virtual_mailbox_domains = ${EMAIL_DOMAIN}"
postconf -e "virtual_mailbox_maps = regexp:/etc/postfix/virtual_mailbox_regexp"
postconf -e "virtual_transport = tempmail:"

DOMAIN_ESC="${EMAIL_DOMAIN//./\\.}"
cat > /etc/postfix/virtual_mailbox_regexp <<EOF
/.*@${DOMAIN_ESC}\$/  OK
EOF

PIPE_SCRIPT="${APP_DIR}/deploy/services/vps-email/postfix_pipe.sh"
chmod +x "${PIPE_SCRIPT}"
if ! grep -q "^tempmail" /etc/postfix/master 2>/dev/null; then
  cat >> /etc/postfix/master <<EOF

tempmail   unix  -       n       n       -       -       pipe
  flags=FR user=nobody argv=${PIPE_SCRIPT} \${recipient}
EOF
fi

systemctl enable postfix
systemctl restart postfix

echo "==> 配置 systemd: temp-email-api..."
cat > /etc/systemd/system/temp-email-api.service <<EOF
[Unit]
Description=Temp Email API (cloudflare_temp_email compatible)
After=network.target

[Service]
Type=simple
Environment=EMAIL_DOMAIN=${EMAIL_DOMAIN}
Environment=EMAIL_API_HOST=127.0.0.1
Environment=EMAIL_API_PORT=${API_PORT}
Environment=EMAIL_DB_PATH=${APP_DIR}/data/email.db
WorkingDirectory=${APP_DIR}
ExecStart=${VENV}/bin/python ${APP_DIR}/deploy/services/vps-email/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable temp-email-api
systemctl restart temp-email-api

echo "==> 配置 Nginx 反向代理 ${API_HOSTNAME}..."
cat > "/etc/nginx/sites-available/${API_HOSTNAME}" <<'NGINX'
server {
    listen 80;
    server_name mx1.metoolbot.top;
    location / {
        proxy_pass http://127.0.0.1:18787;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX
sed -i "s/mx1.metoolbot.top/${API_HOSTNAME}/g" "/etc/nginx/sites-available/${API_HOSTNAME}"
sed -i "s/18787/${API_PORT}/g" "/etc/nginx/sites-available/${API_HOSTNAME}"
ln -sf "/etc/nginx/sites-available/${API_HOSTNAME}" "/etc/nginx/sites-enabled/${API_HOSTNAME}"
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> 申请 HTTPS 证书（需 DNS 已解析 ${API_HOSTNAME} -> 本机）..."
if certbot --nginx -d "${API_HOSTNAME}" --non-interactive --agree-tos --register-unsafely-without-email 2>/dev/null; then
  echo "HTTPS 证书已配置"
else
  echo "警告: certbot 失败，请确认 DNS A 记录后再执行:"
  echo "  certbot --nginx -d ${API_HOSTNAME}"
fi

echo ""
echo "邮箱 API: https://${API_HOSTNAME}"
echo "收信域名: ${EMAIL_DOMAIN}"
echo "测试: curl -s https://${API_HOSTNAME}/api/health"
echo "      curl -s -X POST https://${API_HOSTNAME}/api/new_address -H 'Content-Type: application/json' -d '{\"name\":\"test\"}'"
