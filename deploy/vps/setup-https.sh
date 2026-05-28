#!/usr/bin/env bash
# 为 mx1 申请 Let's Encrypt 证书并配置 Nginx HTTPS
# 前提: A 记录 mx1 指向本机公网 IP，且 Cloudflare 为「仅 DNS」(灰云)
set -euo pipefail

API_HOSTNAME="${API_HOSTNAME:-mx1.metoolbot.top}"
EMAIL_DOMAIN="${EMAIL_DOMAIN:-metoolbot.top}"
CERT_EMAIL="${CERT_EMAIL:-admin@${EMAIL_DOMAIN}}"
API_PORT="${EMAIL_API_PORT:-18787}"

echo "==> 检查 DNS..."
PUBLIC_IP=$(curl -4 -s --max-time 8 ifconfig.me || hostname -I | awk '{print $1}')
RESOLVED=$(getent ahostsv4 "${API_HOSTNAME}" 2>/dev/null | awk '{print $1; exit}' || true)
if [[ -z "${RESOLVED}" ]]; then
  echo "错误: 无法解析 ${API_HOSTNAME}，请先在 DNS 添加 A 记录"
  exit 1
fi
if [[ "${RESOLVED}" != "${PUBLIC_IP}" ]]; then
  echo "警告: ${API_HOSTNAME} -> ${RESOLVED}，本机公网 IP=${PUBLIC_IP}"
  echo "若使用 Cloudflare 橙云代理，请改为灰云(仅 DNS) 后再申请证书"
  read -r -p "仍继续申请证书? [y/N] " ans || true
  [[ "${ans:-}" =~ ^[Yy]$ ]] || exit 1
fi

echo "==> 确保 Nginx 80 可访问..."
apt-get install -y -qq certbot python3-certbot-nginx 2>/dev/null || true

cat > "/etc/nginx/sites-available/temp-email" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${API_HOSTNAME};
    location / {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/temp-email /etc/nginx/sites-enabled/temp-email
rm -f /etc/nginx/sites-enabled/temp-email-ssl 2>/dev/null || true
nginx -t && systemctl reload nginx

echo "==> certbot 申请证书..."
certbot --nginx -d "${API_HOSTNAME}" \
  --non-interactive --agree-tos --email "${CERT_EMAIL}" \
  --redirect --no-eff-email

nginx -t && systemctl reload nginx
echo ""
echo "HTTPS 已配置: https://${API_HOSTNAME}/"
certbot certificates 2>/dev/null | head -20 || true
