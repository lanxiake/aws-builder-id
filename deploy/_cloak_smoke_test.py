#!/usr/bin/env python3
"""VPS 上 CloakBrowser 冒烟测试（无代理 / 有代理）。"""
import asyncio
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
PROXY = os.environ.get("PROXY_URL", "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.119.110.157", username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY), timeout=30)
    test_py = r'''
import asyncio
from cloakbrowser import launch_async

async def t(label, **kw):
    print("===", label, "===")
    try:
        b = await launch_async(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"], **kw)
        p = await b.new_page()
        await p.goto("https://example.com", timeout=60000)
        print("title:", await p.title())
        await b.close()
        print("OK")
    except Exception as e:
        print("FAIL:", e)

async def main():
    await t("no proxy", humanize=False, geoip=False)
    await t("with proxy", proxy=%r, humanize=False, geoip=False)
    await t("proxy+geoip", proxy=%r, humanize=False, geoip=True)

asyncio.run(main())
''' % (PROXY, PROXY)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_cloak_smoke.py", "w") as f:
        f.write(test_py)
    sftp.close()
    _, o, _ = c.exec_command(
        "cd /opt/aws-builder-id && source .venv/bin/activate && python /tmp/_cloak_smoke.py",
        get_pty=True,
        timeout=180,
    )
    o.channel.recv_exit_status()
    print(o.read().decode(errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
