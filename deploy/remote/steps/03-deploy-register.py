#!/usr/bin/env python3
"""步骤3：tar 上传 + 后台安装 Chrome + pip install。"""
import os
import sys
import time
import paramiko
from scp import SCPClient

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE_DIR = "/opt/aws-builder-id"
TAR_PATH = os.path.join(os.environ.get("TEMP", "/tmp"), "aws-builder-id.tar.gz")


def get_client():
    """获取新的 SSH 连接。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    return c


def run(cmd, timeout=120):
    """新建连接执行单条命令。"""
    c = get_client()
    _, stdout, stderr = c.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    return code, out


def main():
    """部署注册工具。"""
    print("=" * 50)
    print("步骤3: 部署注册工具（tar方式）")
    print("=" * 50)

    # 1. 上传 tar
    print("\n[1/5] 上传项目 tarball...")
    c = get_client()
    c.exec_command(f"mkdir -p {REMOTE_DIR}")
    time.sleep(1)
    with SCPClient(c.get_transport()) as scp:
        scp.put(TAR_PATH, "/root/aws-builder-id.tar.gz")
    c.close()
    print(f"  上传完成 ({os.path.getsize(TAR_PATH)} bytes)")

    # 2. 解压
    print("\n[2/5] 解压...")
    code, out = run(f"cd {REMOTE_DIR} && tar -xzf /root/aws-builder-id.tar.gz")
    print(f"  exit={code}")

    # 3. 后台安装 Chrome
    print("\n[3/5] 后台安装 Chrome...")
    chrome_script = (
        "export DEBIAN_FRONTEND=noninteractive\n"
        "echo START > /tmp/chrome_install.log\n"
        "if ! command -v google-chrome >/dev/null 2>&1; then\n"
        "  install -d -m 0755 /etc/apt/keyrings 2>/dev/null\n"
        "  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --yes --dearmor -o /etc/apt/keyrings/google-chrome.gpg\n"
        "  echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list\n"
        "  apt-get update -qq >> /tmp/chrome_install.log 2>&1\n"
        "  apt-get install -y -qq google-chrome-stable >> /tmp/chrome_install.log 2>&1\n"
        "fi\n"
        "apt-get install -y -qq fonts-liberation xdg-utils >> /tmp/chrome_install.log 2>&1\n"
        "echo DONE >> /tmp/chrome_install.log\n"
    )
    c = get_client()
    sftp = c.open_sftp()
    with sftp.open("/tmp/install_chrome.sh", "w") as f:
        f.write(chrome_script)
    sftp.close()
    c.exec_command("nohup bash /tmp/install_chrome.sh > /tmp/chrome_full.log 2>&1 &")
    time.sleep(2)
    c.close()

    for i in range(60):
        time.sleep(10)
        code, out = run("tail -1 /tmp/chrome_install.log 2>/dev/null")
        line = out.strip().split("\n")[-1].strip()
        print(f"  [{(i+1)*10}s] {line}")
        if line == "DONE":
            break
    else:
        print("  Chrome 安装可能超时")

    # 4. Python venv + pip
    print("\n[4/5] 安装 Python 依赖...")
    code, out = run(
        f"cd {REMOTE_DIR} && python3 -m venv .venv && "
        "source .venv/bin/activate && "
        "pip install -q -U pip && pip install -q -r requirements.txt && "
        "echo PIP_OK",
        timeout=300,
    )
    ok = "PIP_OK" in out
    print(f"  {'成功' if ok else '失败'}")
    if not ok:
        print(out[-2000:])

    # 5. 配置：用本机 API、headless、germany
    print("\n[5/5] 写入生产配置...")
    code, out = run(
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
        "print('config updated')\"",
    )
    print(f"  {out.strip()}")

    # 验证
    print("\n=== 验证 ===")
    code, out = run("google-chrome --version 2>/dev/null || echo NO_CHROME")
    print(f"  Chrome: {out.strip()}")
    code, out = run(f"source {REMOTE_DIR}/.venv/bin/activate && python -c 'import undetected_chromedriver as uc; print(uc.__version__)' 2>&1")
    print(f"  undetected-chromedriver: {out.strip()}")
    code, out = run(f"source {REMOTE_DIR}/.venv/bin/activate && python -c 'import sys; sys.path.insert(0,\"{REMOTE_DIR}/src\"); from config import EMAIL_WORKER_URL,HEADLESS; print(EMAIL_WORKER_URL, HEADLESS)' 2>&1")
    print(f"  Config: {out.strip()}")
    code, out = run(f"ls {REMOTE_DIR}/src/runners/*.py 2>/dev/null")
    print(f"  Runners: {out.strip()}")

    print("\n" + "=" * 50)
    print("注册工具部署完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
