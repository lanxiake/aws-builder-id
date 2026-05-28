#!/usr/bin/env python3
"""验证修复后的 main.py 在 VPS 上也能正常运行。"""

import os
import sys
import time
from pathlib import Path

import paramiko
import yaml

HOST = "192.119.110.157"
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE = "/opt/aws-builder-id"
PROXY_URL = "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443"


def connect():
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
    return c


def run_cmd(c, cmd, timeout=15):
    _, stdout, _ = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="replace")


def upload(sftp, local: Path, remote: str):
    """上传单文件，自动创建远程目录。"""
    rd = os.path.dirname(remote)
    parts = rd.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)
    sftp.put(str(local), remote)


def main():
    repo = Path(__file__).resolve().parents[1]

    files = [
        "src/services/gmail_alias_service.py",
        "src/services/email_service.py",
        "src/helpers/account_utils.py",
        "src/helpers/builder_auth.py",
        "src/helpers/cloak_driver.py",
        "src/helpers/proxy_auth_extension.py",
        "src/runners/main.py",
        "src/config.py",
        "config/config.yaml",
        "requirements.txt",
    ]

    c = connect()
    sftp = c.open_sftp()
    print("Uploading files ...")
    for rel in files:
        lp = repo / rel.replace("/", os.sep)
        if lp.exists():
            upload(sftp, lp, f"{REMOTE}/{rel}")
            print(f"  + {rel}")
    sftp.close()

    # 写入 config
    cfg = yaml.safe_load((repo / "config" / "config.yaml").read_text(encoding="utf-8"))
    cfg["email"]["provider"] = "gmail_alias"
    cfg["email"]["worker_url"] = "http://127.0.0.1:18787"
    cfg["region"]["current"] = "usa"
    cfg["region"]["use_proxy"] = True
    cfg["region"]["proxy_url"] = "http://127.0.0.1:18080"
    cfg["browser"]["engine"] = "uc_plain"
    cfg["browser"]["headless"] = False

    cfg_py = f"""import yaml
cfg = {repr(cfg)}
with open('{REMOTE}/config/config.yaml','w',encoding='utf-8') as f:
    yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)
print('config written')
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_verify_cfg.py", "w") as f:
        f.write(cfg_py.replace("\r\n", "\n"))
    sftp.close()

    from urllib.parse import urlparse
    _p = urlparse(PROXY_URL)
    _pproxy_remote = f"{_p.hostname}:{_p.port}#{_p.username}:{_p.password}"

    run_sh = f"""#!/bin/bash
set -e
cd {REMOTE}
source .venv/bin/activate
python /tmp/_verify_cfg.py

rm -f /tmp/register_gmail.log
pkill -9 -f 'runners/main' 2>/dev/null || true
pkill -9 -f chrome 2>/dev/null || true
pkill -9 -f chromedriver 2>/dev/null || true
pkill -f pproxy 2>/dev/null || true
sleep 3

pkill -f Xvfb 2>/dev/null || true
sleep 1
Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
sleep 1

nohup pproxy -l http://127.0.0.1:18080 -r 'http://{_pproxy_remote}' > /tmp/pproxy.log 2>&1 &
sleep 2

export DISPLAY=:99
export BROWSER_ENGINE=uc_plain
export EMAIL_PROVIDER=gmail_alias

echo "$(date) Starting main.py" > /tmp/register_gmail.log
python src/runners/main.py >> /tmp/register_gmail.log 2>&1
echo "$(date) EXIT=$?" >> /tmp/register_gmail.log
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_verify_run.sh", "w") as f:
        f.write(run_sh.replace("\r\n", "\n"))
    sftp.close()
    c.close()

    # 用 screen 启动
    c = connect()
    run_cmd(c, "screen -X -S verify quit 2>/dev/null || true")
    time.sleep(1)
    run_cmd(c, "screen -dmS verify bash /tmp/_verify_run.sh")
    time.sleep(3)
    sess = run_cmd(c, "screen -ls 2>/dev/null || true")
    print(f"Screen: {sess.strip()}")
    c.close()

    # 轮询日志
    print("\n=== Polling main.py log ===")
    last_size = 0
    for _ in range(36):
        time.sleep(10)
        try:
            c2 = connect()
            log = run_cmd(c2, "cat /tmp/register_gmail.log 2>/dev/null")
            c2.close()
        except Exception as e:
            print(f"  (err: {e})")
            continue

        if len(log) > last_size:
            print(log[last_size:], end="")
            last_size = len(log)

        if "EXIT=" in log or "过程发生错误" in log or "账号流程结束" in log:
            print("\n--- Done ---")
            break
    else:
        print("\n--- Timeout ---")

    return 0


if __name__ == "__main__":
    sys.exit(main())
