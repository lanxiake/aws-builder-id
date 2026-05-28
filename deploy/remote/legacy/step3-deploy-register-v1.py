#!/usr/bin/env python3
"""步骤3：部署 AWS Builder ID 注册工具到 VPS。"""
import os
import sys
import paramiko
from scp import SCPClient

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE_DIR = "/opt/aws-builder-id"


def get_client():
    """通过密钥连接服务器。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username="root", pkey=key, timeout=30,
                   allow_agent=False, look_for_keys=False)
    return client


def run(client, cmd, timeout=600):
    """执行命令并打印输出。"""
    print(f"\n$ {cmd[:150]}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-5000:] if len(out) > 5000 else out)
    if code != 0:
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(f"STDERR: {err[-1000:]}")
        print(f"[exit {code}]")
    return code, out


def upload_tree(scp_client, local_dir, remote_dir, exclude=None):
    """递归上传目录（跳过排除项）。"""
    exclude = exclude or set()
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in exclude]
        rel = os.path.relpath(root, local_dir).replace("\\", "/")
        remote_path = f"{remote_dir}/{rel}" if rel != "." else remote_dir
        for f in files:
            local_path = os.path.join(root, f)
            remote_file = f"{remote_path}/{f}"
            scp_client.put(local_path, remote_file)


def main():
    """上传项目并安装注册工具。"""
    print("=" * 50)
    print("步骤3: 部署 AWS Builder ID 注册工具")
    print("=" * 50)

    client = get_client()
    print(f"已连接 root@{HOST}")

    print("\n[1/4] 创建远程目录结构...")
    dirs = [
        f"{REMOTE_DIR}/src/runners", f"{REMOTE_DIR}/src/services",
        f"{REMOTE_DIR}/src/managers", f"{REMOTE_DIR}/src/helpers",
        f"{REMOTE_DIR}/config", f"{REMOTE_DIR}/scripts",
    ]
    run(client, f"mkdir -p {' '.join(dirs)}")

    print("\n[2/4] 上传项目文件...")
    with SCPClient(client.get_transport()) as scp:
        for subdir in ["src/runners", "src/services", "src/managers", "src/helpers"]:
            local = os.path.join(PROJECT_ROOT, subdir)
            if os.path.isdir(local):
                for f in os.listdir(local):
                    fp = os.path.join(local, f)
                    if f.endswith(".py") and os.path.isfile(fp):
                        scp.put(fp, f"{REMOTE_DIR}/{subdir}/{f}")
        for f in os.listdir(os.path.join(PROJECT_ROOT, "src")):
            fp = os.path.join(PROJECT_ROOT, "src", f)
            if f.endswith(".py") and os.path.isfile(fp):
                scp.put(fp, f"{REMOTE_DIR}/src/{f}")
        scp.put(os.path.join(PROJECT_ROOT, "config", "config.yaml"),
                f"{REMOTE_DIR}/config/config.yaml")
        if os.path.isfile(os.path.join(PROJECT_ROOT, "config", "languages.yaml")):
            scp.put(os.path.join(PROJECT_ROOT, "config", "languages.yaml"),
                    f"{REMOTE_DIR}/config/languages.yaml")
        scp.put(os.path.join(PROJECT_ROOT, "requirements.txt"),
                f"{REMOTE_DIR}/requirements.txt")
        for f in os.listdir(os.path.join(PROJECT_ROOT, "scripts")):
            fp = os.path.join(PROJECT_ROOT, "scripts", f)
            if f.endswith(".py") and os.path.isfile(fp):
                scp.put(fp, f"{REMOTE_DIR}/scripts/{f}")
    print("  上传完成")

    print("\n[3/4] 安装 Chrome + Python 依赖...")
    install_cmd = (
        f"cd {REMOTE_DIR} && "
        "export DEBIAN_FRONTEND=noninteractive && "
        # Chrome
        "if ! command -v google-chrome >/dev/null 2>&1; then "
        "  install -d -m 0755 /etc/apt/keyrings && "
        "  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg && "
        "  echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list && "
        "  apt-get update -qq && apt-get install -y -qq google-chrome-stable; "
        "fi && "
        # Chrome deps
        "apt-get install -y -qq fonts-liberation libasound2t64 libatk-bridge2.0-0 libatk1.0-0 "
        "libcairo2 libcups2t64 libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libglib2.0-0 "
        "libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libx11-6 libx11-xcb1 libxcb1 "
        "libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 "
        "libxrender1 libxss1 libxtst6 xdg-utils 2>/dev/null; "
        # Python venv
        "python3 -m venv .venv && source .venv/bin/activate && "
        "pip install -q -U pip && pip install -q -r requirements.txt && "
        "echo 'INSTALL OK'"
    )
    code, out = run(client, install_cmd, timeout=600)
    if "INSTALL OK" not in out:
        print("安装可能有问题，继续检查...")

    print("\n[4/4] 验证...")
    run(client, "google-chrome --version 2>/dev/null || echo 'Chrome not installed'")
    run(client, f"source {REMOTE_DIR}/.venv/bin/activate && python -c 'import undetected_chromedriver; print(\"uc ok\")' 2>&1")
    run(client, f"source {REMOTE_DIR}/.venv/bin/activate && python -c 'from config import EMAIL_WORKER_URL; print(\"worker_url:\", EMAIL_WORKER_URL)' 2>&1",)
    run(client, f"ls -la {REMOTE_DIR}/src/runners/")

    client.close()
    print("\n" + "=" * 50)
    print("注册工具部署完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
