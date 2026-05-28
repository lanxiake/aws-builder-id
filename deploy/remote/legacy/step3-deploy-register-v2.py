#!/usr/bin/env python3
"""步骤3b：部署注册工具——后台安装 Chrome，轮询进度。"""
import os
import sys
import time
import paramiko
from scp import SCPClient

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE_DIR = "/opt/aws-builder-id"


def get_client():
    """获取新的 SSH 连接。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username="root", pkey=key, timeout=30,
                   allow_agent=False, look_for_keys=False)
    return client


def run(client, cmd, timeout=120):
    """执行命令并返回输出。"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out


def main():
    """分步部署注册工具。"""
    print("=" * 50)
    print("步骤3: 部署注册工具")
    print("=" * 50)

    # 上传文件
    print("\n[1/5] 上传项目文件...")
    c = get_client()
    dirs = [
        f"{REMOTE_DIR}/src/runners", f"{REMOTE_DIR}/src/services",
        f"{REMOTE_DIR}/src/managers", f"{REMOTE_DIR}/src/helpers",
        f"{REMOTE_DIR}/config", f"{REMOTE_DIR}/scripts",
    ]
    c.exec_command(f"mkdir -p {' '.join(dirs)}")
    time.sleep(1)

    with SCPClient(c.get_transport()) as scp:
        for subdir in ["src", "src/runners", "src/services", "src/managers", "src/helpers"]:
            local = os.path.join(PROJECT_ROOT, subdir)
            if os.path.isdir(local):
                for f in os.listdir(local):
                    fp = os.path.join(local, f)
                    if f.endswith(".py") and os.path.isfile(fp):
                        scp.put(fp, f"{REMOTE_DIR}/{subdir}/{f}")
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
    c.close()

    # 后台安装 Chrome
    print("\n[2/5] 后台安装 Chrome（可能需要几分钟）...")
    c = get_client()
    install_script = (
        "#!/bin/bash\n"
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "echo 'START' > /tmp/chrome_install.log\n"
        "if ! command -v google-chrome >/dev/null 2>&1; then\n"
        "  echo 'installing chrome...' >> /tmp/chrome_install.log\n"
        "  install -d -m 0755 /etc/apt/keyrings\n"
        "  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg 2>/dev/null\n"
        "  echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list\n"
        "  apt-get update -qq >> /tmp/chrome_install.log 2>&1\n"
        "  apt-get install -y -qq google-chrome-stable >> /tmp/chrome_install.log 2>&1\n"
        "fi\n"
        "echo 'chrome done' >> /tmp/chrome_install.log\n"
        "apt-get install -y -qq fonts-liberation xdg-utils >> /tmp/chrome_install.log 2>&1\n"
        "echo 'DONE' >> /tmp/chrome_install.log\n"
    )
    sftp = c.open_sftp()
    with sftp.open("/tmp/install_chrome.sh", "w") as f:
        f.write(install_script)
    sftp.close()
    c.exec_command("nohup bash /tmp/install_chrome.sh > /tmp/chrome_install_full.log 2>&1 &")
    c.close()

    # 轮询
    for i in range(60):
        time.sleep(10)
        c = get_client()
        code, out = run(c, "tail -3 /tmp/chrome_install.log 2>/dev/null; echo '---'; pgrep -f install_chrome.sh >/dev/null && echo RUNNING || echo FINISHED")
        c.close()
        last = out.strip().split("\n")[-1]
        status = out.strip().split("---")[-1].strip() if "---" in out else ""
        print(f"  [{(i+1)*10}s] {last}")
        if "FINISHED" in status and "DONE" in out:
            break
    else:
        print("  超时，请检查服务器 /tmp/chrome_install.log")

    # Python venv
    print("\n[3/5] 安装 Python 依赖...")
    c = get_client()
    code, out = run(c, (
        f"cd {REMOTE_DIR} && "
        "python3 -m venv .venv && source .venv/bin/activate && "
        "pip install -q -U pip && pip install -q -r requirements.txt && "
        "echo 'PIP_OK'"
    ), timeout=300)
    print(f"  {'成功' if 'PIP_OK' in out else '可能有问题'}")
    c.close()

    # 更新配置
    print("\n[4/5] 配置: headless + 本机邮箱 API...")
    c = get_client()
    run(c, (
        f"cd {REMOTE_DIR} && source .venv/bin/activate && "
        "python3 -c \""
        "import yaml; "
        f"p='{REMOTE_DIR}/config/config.yaml'; "
        "cfg=yaml.safe_load(open(p)); "
        "cfg['email']['worker_url']='http://127.0.0.1:18787'; "
        "cfg['browser']['headless']=True; "
        "cfg['region']['current']='germany'; "
        "cfg['region']['use_proxy']=False; "
        "yaml.dump(cfg,open(p,'w'),allow_unicode=True,sort_keys=False); "
        "print('config updated')\""
    ))
    c.close()

    # 验证
    print("\n[5/5] 最终验证...")
    c = get_client()
    code, out = run(c, "google-chrome --version 2>/dev/null || echo 'NO CHROME'")
    print(f"  Chrome: {out.strip()}")
    code, out = run(c, f"source {REMOTE_DIR}/.venv/bin/activate && python -c 'import undetected_chromedriver; print(\"uc:\", undetected_chromedriver.__version__)' 2>&1")
    print(f"  UC: {out.strip()}")
    code, out = run(c, f"ls {REMOTE_DIR}/src/runners/*.py")
    print(f"  Runners: {out.strip()}")
    c.close()

    print("\n" + "=" * 50)
    print("注册工具部署完成!")
    print(f"试跑命令: ssh root@{HOST}")
    print(f"  cd {REMOTE_DIR} && source .venv/bin/activate && python src/runners/main.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
