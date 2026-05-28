#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE_TEST = """
import asyncio
from cloakbrowser import launch_async

P = "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443"

async def main():
    for label, kw in [
        ("humanize+geoip", dict(proxy=P, geoip=True, humanize=True)),
        ("plain", dict(proxy=P, geoip=False, humanize=False)),
    ]:
        print("===", label, "===")
        b = await launch_async(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            **kw,
        )
        p = await b.new_page()
        try:
            await p.goto(
                "https://builder.aws.com/start",
                timeout=120000,
                wait_until="domcontentloaded",
            )
            print("title:", await p.title())
            print("url:", p.url)
            await p.wait_for_timeout(8000)
            print("alive after 8s")
        except Exception as e:
            print("FAIL:", e)
        await b.close()

asyncio.run(main())
"""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.119.110.157", username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY), timeout=30)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_aws_smoke.py", "w") as f:
        f.write(REMOTE_TEST)
    sftp.close()
    _, o, _ = c.exec_command(
        "cd /opt/aws-builder-id && source .venv/bin/activate && python /tmp/_aws_smoke.py",
        get_pty=True,
        timeout=200,
    )
    o.channel.recv_exit_status()
    print(o.read().decode(errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
