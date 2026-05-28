#!/usr/bin/env python3
"""上传 Web 收件箱页面并在 VPS 上配置 Let's Encrypt HTTPS。"""

import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("DEPLOY_HOST", "192.119.110.157")
KEY_PATH = os.environ.get("DEPLOY_KEY", os.path.expanduser("~/.ssh/toolan_deploy.pem"))
APP_DIR = "/opt/temp-email"
REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "deploy" / "services" / "vps-email"


def run(client, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    """在远程执行命令并返回退出码与输出。"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def upload_sftp(sftp, local: Path, remote: str) -> None:
    """上传单个文件到远程路径。"""
    sftp.put(str(local), remote)


def main() -> int:
    """部署 Web UI 与 HTTPS 证书。"""
    if not KEY_PATH or not os.path.isfile(KEY_PATH):
        print(f"缺少 SSH 密钥: {KEY_PATH}")
        return 1
    if not SRC.is_dir():
        print(f"缺少源码目录: {SRC}")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username="root", pkey=key, timeout=30, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()

    remote_base = f"{APP_DIR}/deploy/vps_email"
    run(client, f"mkdir -p {remote_base}/static")
    upload_sftp(sftp, SRC / "app.py", f"{remote_base}/app.py")
    upload_sftp(sftp, SRC / "static" / "index.html", f"{remote_base}/static/index.html")
    setup_sh = REPO / "deploy" / "vps" / "setup-https.sh"
    with open(setup_sh, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n")
    with sftp.open("/tmp/setup-https.sh", "wb") as rf:
        rf.write(data)
    sftp.close()

    print("==> 重启 temp-email-api")
    code, out, err = run(client, "systemctl restart temp-email-api && sleep 1 && curl -sf http://127.0.0.1:18787/api/health")
    print(out or err)
    if code != 0:
        print("API 健康检查失败")
        return code

    print("==> 验证 Web 首页")
    code, out, _ = run(client, "curl -sf http://127.0.0.1:18787/ | head -3")
    print(out)
    if "临时邮箱" not in out and "<!DOCTYPE" not in out:
        print("Web 页面未返回 HTML")
        return 1

    print("==> 申请 Let's Encrypt 证书")
    code, out, err = run(
        client,
        "chmod +x /tmp/setup-https.sh && API_HOSTNAME=mx1.metoolbot.top bash /tmp/setup-https.sh",
        timeout=900,
    )
    print(out)
    if err:
        print(err, file=sys.stderr)

    print("==> 外网探测")
    for url in ("https://mx1.metoolbot.top/api/health", "https://mx1.metoolbot.top/"):
        code, out, err = run(client, f"curl -skI --max-time 15 {url} | head -8")
        print(f"\n--- {url} ---\n{out}{err}")

    client.close()
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
