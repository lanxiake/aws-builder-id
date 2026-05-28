#!/usr/bin/env python3
"""从服务器内部测试邮箱API，以及从本机通过IP测试。"""
import os
import sys
import json
import paramiko
import requests

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

REMOTE_TEST_SCRIPT = r"""
import urllib.request, json
data = json.dumps({"name": "remotetest"}).encode()
req = urllib.request.Request("http://127.0.0.1:18787/api/new_address", data=data, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
print(resp.read().decode())
"""


def main():
    """测试邮箱API。"""
    print("=== 服务器内部测试 ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    client.connect(HOST, username="root", pkey=key, timeout=30,
                   allow_agent=False, look_for_keys=False)

    sftp = client.open_sftp()
    sftp.open("/tmp/_test_api.py", "w").write(REMOTE_TEST_SCRIPT)
    sftp.close()

    _, stdout, stderr = client.exec_command("python3 /tmp/_test_api.py", timeout=30)
    print("  结果:", stdout.read().decode().strip())
    err = stderr.read().decode().strip()
    if err:
        print("  错误:", err)
    client.close()

    print("\n=== 本机通过IP测试 ===")
    try:
        r = requests.get(f"http://{HOST}/api/health", timeout=10)
        print(f"  GET /api/health -> {r.status_code}: {r.text.strip()}")
    except Exception as e:
        print(f"  GET 失败: {e}")

    try:
        r = requests.post(
            f"http://{HOST}/api/new_address",
            json={"name": "localiptest"},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        print(f"  POST /api/new_address -> {r.status_code}: {r.text.strip()[:200]}")
    except Exception as e:
        print(f"  POST 失败: {e}")


if __name__ == "__main__":
    main()
