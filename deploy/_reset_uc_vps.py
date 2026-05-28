#!/usr/bin/env python3
"""在 VPS 上重置 undetected_chromedriver 缓存，修复 driver 缺失/占用问题。"""

import os
import paramiko


def main() -> int:
    """写入并执行远程重置脚本。"""
    key_path = os.path.expanduser("~/.ssh/toolan_deploy.pem")
    if not os.path.isfile(key_path):
        print(f"缺少 SSH 私钥: {key_path}")
        return 1

    host = os.environ.get("DEPLOY_HOST", "192.119.110.157")

    script = r"""#!/usr/bin/env bash
set -euo pipefail
pkill -f undetected_chromedriver 2>/dev/null || true
pkill -f chromedriver 2>/dev/null || true
sleep 1
rm -rf /root/.local/share/undetected_chromedriver
rm -rf /root/.cache/undetected_chromedriver 2>/dev/null || true

cd /opt/aws-builder-id
source .venv/bin/activate

# 触发 UC 重新下载/解压驱动（只做冒烟）
# 注意：必须让 UC 使用 CloakBrowser 的 Chromium，否则会与系统 Chrome 版本不匹配。
python - <<'PY'
import undetected_chromedriver as uc
from cloakbrowser.download import ensure_binary
try:
    opts = uc.ChromeOptions()
    opts.binary_location = ensure_binary()
    d = uc.Chrome(version_main=146, options=opts, headless=True)
    d.get("https://example.com")
    print("title:", d.title)
    d.quit()
    print("uc smoke ok")
except Exception as e:
    print("uc smoke failed:", e)
    raise
PY
"""

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        host,
        username="root",
        pkey=paramiko.RSAKey.from_private_key_file(key_path),
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = c.open_sftp()
    with sftp.open("/tmp/reset_uc.sh", "w") as f:
        f.write(script.replace("\r\n", "\n"))
    sftp.close()

    _, stdout, stderr = c.exec_command("bash /tmp/reset_uc.sh", get_pty=True, timeout=300)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()

    print(out)
    if err.strip():
        print("\n--- STDERR ---")
        print(err)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

