#!/usr/bin/env bash
# 在服务器上执行单次 AWS Builder ID 注册
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/aws-builder-id}"
cd "${APP_DIR}"
source .venv/bin/activate
export DISPLAY="${DISPLAY:-:99}"
# 无头模式时一般不需要 Xvfb；若 headless=false 可: xvfb-run -a python src/runners/main.py
python src/runners/main.py "$@"
