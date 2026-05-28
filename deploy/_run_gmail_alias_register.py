#!/usr/bin/env python3
"""
部署并运行 Gmail 别名注册流程。

上传最新代码（含 gmail_alias_service）到 VPS，
配置 EMAIL_PROVIDER=gmail_alias，启动完整注册。
"""

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


def main() -> int:
    """上传代码并启动 Gmail 别名注册。"""
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
    print("📤 上传文件到 VPS ...")
    for rel in files:
        lp = repo / rel.replace("/", os.sep)
        if lp.exists():
            upload(sftp, lp, f"{REMOTE}/{rel}")
            print(f"   ✅ {rel}")
        else:
            print(f"   ⚠️  {rel} 不存在，跳过")
    sftp.close()

    # 在 VPS 上写入 config（覆盖 provider=gmail_alias + proxy 等设置）
    cfg = yaml.safe_load((repo / "config" / "config.yaml").read_text(encoding="utf-8"))
    cfg["email"]["provider"] = "gmail_alias"
    cfg["email"]["worker_url"] = "http://127.0.0.1:18787"
    cfg["email"]["poll_interval"] = 5
    cfg["region"]["current"] = "usa"
    cfg["region"]["use_proxy"] = True
    cfg["region"]["proxy_url"] = "http://127.0.0.1:18080"
    cfg["browser"]["engine"] = "uc_plain"
    cfg["browser"]["headless"] = False

    cfg_script = f"""
import yaml
cfg = {repr(cfg)}
with open('{REMOTE}/config/config.yaml','w',encoding='utf-8') as f:
    yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)
print('config written')
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_gmail_cfg.py", "w") as f:
        f.write(cfg_script)
    sftp.close()

    # 解析代理 URL 为 pproxy 格式: http://host:port#user:password
    from urllib.parse import urlparse
    _p = urlparse(PROXY_URL)
    _pproxy_remote = f"{_p.hostname}:{_p.port}#{_p.username}:{_p.password}" if _p.username else f"{_p.hostname}:{_p.port}"

    run_sh = f"""#!/bin/bash
set -e
cd {REMOTE}
source .venv/bin/activate
pip install -q pproxy 2>&1 | tail -3
python /tmp/_gmail_cfg.py
pkill -f 'runners/main.py' 2>/dev/null || true
pkill -f pproxy 2>/dev/null || true
pkill -f Xvfb 2>/dev/null || true
sleep 2

# 启动本地代理转发（无认证 → 有认证上游）
# pproxy 用 # 分隔认证: http://host:port#user:password
nohup pproxy -l http://127.0.0.1:18080 -r http://{_pproxy_remote} > /tmp/pproxy.log 2>&1 &
sleep 2
echo "本地代理 PID=$!"

export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &>/dev/null &
sleep 1
echo "===== 启动 Gmail 别名注册 (xvfb + uc_plain + local-proxy) ====="
export BROWSER_ENGINE=uc_plain
export EMAIL_PROVIDER=gmail_alias
export CHROME_LOG_FILE=/tmp/chrome_debug.log
nohup python src/runners/main.py > /tmp/register_gmail.log 2>&1 &
echo PID=$!
sleep 120
echo "===== 日志（最后 100 行） ====="
tail -100 /tmp/register_gmail.log
"""
    sftp = c.open_sftp()
    with sftp.open("/tmp/_gmail_run.sh", "w") as f:
        f.write(run_sh.replace("\r\n", "\n"))
    sftp.close()

    print("\n🚀 在 VPS 上启动注册...")
    _, stdout, stderr = c.exec_command("bash /tmp/_gmail_run.sh", get_pty=True, timeout=600)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    c.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
