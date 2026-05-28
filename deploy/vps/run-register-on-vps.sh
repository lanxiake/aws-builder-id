#!/usr/bin/env bash
# 在 VPS 上运行单次 AWS Builder ID 注册
# 用法: bash /opt/aws-builder-id/deploy/vps/run-register-on-vps.sh
# 兼容: bash /opt/aws-builder-id/deploy/run_register_on_vps.sh（若存在包装脚本）

set -euo pipefail
APP_DIR="${APP_DIR:-/opt/aws-builder-id}"
LOG="/tmp/register_run.log"
PID_FILE="/tmp/register_run.pid"

cd "${APP_DIR}"
# shellcheck source=/dev/null
source .venv/bin/activate

echo "启动注册，日志: ${LOG}"
nohup python src/runners/main.py > "${LOG}" 2>&1 &
echo $! > "${PID_FILE}"
echo "PID=$(cat "${PID_FILE}")"
echo "查看: tail -f ${LOG}"
