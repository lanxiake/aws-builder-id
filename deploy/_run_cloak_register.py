#!/usr/bin/env python3
"""部署 CloakBrowser 注册并配置美区代理后启动。"""

import os
import sys
from pathlib import Path

import paramiko
import yaml

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE = "/opt/aws-builder-id"
PROXY_URL = os.environ.get(
    "PROXY_URL",
    "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443",
)


def upload(sftp, local: Path, remote: str) -> None:
    """上传单文件。"""
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


def main() -> int:
    """上传代码、写配置并启动 cloak 注册。"""
    repo = Path(__file__).resolve().parents[1]
    files = [
        "src/helpers/account_utils.py",
        "src/helpers/cloak_driver.py",
        "src/helpers/proxy_auth_extension.py",
        "src/runners/main.py",
        "src/runners/cloak_register.py",
        "src/config.py",
        "config/config.yaml",
        "requirements.txt",
        "scripts/run_cloak_register.py",
    ]

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
    sftp = c.open_sftp()
    for rel in files:
        lp = repo / rel.replace("/", os.sep)
        if lp.exists():
            upload(sftp, lp, f"{REMOTE}/{rel}")
    sftp.close()

    cfg = yaml.safe_load((repo / "config" / "config.yaml").read_text(encoding="utf-8"))
    cfg["email"]["worker_url"] = "http://127.0.0.1:18787"
    cfg["region"]["current"] = "usa"
    cfg["region"]["use_proxy"] = True
    cfg["region"]["proxy_url"] = PROXY_URL
    cfg["browser"]["engine"] = "cloak"
    cfg["browser"]["headless"] = True

    cfg_script = f"""
import yaml
cfg = {repr(cfg)}
with open('{REMOTE}/config/config.yaml','w',encoding='utf-8') as f:
    yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)
print('config written')
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_cloak_cfg.py", "w") as f:
        f.write(cfg_script)
    sftp.close()

    run_sh = f"""#!/bin/bash
set -e
cd {REMOTE}
source .venv/bin/activate
pip install -q 'cloakbrowser[geoip]' 2>&1 | tail -3
apt-get install -y -qq xvfb libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2t64 2>/dev/null || \
  apt-get install -y -qq xvfb libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 2>/dev/null || true
python -m cloakbrowser install 2>&1 | tail -2
python /tmp/_cloak_cfg.py
pkill -f 'runners/cloak_register' 2>/dev/null || true
pkill -f 'runners/main.py' 2>/dev/null || true
sleep 1
nohup env BROWSER_ENGINE=cloak python src/runners/main.py > /tmp/register_cloak.log 2>&1 &
echo PID=$!
sleep 55
tail -70 /tmp/register_cloak.log
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_cloak_run.sh", "w") as f:
        f.write(run_sh.replace("\r\n", "\n"))
    sftp.close()

    _, stdout, stderr = c.exec_command("bash /tmp/_cloak_run.sh", get_pty=True, timeout=600)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    c.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
