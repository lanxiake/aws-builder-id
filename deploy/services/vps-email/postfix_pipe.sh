#!/usr/bin/env bash
# Postfix 管道：将入站邮件写入临时邮箱 SQLite（由 install 脚本注册）
set -euo pipefail
if [[ -d /opt/temp-email/.venv ]]; then
  APP_DIR="/opt/temp-email"
elif [[ -d /opt/aws-builder-id/.venv ]]; then
  APP_DIR="/opt/aws-builder-id"
else
  APP_DIR="${APP_DIR:-/opt/temp-email}"
fi
VENV="${APP_DIR}/.venv"
RECIPIENT="${1:-}"
export EMAIL_DOMAIN="${EMAIL_DOMAIN:-metoolbot.top}"
export EMAIL_DB_PATH="${EMAIL_DB_PATH:-${APP_DIR}/data/email.db}"
if [[ -f "${APP_DIR}/deploy/services/vps-email/app.py" ]]; then
  APP_PY="${APP_DIR}/deploy/services/vps-email/app.py"
else
  APP_PY="${APP_DIR}/deploy/vps_email/app.py"
fi
exec "${VENV}/bin/python" "${APP_PY}" store "${RECIPIENT}"
