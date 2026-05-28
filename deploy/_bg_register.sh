#!/bin/bash
# 后台运行独立注册脚本，自带自己的日志管理
set -e
cd /opt/aws-builder-id
source .venv/bin/activate

# 清理
rm -f /tmp/standalone.log /tmp/step_*.png /tmp/final.png /tmp/error.png /tmp/standalone_result.json
pkill -9 -f _standalone_register 2>/dev/null || true
pkill -9 -f chrome 2>/dev/null || true
pkill -9 -f chromedriver 2>/dev/null || true
pkill -f pproxy 2>/dev/null || true
sleep 3

# 确保 Xvfb 运行
pkill -f Xvfb 2>/dev/null || true
sleep 1
Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
sleep 1

# 启动 pproxy
nohup pproxy -l http://127.0.0.1:18080 -r 'http://70.39.242.6:443#WMauHktAwcKX:YiLkHvDOJs' > /tmp/pproxy.log 2>&1 &
sleep 2

export DISPLAY=:99
export PROXY_URL=http://127.0.0.1:18080
export GMAIL_BASE_USER=toojia0510
export GMAIL_APP_PASSWORD='ties zgem pvky ilah'

echo "$(date) Starting standalone register" >> /tmp/standalone.log
python /tmp/_standalone_register.py >> /tmp/standalone.log 2>&1
echo "$(date) Script finished with exit code $?" >> /tmp/standalone.log
