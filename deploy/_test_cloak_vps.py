#!/usr/bin/env python3
"""在 VPS 上测试 CloakBrowser 并短时启动注册。"""

import os
import sys

import paramiko

HOST = "192.119.110.157"
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE = "/opt/aws-builder-id"


def main() -> int:
    """执行远程测试命令。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username="root",
        pkey=paramiko.RSAKey.from_private_key_file(KEY),
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )

    script = f"""#!/bin/bash
set -e
cd {REMOTE}
source .venv/bin/activate
export BROWSER_ENGINE=cloak
export DISPLAY=:99
command -v Xvfb >/dev/null && (pgrep -f 'Xvfb :99' || Xvfb :99 -screen 0 1920x1080x24 &) || true
python -m cloakbrowser install 2>&1 | tail -3
python -c "import sys; sys.path.insert(0,'src'); from helpers.cloak_driver import is_cloak_enabled; print('cloak_enabled', is_cloak_enabled())"
grep -E 'engine|headless|use_proxy' config/config.yaml | head -6
# 后台跑注册
nohup env BROWSER_ENGINE=cloak python src/runners/main.py > /tmp/register_cloak.log 2>&1 &
echo PID=$!
sleep 20
tail -60 /tmp/register_cloak.log || true
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_cloak_test.sh", "w") as f:
        f.write(script)
    sftp.close()

    _, stdout, stderr = c.exec_command("bash /tmp/_cloak_test.sh", get_pty=True, timeout=300)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print(err, file=sys.stderr)
    c.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
